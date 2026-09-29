import 'server-only';
import { cache } from 'react';
import { query } from './db';
import { avatarUrl, getEvent, getPeriods } from './data';
import { currentPeriodState } from './periods';
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

export const loadLeaderboard = cache(async () => {
  const now = new Date();
  const event = await getEvent();
  const periods = await getPeriods(event.id);
  const state = currentPeriodState(periods, now);

  const users = await query<{ id: number; nick: string; preset: string | null; file: string | null }>(
    `SELECT id, public_nickname AS nick, avatar_preset AS preset, avatar_file AS file
     FROM users WHERE status = 'active' AND role = 'participant'`,
  );
  const participants: Participant[] = users.map((u) => ({
    userId: u.id,
    nickname: u.nick,
    avatarUrl: avatarUrl({ avatarPreset: u.preset, avatarFile: u.file }),
  }));

  const indexById = new Map(periods.map((p, i) => [p.id, i]));
  const rawEntries = await query<{ userId: number; periodId: number; value: number | string }>(
    `SELECT user_id AS userId, reporting_period_id AS periodId, cumulative_revenue AS value
     FROM revenue_entries WHERE event_id = ?`,
    [event.id],
  );
  const entries: EntryPoint[] = rawEntries.map((e) => ({
    userId: e.userId,
    periodIndex: indexById.get(e.periodId) ?? -1,
    value: Number(e.value),
  }));
  const ledger = buildLedger(participants, entries, periods.length);

  const q4 = q4Ranking(participants, ledger, state.index);
  const week = weeklyRanking(participants, ledger, state.index);
  const prev = weeklyRanking(participants, ledger, state.index - 1);
  const totalRevenue = participants.reduce((sum, p) => sum + (cumulativeAt(ledger, p.userId, state.index) ?? 0), 0);

  return {
    now,
    event,
    periods,
    state,
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
