import 'server-only';
import zlib from 'node:zlib';
import type { PoolConnection } from 'mysql2/promise';
import { execute, query, transaction } from './db';
import { invalidateLeaderboardCache } from './leaderboard';

// Everything needed to rebuild the ranking and the admin panel. Sessions, rate limits,
// password-reset tokens and avatar images are left out (they are either temporary or,
// for avatars, would make the file too large to upload back; missing avatars fall back
// to a preset).
const TABLES = ['events', 'reporting_periods', 'users', 'revenue_entries', 'revenue_entry_audit_log', 'correction_requests'] as const;
type TableName = (typeof TABLES)[number];

export type BackupFile = {
  format: 'q4-leaderboard-backup';
  version: 1;
  createdAt: string;
  tables: Record<TableName, Record<string, unknown>[]>;
};

const KEEP_BACKUPS = 40;
const DAY_MS = 86_400_000;

export async function buildBackup(): Promise<BackupFile> {
  const tables = {} as BackupFile['tables'];
  for (const t of TABLES) tables[t] = await query<Record<string, unknown>>(`SELECT * FROM \`${t}\``);
  return { format: 'q4-leaderboard-backup', version: 1, createdAt: new Date().toISOString(), tables };
}

export function summarize(b: BackupFile): string {
  const users = b.tables.users.filter((u) => u.status !== 'deleted').length;
  return `${users} kont, ${b.tables.revenue_entries.length} wpisów, ${b.tables.revenue_entry_audit_log.length} zmian w dzienniku`;
}

/** Stores a compressed snapshot in the database and keeps only the newest ones. */
export async function createBackup(reason: string, createdBy: number | null): Promise<{ id: number; summary: string }> {
  const backup = await buildBackup();
  const summary = summarize(backup);
  const data = zlib.gzipSync(JSON.stringify(backup));
  const res = await execute('INSERT INTO backups (created_at, reason, created_by, summary, data) VALUES (?, ?, ?, ?, ?)', [
    new Date(),
    reason.slice(0, 120),
    createdBy,
    summary,
    data,
  ]);
  const old = await query<{ id: number }>('SELECT id FROM backups ORDER BY created_at DESC, id DESC LIMIT 1000 OFFSET ?', [KEEP_BACKUPS]);
  if (old.length > 0) await execute('DELETE FROM backups WHERE id IN (?)', [old.map((r) => r.id)]);
  return { id: res.insertId, summary };
}

/** Makes an automatic snapshot if the newest one is older than a day. Safe to call often. */
export async function ensureDailyBackup(): Promise<void> {
  const rows = await query<{ at: Date | null }>('SELECT MAX(created_at) AS at FROM backups');
  const last = rows[0]?.at;
  if (last && Date.now() - last.getTime() < DAY_MS) return;
  await createBackup('Automatyczna kopia dzienna', null);
}

export async function listBackups() {
  return query<{ id: number; createdAt: Date; reason: string; summary: string; size: number; by: string | null }>(
    `SELECT b.id, b.created_at AS createdAt, b.reason, b.summary, LENGTH(b.data) AS size, u.public_nickname AS \`by\`
     FROM backups b LEFT JOIN users u ON u.id = b.created_by ORDER BY b.created_at DESC, b.id DESC`,
  );
}

export async function readBackup(id: number): Promise<BackupFile | null> {
  const rows = await query<{ data: Buffer }>('SELECT data FROM backups WHERE id = ?', [id]);
  if (!rows[0]) return null;
  return JSON.parse(zlib.gunzipSync(rows[0].data).toString('utf8')) as BackupFile;
}

export function parseBackupFile(text: string): BackupFile | { error: string } {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { error: 'To nie jest poprawny plik kopii (JSON).' };
  }
  const b = parsed as Partial<BackupFile>;
  if (b?.format !== 'q4-leaderboard-backup' || !b.tables) return { error: 'To nie jest plik kopii rankingu Q4.' };
  for (const t of TABLES) if (!Array.isArray(b.tables[t])) return { error: `W pliku brakuje tabeli ${t}.` };
  if (b.tables.events.length === 0) return { error: 'Kopia nie zawiera eventu.' };
  return b as BackupFile;
}

const COLUMN_RE = /^[a-z_]+$/;
const ISO_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/;

async function insertRows(conn: PoolConnection, table: TableName, rows: Record<string, unknown>[]) {
  if (rows.length === 0) return;
  const columns = Object.keys(rows[0]).filter((c) => COLUMN_RE.test(c));
  for (let i = 0; i < rows.length; i += 500) {
    const values = rows.slice(i, i + 500).map((r) =>
      columns.map((c) => {
        const v = r[c];
        // JSON turns DATETIME values into ISO strings; turn them back into dates.
        // (No user-entered field can hold this exact format — nicknames cannot contain ':'.)
        return typeof v === 'string' && ISO_RE.test(v) ? new Date(v) : v;
      }),
    );
    await conn.query(`INSERT INTO \`${table}\` (${columns.map((c) => `\`${c}\``).join(', ')}) VALUES ?`, [values]);
  }
}

/**
 * Replaces all ranking data with the backup's content in one transaction (all or nothing).
 * A snapshot of the current state is taken first, so a restore can itself be undone.
 */
export async function restoreBackup(backup: BackupFile, adminId: number): Promise<string> {
  await createBackup('Automatycznie przed przywróceniem kopii', adminId);
  await transaction(async (conn) => {
    await conn.query('SET FOREIGN_KEY_CHECKS = 0');
    try {
      for (const t of [...TABLES].reverse()) await conn.query(`DELETE FROM \`${t}\``);
      for (const t of TABLES) await insertRows(conn, t, backup.tables[t]);
      // Sessions of accounts that do not exist in the backup are dropped.
      await conn.query('DELETE FROM sessions WHERE user_id NOT IN (SELECT id FROM users)');
    } finally {
      await conn.query('SET FOREIGN_KEY_CHECKS = 1');
    }
  });
  invalidateLeaderboardCache();
  return summarize(backup);
}

export async function backupAdminExists(backup: BackupFile, adminId: number): Promise<boolean> {
  return backup.tables.users.some((u) => Number(u.id) === adminId && u.role === 'admin');
}

