import { AVATAR_TYPES, readAvatar } from '@/lib/uploads';

export async function GET(_req: Request, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const data = await readAvatar(name);
  if (!data) return new Response('Not found', { status: 404 });
  return new Response(new Uint8Array(data), {
    headers: {
      'Content-Type': AVATAR_TYPES[name.split('.').pop()!],
      'Cache-Control': 'public, max-age=31536000, immutable',
      'Content-Security-Policy': "default-src 'none'",
    },
  });
}
