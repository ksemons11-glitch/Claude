import { NextResponse, type NextRequest } from 'next/server';
import { getCurrentUser } from '@/lib/auth';
import { buildBackup, readBackup } from '@/lib/backup';
import { isAdminUser } from '@/lib/maintenance';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  if (!isAdminUser(await getCurrentUser())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const id = req.nextUrl.searchParams.get('id') ?? 'current';
  const backup = id === 'current' ? await buildBackup() : await readBackup(Number(id));
  if (!backup) return NextResponse.json({ error: 'not found' }, { status: 404 });
  const stamp = backup.createdAt.slice(0, 16).replace(/[:T]/g, '-');
  return new NextResponse(JSON.stringify(backup), {
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Content-Disposition': `attachment; filename="ranking-q4-kopia-${stamp}.json"`,
      'Cache-Control': 'no-store',
    },
  });
}
