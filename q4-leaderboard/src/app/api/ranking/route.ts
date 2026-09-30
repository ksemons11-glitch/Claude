import { NextResponse, type NextRequest } from 'next/server';
import { getCurrentUser } from '@/lib/auth';
import { siteClosedFor } from '@/lib/maintenance';
import { isRankingHidden, loadLeaderboard, parseView, toPublicRow } from '@/lib/leaderboard';

export const dynamic = 'force-dynamic';

// Public paging/search endpoint. Returns only whitelisted public fields (see toPublicRow).
export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const user = await getCurrentUser();
  const isAdmin = user?.role === 'admin' && user.status === 'active';
  const lb = await loadLeaderboard(isAdmin);
  if (siteClosedFor(lb.event, user)) return NextResponse.json({ error: 'maintenance' }, { status: 503 });
  if (!isAdmin && isRankingHidden(lb.event, lb.now)) {
    return NextResponse.json({ rows: [], total: 0 }, { headers: { 'Cache-Control': 'no-store' } });
  }
  if (!lb.event.isPublicLeaderboard && user?.status !== 'active') {
    return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  }
  const meId = user?.status === 'active' ? user.id : null;
  const all = lb.rankings[parseView(sp.get('view'))];
  const offset = Math.max(0, Number(sp.get('offset')) || 0);
  const limit = Math.min(50, Math.max(1, Number(sp.get('limit')) || 25));
  const q = (sp.get('q') ?? '').trim().toLocaleLowerCase('pl').slice(0, 40);

  const source = q ? all.filter((r) => r.nickname.toLocaleLowerCase('pl').includes(q)) : all.slice(offset);
  return NextResponse.json(
    { rows: source.slice(0, limit).map((r) => toPublicRow(r, meId)), total: all.length },
    { headers: { 'Cache-Control': 'no-store' } },
  );
}
