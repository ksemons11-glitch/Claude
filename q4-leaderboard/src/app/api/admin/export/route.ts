import { NextResponse, type NextRequest } from 'next/server';
import { getCurrentUser } from '@/lib/auth';
import { query } from '@/lib/db';
import { getEvent, getPeriods } from '@/lib/data';
import { loadLeaderboard } from '@/lib/leaderboard';
import { formatFull } from '@/lib/time';

export const dynamic = 'force-dynamic';

// Excel (Polish locale) opens ";"-separated UTF-8 files with BOM correctly.
function csv(rows: (string | number | null)[][]): string {
  const cell = (v: string | number | null) => {
    let s = v === null ? '' : String(v);
    if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`; // prevent formula injection
    return /[";\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return '﻿' + rows.map((r) => r.map(cell).join(';')).join('\r\n');
}

export async function GET(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user || user.role !== 'admin' || user.status !== 'active') return NextResponse.json({ error: 'forbidden' }, { status: 403 });

  const type = req.nextUrl.searchParams.get('type') === 'entries' ? 'entries' : 'users';
  const event = await getEvent();
  let body: string;

  if (type === 'users') {
    const lb = await loadLeaderboard();
    const rank = new Map(lb.rankings.q4.map((r) => [r.userId, r]));
    const users = await query<Record<string, unknown>>(
      `SELECT id, email, discord_nickname, public_nickname, role, status, created_at, verified_at, consent_public_profile_at, deletion_requested_at
       FROM users WHERE status <> 'deleted' ORDER BY id`,
    );
    body = csv([
      ['id', 'email', 'discord', 'nick', 'rola', 'status', 'miejsce_q4', 'przychod_q4', 'rejestracja', 'akceptacja', 'zgoda_publiczna', 'prosba_usuniecia'],
      ...users.map((u) => {
        const r = rank.get(Number(u.id));
        const d = (v: unknown) => (v instanceof Date ? formatFull(v) : null);
        return [
          Number(u.id),
          String(u.email),
          String(u.discord_nickname),
          String(u.public_nickname),
          String(u.role),
          String(u.status),
          r?.rank ?? null,
          r?.cumulative ?? null,
          d(u.created_at),
          d(u.verified_at),
          d(u.consent_public_profile_at),
          d(u.deletion_requested_at),
        ];
      }),
    ]);
  } else {
    const periods = await getPeriods(event.id);
    const entries = await query<{ userId: number; email: string; nick: string; periodId: number; value: number | string; updatedAt: Date }>(
      `SELECT e.user_id AS userId, u.email, u.public_nickname AS nick, e.reporting_period_id AS periodId, e.cumulative_revenue AS value, e.updated_at AS updatedAt
       FROM revenue_entries e JOIN users u ON u.id = e.user_id
       WHERE e.event_id = ? AND u.status <> 'deleted'`,
      [event.id],
    );
    const week = new Map(periods.map((p) => [p.id, p.weekNumber]));
    const firstWeek = periods[0]?.weekNumber;
    entries.sort((a, b) => a.nick.localeCompare(b.nick, 'pl') || (week.get(a.periodId) ?? 0) - (week.get(b.periodId) ?? 0));
    const last = new Map<number, number>();
    body = csv([
      ['nick', 'email', 'tydzien', 'przychod_narastajaco', 'przyrost_tygodnia', 'zmieniono'],
      ...entries.map((e) => {
        const v = Number(e.value);
        const prev = last.get(e.userId);
        // A late joiner's first entry is not a weekly increase (same rule as the ranking).
        const weekly = prev === undefined && week.get(e.periodId) !== firstWeek ? null : v - (prev ?? 0);
        last.set(e.userId, v);
        return [e.nick, e.email, week.get(e.periodId) ?? null, v, weekly, formatFull(e.updatedAt)];
      }),
    ]);
  }

  return new NextResponse(body, {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="${event.slug}-${type}.csv"`,
      'Cache-Control': 'no-store',
    },
  });
}
