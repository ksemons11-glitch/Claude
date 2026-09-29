import 'server-only';
import mysql from 'mysql2/promise';
import bcrypt from 'bcryptjs';
import { config } from './config';
import { SCHEMA } from './schema';
import { generateDefaultPeriods } from './periods';
import { parseIsoDate, warsawToUtc } from './time';

type Globals = { pool?: mysql.Pool; ready?: Promise<void> };
const g = globalThis as unknown as { __lb?: Globals };
const state: Globals = (g.__lb ??= {});

function pool(): mysql.Pool {
  if (!state.pool) {
    if (!config.databaseUrl) throw new Error('DATABASE_URL is not set');
    state.pool = mysql.createPool({
      uri: config.databaseUrl,
      timezone: 'Z',
      connectionLimit: 4,
      maxIdle: 2,
      idleTimeout: 60_000,
      charset: 'utf8mb4',
      supportBigNumbers: true,
      // Managed cloud databases require TLS; a MySQL on the same host does not.
      ssl: config.databaseSsl ? { minVersion: 'TLSv1.2', rejectUnauthorized: true } : undefined,
    });
  }
  return state.pool;
}

async function bootstrap(): Promise<void> {
  const p = pool();
  for (const stmt of SCHEMA) await p.query(stmt);

  const [rows] = await p.query<mysql.RowDataPacket[]>('SELECT id FROM events WHERE slug = ?', [config.eventSlug]);
  if (rows.length > 0) return;

  const start = parseIsoDate(config.q4Start);
  const end = parseIsoDate(config.q4End);
  if (!start || !end) throw new Error('Q4_START / Q4_END must be YYYY-MM-DD');
  const now = new Date();
  const codeHash = config.eventAccessCode ? await bcrypt.hash(normalizeCode(config.eventAccessCode), 10) : null;
  const [res] = await p.query<mysql.ResultSetHeader>(
    `INSERT IGNORE INTO events (name, slug, motivation_text, access_code_hash, access_code_required, starts_at, ends_at, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      config.eventName,
      config.eventSlug,
      'Każdy tydzień to nowa szansa. Liczy się Twój przyrost!',
      codeHash,
      codeHash ? 1 : 0,
      warsawToUtc(start.y, start.m, start.d),
      warsawToUtc(end.y, end.m, end.d, 23, 59, 59),
      now,
    ],
  );
  if (!res.insertId) return; // another process created it concurrently
  for (const d of generateDefaultPeriods(start, end)) {
    await p.query(
      'INSERT INTO reporting_periods (event_id, week_number, starts_at, ends_at, entry_deadline) VALUES (?, ?, ?, ?, ?)',
      [res.insertId, d.weekNumber, d.startsAt, d.endsAt, d.entryDeadline],
    );
  }
}

export function normalizeCode(code: string): string {
  return code.trim().toLowerCase();
}

async function ready(): Promise<mysql.Pool> {
  state.ready ??= bootstrap().catch((err) => {
    state.ready = undefined;
    throw err;
  });
  await state.ready;
  return pool();
}

export async function query<T = mysql.RowDataPacket>(sql: string, params: unknown[] = []): Promise<T[]> {
  const p = await ready();
  const [rows] = await p.query(sql, params);
  return rows as T[];
}

export async function execute(sql: string, params: unknown[] = []): Promise<mysql.ResultSetHeader> {
  const p = await ready();
  const [res] = await p.query<mysql.ResultSetHeader>(sql, params);
  return res;
}

export async function transaction<T>(fn: (conn: mysql.PoolConnection) => Promise<T>): Promise<T> {
  const p = await ready();
  const conn = await p.getConnection();
  try {
    await conn.beginTransaction();
    const result = await fn(conn);
    await conn.commit();
    return result;
  } catch (err) {
    await conn.rollback();
    throw err;
  } finally {
    conn.release();
  }
}
