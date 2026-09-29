import fs from 'node:fs/promises';
import path from 'node:path';
import { AVATAR_FILE_RE, uploadDir } from '@/lib/uploads';

const TYPES: Record<string, string> = { webp: 'image/webp', jpg: 'image/jpeg', png: 'image/png' };

export async function GET(_req: Request, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  if (!AVATAR_FILE_RE.test(name)) return new Response('Not found', { status: 404 });
  try {
    const buf = await fs.readFile(path.join(uploadDir(), name));
    return new Response(new Uint8Array(buf), {
      headers: {
        'Content-Type': TYPES[name.split('.').pop()!],
        'Cache-Control': 'public, max-age=31536000, immutable',
        'Content-Security-Policy': "default-src 'none'",
      },
    });
  } catch {
    return new Response('Not found', { status: 404 });
  }
}
