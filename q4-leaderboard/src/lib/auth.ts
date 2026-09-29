import 'server-only';
import crypto from 'node:crypto';
import { cache } from 'react';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { config } from './config';
import { execute, query } from './db';
import { userColumns, type UserRow } from './data';

const COOKIE = 'lb_session';
const SESSION_DAYS = 30;

export const sha256 = (s: string) => crypto.createHash('sha256').update(s).digest('hex');
export const randomToken = () => crypto.randomBytes(32).toString('base64url');

export async function createSession(userId: number): Promise<void> {
  const token = randomToken();
  const expires = new Date(Date.now() + SESSION_DAYS * 86_400_000);
  await execute('INSERT INTO sessions (id, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)', [
    sha256(token),
    userId,
    expires,
    new Date(),
  ]);
  (await cookies()).set(COOKIE, token, {
    httpOnly: true,
    secure: config.secureCookies,
    sameSite: 'lax',
    path: '/',
    expires,
  });
}

export async function destroySession(): Promise<void> {
  const jar = await cookies();
  const token = jar.get(COOKIE)?.value;
  if (token) await execute('DELETE FROM sessions WHERE id = ?', [sha256(token)]);
  jar.delete(COOKIE);
}

export async function destroyAllSessions(userId: number): Promise<void> {
  await execute('DELETE FROM sessions WHERE user_id = ?', [userId]);
}

/** Logged-in user for this request (deleted accounts count as logged out). */
export const getCurrentUser = cache(async (): Promise<UserRow | null> => {
  const token = (await cookies()).get(COOKIE)?.value;
  if (!token) return null;
  const rows = await query<UserRow>(
    `SELECT ${userColumns('u')}
     FROM sessions s JOIN users u ON u.id = s.user_id
     WHERE s.id = ? AND s.expires_at > ? AND u.status <> 'deleted'`,
    [sha256(token), new Date()],
  );
  return rows[0] ?? null;
});

export async function requireUser(): Promise<UserRow> {
  const user = await getCurrentUser();
  if (!user) redirect('/logowanie');
  return user;
}

export async function requireAdmin(): Promise<UserRow> {
  const user = await getCurrentUser();
  if (!user || user.role !== 'admin' || user.status !== 'active') redirect('/logowanie');
  return user;
}
