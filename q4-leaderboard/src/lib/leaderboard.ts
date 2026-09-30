import 'server-only';
import { cache } from 'react';
import { query } from './db';
import { avatarUrl, getEvent, getPeriods } from './data';
import { currentPeriodState, type PeriodState } from './periods';
import { buildLedger, cumulativeAt, gapToNextPlace, q4Ranking, weeklyRanking, type EntryPoint, type Participant, type RankedRow } from './ranking';

export type RankingView = 'q4' | 'week' | 'prev';

export function parseView(v: unknown): RankingView {
  return v === 'week' || v === 'prev' ? v : 'q4';
}

/**
 * Everything a guest may see about a participant. Built by whitelisting fields,
 * so e-mail, Discord nick or internal ids can never leak into public pages/API.
 */
export type PublicRow = {
  rank: number;
  nickname: string;
  avatarUrl: string;
  value: number;
  cumulative: number;
  weekly: number | null;
  change: number | null;
  isNew: boolean;
  isMe: boolean;
};

export function toPublicRow(r: RankedRow, meId: number | null): PublicRow {
  return {
    rank: r.rank,
    nickname: r.nickname,
    avatarUrl: r.avatarUrl,
    value: r.value,
    cumulative: r.cumulative,
    weekly: r.weekly,
    change: r.change,
    isNew: r.isNew,
    isMe: meId !== null && r.userId === meId,
  };
}

type RawUser = { id: number; nick: string; preset: string | null; file: string | null };
type RawEntry = { userId: number; periodId: number; value: number | string };

// Many people open the ranking at the same moment (e.g. after a Discord announcement).
// Sharing the raw rows for a few seconds per server instance keeps the database load flat;
// every write in this instance clears it, so people see their own change immediately.
// Kept on globalThis: Next.js bundles pages and server actions separately, so a plain
// module variable would give each bundle its own copy and writes could not clear it.
const RAW_TTL_MS = 5_000;
type RawCache = { at: number; eventId: number; users: RawUser[]; entries: RawEntry[] };
const store = globalThis as unknown as { __lbRaw?: RawCache | null };

export function invalidateLeaderboardCache(): void {
  store.__lbRaw = null;
}

async function loadRaw(eventId: number): Promise<{ users: RawUser[]; entries: RawEntry[] }> {
  const rawCache = store.__lbRaw;
  if (rawCache && rawCache.eventId === eventId && Date.now() - rawCache.at < RAW_TTL_MS) return rawCache;
  const [users, entries] = await Promise.all([
    query<RawUser>(
      `SELECT id, public_nickname AS nick, avatar_preset AS preset, avatar_file AS file
       FROM users WHERE status = 'active' AND role = 'participant'`,
    ),
    query<RawEntry>(
      `SELECT user_id AS userId, reporting_period_id AS periodId, cumulative_revenue AS value
       FROM revenue_entries WHERE event_id = ?`,
      [eventId],
    ),
  ]);
  const fresh: RawCache = { at: Date.now(), eventId, users, entries };
  store.__lbRaw = fresh;
  return fresh;
}

/**
 * @param adminPreview when Q4 has not started yet, show the ranking as of the latest week that
 *   already has entries (e.g. generated test data) — only ever passed for administrators.
 */
export const loadLeaderboard = cache(async (adminPreview = false) => {
  const now = new Date();
  const event = await getEvent();
  const periods = await getPeriods(event.id);
  let state: PeriodState = currentPeriodState(periods, now);

  const { users, entries: rawEntries } = await loadRaw(event.id);
  const participants: Participant[] = users.map((u) => ({
    userId: u.id,
    nickname: u.nick,
    avatarUrl: avatarUrl({ avatarPreset: u.preset, avatarFile: u.file }),
  }));

  const indexById = new Map(periods.map((p, i) => [p.id, i]));
  const entries: EntryPoint[] = rawEntries.map((e) => ({
    userId: e.userId,
    periodIndex: indexById.get(e.periodId) ?? -1,
    value: Number(e.value),
  }));
  const ledger = buildLedger(participants, entries, periods.length);

  let preview = false;
  if (adminPreview && state.phase === 'before' && entries.length > 0) {
    state = { phase: 'running', index: Math.max(0, ...entries.map((e) => e.periodIndex)) };
    preview = true;
  }

  const q4 = q4Ranking(participants, ledger, state.index);
  const week = weeklyRanking(participants, ledger, state.index);
  const prev = weeklyRanking(participants, ledger, state.index - 1);
  const totalRevenue = participants.reduce((sum, p) => sum + (cumulativeAt(ledger, p.userId, state.index) ?? 0), 0);

  return {
    now,
    event,
    periods,
    state,
    preview,
    currentPeriod: state.index >= 0 ? periods[state.index] : null,
    participantsCount: participants.length,
    totalRevenue,
    rankings: { q4, week, prev } as Record<RankingView, RankedRow[]>,
  };
});

export type Leaderboard = Awaited<ReturnType<typeof loadLeaderboard>>;

/** Data for the "Twoja pozycja" card. */
export function myPosition(lb: Leaderboard, userId: number) {
  const row = lb.rankings.q4.find((r) => r.userId === userId) ?? null;
  const weekRow = lb.rankings.week.find((r) => r.userId === userId) ?? null;
  return {
    row,
    weekRank: weekRow?.rank ?? null,
    gap: gapToNextPlace(lb.rankings.q4, userId),
    total: lb.rankings.q4.length,
  };
}

/** Whether positions are still hidden from non-admins (the ranking "reveal" has not happened yet). */
export function isRankingHidden(event: { rankingRevealAt: Date | null }, now: Date): boolean {
  return event.rankingRevealAt !== null && now < event.rankingRevealAt;
}
