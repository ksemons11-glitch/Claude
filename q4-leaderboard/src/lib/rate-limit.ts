import 'server-only';
import crypto from 'node:crypto';
import type { RowDataPacket } from 'mysql2/promise';
import { headers } from 'next/headers';
import { execute, transaction } from './db';

// Attempt limits live in the database so they hold across all server instances
// (on Vercel an in-memory counter resets with every new instance). Keys are hashed,
// so no e-mail or IP address is stored in plain text.
const bucketOf = (key: string) => crypto.createHash('sha256').update(key).digest('hex');

/** Records an attempt; returns false once `limit` attempts were made within `windowMs`. */
export async function hit(key: string, limit: number, windowMs: number): Promise<boolean> {
  const now = Date.now();
  const bucket = bucketOf(key);
  try {
    const allowed = await transaction(async (conn) => {
      await conn.query('DELETE FROM rate_limits WHERE bucket = ? AND hit_at < ?', [bucket, new Date(now - windowMs)]);
      const [rows] = await conn.query<RowDataPacket[]>('SELECT COUNT(*) AS n FROM rate_limits WHERE bucket = ?', [bucket]);
      if (Number(rows[0]?.n ?? 0) >= limit) return false;
      await conn.query('INSERT INTO rate_limits (bucket, hit_at) VALUES (?, ?)', [bucket, new Date(now)]);
      return true;
    });
    // Occasionally sweep old rows of all buckets (no window is longer than an hour).
    if (allowed && Math.random() < 0.02) {
      await execute('DELETE FROM rate_limits WHERE hit_at < ?', [new Date(now - 3_600_000)]).catch(() => {});
    }
    return allowed;
  } catch (err) {
    // Fail open: a database hiccup must not lock real participants out of logging in.
    console.error('[rate-limit] check failed', err);
    return true;
  }
}

export async function clientIp(): Promise<string> {
  const h = await headers();
  return h.get('x-forwarded-for')?.split(',')[0]?.trim() || h.get('x-real-ip') || 'unknown';
}
