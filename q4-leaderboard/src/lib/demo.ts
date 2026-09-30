import 'server-only';
import bcrypt from 'bcryptjs';
import crypto from 'node:crypto';
import { execute, query } from './db';
import { AVATAR_PRESETS, getPeriods } from './data';

// Test accounts let organisers see a full ranking before real participants report.
// They are recognisable by their e-mail domain and can be removed in one go.
export const DEMO_EMAIL_DOMAIN = 'demo.invalid';

const FIRST = ['Szybki', 'Złoty', 'Nocny', 'Leśny', 'Cichy', 'Dziki', 'Mocny', 'Sprytny', 'Nowy', 'Wielki', 'Turbo', 'Eko', 'Retro', 'Smart', 'Happy', 'Prime', 'Mega', 'Super'];
const SECOND = ['Sklep', 'Koszyk', 'Market', 'Butik', 'Kram', 'Store', 'Shop', 'Handel', 'Outlet', 'Box', 'Dostawa', 'Zakupy', 'Deal'];

const pick = <T,>(arr: readonly T[]) => arr[crypto.randomInt(arr.length)];
const between = (min: number, max: number) => min + crypto.randomInt(max - min + 1);

export async function countDemoAccounts(): Promise<number> {
  const rows = await query<{ n: number }>('SELECT COUNT(*) AS n FROM users WHERE email LIKE ?', [`%@${DEMO_EMAIL_DOMAIN}`]);
  return Number(rows[0]?.n ?? 0);
}

/**
 * Creates `count` active test participants with cumulative revenue in the first three weeks
 * (a few join only in week 2, to show how late joiners look). Returns how many were created.
 */
export async function seedDemoData(eventId: number, count: number): Promise<number> {
  if ((await countDemoAccounts()) > 0) return 0;
  const periods = (await getPeriods(eventId)).slice(0, 3);
  if (periods.length === 0) return 0;

  const taken = new Set((await query<{ n: string }>('SELECT LOWER(public_nickname) AS n FROM users')).map((r) => r.n));
  // A real hash of a random password: the accounts exist but nobody can log into them.
  const passwordHash = await bcrypt.hash(crypto.randomBytes(24).toString('hex'), 10);
  const now = new Date();

  let created = 0;
  const entryRows: unknown[][] = [];
  for (let i = 1; i <= count; i++) {
    let nick = '';
    do nick = `${pick(FIRST)}${pick(SECOND)}${crypto.randomInt(3) === 0 ? '' : between(1, 99)}`;
    while (taken.has(nick.toLowerCase()) || nick.length > 24);
    taken.add(nick.toLowerCase());

    const res = await execute(
      `INSERT INTO users (email, password_hash, discord_nickname, public_nickname, avatar_preset, role, status,
                          consent_terms_at, consent_public_profile_at, verified_at, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, 'participant', 'active', ?, ?, ?, ?, ?)`,
      [`test${i}-${crypto.randomBytes(3).toString('hex')}@${DEMO_EMAIL_DOMAIN}`, passwordHash, `test_${i}`, nick, pick(AVATAR_PRESETS), now, now, now, now, now],
    );

    // Weekly sales between a few and several dozen thousand złoty, growing unevenly.
    const lateJoiner = i > count - 5 && periods.length > 1;
    let cumulative = 0;
    for (let w = lateJoiner ? 1 : 0; w < periods.length; w++) {
      cumulative += w === 1 && lateJoiner ? between(8_000, 60_000) : between(1_500, 45_000);
      entryRows.push([eventId, res.insertId, periods[w].id, cumulative, now, now]);
    }
    created++;
  }
  await execute(
    'INSERT INTO revenue_entries (event_id, user_id, reporting_period_id, cumulative_revenue, created_at, updated_at) VALUES ?',
    [entryRows],
  );
  return created;
}

/** Deletes all test accounts together with their entries (and their audit-log rows). */
export async function removeDemoData(): Promise<number> {
  const ids = (await query<{ id: number }>('SELECT id FROM users WHERE email LIKE ?', [`%@${DEMO_EMAIL_DOMAIN}`])).map((r) => r.id);
  if (ids.length === 0) return 0;
  await execute('DELETE FROM revenue_entry_audit_log WHERE user_id IN (?)', [ids]);
  await execute('DELETE FROM users WHERE id IN (?)', [ids]); // entries, sessions, corrections cascade
  return ids.length;
}
