import 'server-only';
import crypto from 'node:crypto';
import { execute, query } from './db';

// Avatars live in the database (256×256, a few dozen KB each), so the app needs no
// writable disk and runs the same on shared hosting and serverless platforms.
export const MAX_AVATAR_BYTES = 300 * 1024;
export const AVATAR_FILE_RE = /^[a-f0-9]{32}\.(webp|jpg|png)$/;
export const AVATAR_TYPES: Record<string, string> = { webp: 'image/webp', jpg: 'image/jpeg', png: 'image/png' };

function detectType(buf: Buffer): 'webp' | 'jpg' | 'png' | null {
  if (buf.length > 12 && buf.toString('ascii', 0, 4) === 'RIFF' && buf.toString('ascii', 8, 12) === 'WEBP') return 'webp';
  if (buf.length > 3 && buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) return 'jpg';
  if (buf.length > 8 && buf.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) return 'png';
  return null;
}

/**
 * Stores an avatar sent as a data URL (the browser already cropped and scaled it
 * to 256×256). The file type is checked by its content, not by what the client claims.
 */
export async function saveAvatarDataUrl(dataUrl: string): Promise<{ file: string } | { error: string }> {
  const m = /^data:image\/(webp|jpeg|png);base64,([A-Za-z0-9+/=]+)$/.exec(dataUrl);
  if (!m) return { error: 'Nieprawidłowy plik awatara.' };
  const buf = Buffer.from(m[2], 'base64');
  if (buf.length > MAX_AVATAR_BYTES) return { error: 'Awatar jest za duży (maks. 300 KB po zmniejszeniu).' };
  const type = detectType(buf);
  if (!type) return { error: 'Dozwolone formaty awatara: JPG, PNG, WEBP.' };
  const file = `${crypto.randomBytes(16).toString('hex')}.${type}`;
  await execute('INSERT INTO avatars (name, data, created_at) VALUES (?, ?, ?)', [file, buf, new Date()]);
  return { file };
}

export async function readAvatar(file: string): Promise<Buffer | null> {
  if (!AVATAR_FILE_RE.test(file)) return null;
  const rows = await query<{ data: Buffer }>('SELECT data FROM avatars WHERE name = ?', [file]);
  return rows[0]?.data ?? null;
}

export async function deleteAvatar(file: string | null): Promise<void> {
  if (!file || !AVATAR_FILE_RE.test(file)) return;
  await execute('DELETE FROM avatars WHERE name = ?', [file]);
}
