// Pure ranking logic — no database access, fully unit-tested.

export type Participant = {
  userId: number;
  nickname: string;
  avatarUrl: string;
};

export type EntryPoint = {
  userId: number;
  /** Index of the reporting period in the ordered list of periods. */
  periodIndex: number;
  value: number;
};

export type Ledger = {
  /** cumulative[userId][i] = latest cumulative revenue reported in periods 0..i (null = nothing yet). */
  cumulative: Map<number, (number | null)[]>;
  /** reported[userId][i] = whether the user has an entry in period i itself. */
  reported: Map<number, boolean[]>;
  periodCount: number;
};

export type RankedRow = {
  userId: number;
  nickname: string;
  avatarUrl: string;
  rank: number;
  /** Q4 view: cumulative revenue. Week view: revenue generated in that week. */
  value: number;
  cumulative: number;
  weekly: number | null;
  /** Places gained since the end of the previous week (negative = dropped). null = not applicable. */
  change: number | null;
  isNew: boolean;
};

export function buildLedger(participants: Participant[], entries: EntryPoint[], periodCount: number): Ledger {
  const cumulative = new Map<number, (number | null)[]>();
  const reported = new Map<number, boolean[]>();
  const raw = new Map<number, (number | null)[]>();
  for (const p of participants) raw.set(p.userId, new Array(periodCount).fill(null));
  for (const e of entries) {
    const row = raw.get(e.userId);
    if (row && e.periodIndex >= 0 && e.periodIndex < periodCount) row[e.periodIndex] = e.value;
  }
  for (const [userId, row] of raw) {
    let last: number | null = null;
    const cum: (number | null)[] = [];
    for (let i = 0; i < periodCount; i++) {
      if (row[i] !== null) last = row[i];
      cum.push(last);
    }
    cumulative.set(userId, cum);
    reported.set(userId, row.map((v) => v !== null));
  }
  return { cumulative, reported, periodCount };
}

/** Standard competition ranking: equal scores share a place, next place skips (1, 2, 2, 4). */
export function assignRanks<T>(items: T[], score: (t: T) => number, tieBreak: (a: T, b: T) => number): { item: T; rank: number }[] {
  const sorted = [...items].sort((a, b) => score(b) - score(a) || tieBreak(a, b));
  const out: { item: T; rank: number }[] = [];
  sorted.forEach((item, i) => {
    const rank = i > 0 && score(sorted[i - 1]) === score(item) ? out[i - 1].rank : i + 1;
    out.push({ item, rank });
  });
  return out;
}

const byNickname = (a: Participant, b: Participant) => a.nickname.localeCompare(b.nickname, 'pl');

export function cumulativeAt(ledger: Ledger, userId: number, index: number): number | null {
  if (index < 0) return null;
  return ledger.cumulative.get(userId)?.[index] ?? null;
}

/** True when the user's very first entry falls in this week, but not in week 1 (a late joiner). */
export function isLateFirstEntry(ledger: Ledger, userId: number, index: number): boolean {
  return index > 0 && Boolean(ledger.reported.get(userId)?.[index]) && cumulativeAt(ledger, userId, index - 1) === null;
}

/**
 * Revenue generated in week `index`. null when the user did not report that week, and also
 * for a late joiner's first entry: it contains all sales since 1 October, so it counts for
 * the Q4 ranking but not as a weekly increase.
 */
export function weeklyAt(ledger: Ledger, userId: number, index: number): number | null {
  if (index < 0 || !ledger.reported.get(userId)?.[index]) return null;
  if (isLateFirstEntry(ledger, userId, index)) return null;
  const now = cumulativeAt(ledger, userId, index) ?? 0;
  const before = cumulativeAt(ledger, userId, index - 1) ?? 0;
  return now - before;
}

function q4RankMap(participants: Participant[], ledger: Ledger, index: number): Map<number, number> {
  const withValue = participants.filter((p) => cumulativeAt(ledger, p.userId, index) !== null);
  const ranked = assignRanks(withValue, (p) => cumulativeAt(ledger, p.userId, index)!, byNickname);
  return new Map(ranked.map((r) => [r.item.userId, r.rank]));
}

/** Ranking of the whole Q4 by cumulative revenue as of period `index`. */
export function q4Ranking(participants: Participant[], ledger: Ledger, index: number): RankedRow[] {
  if (index < 0) return [];
  const current = participants.filter((p) => cumulativeAt(ledger, p.userId, index) !== null);
  const previous = index > 0 ? q4RankMap(participants, ledger, index - 1) : null;
  return assignRanks(current, (p) => cumulativeAt(ledger, p.userId, index)!, byNickname).map(({ item, rank }) => {
    const prevRank = previous?.get(item.userId);
    const cumulative = cumulativeAt(ledger, item.userId, index)!;
    return {
      ...item,
      rank,
      value: cumulative,
      cumulative,
      weekly: weeklyAt(ledger, item.userId, index),
      change: prevRank !== undefined ? prevRank - rank : null,
      isNew: previous !== null && prevRank === undefined,
    };
  });
}

/** Ranking of a single week by revenue generated in that week (only people who reported that week). */
export function weeklyRanking(participants: Participant[], ledger: Ledger, index: number): RankedRow[] {
  if (index < 0) return [];
  const current = participants.filter((p) => weeklyAt(ledger, p.userId, index) !== null);
  return assignRanks(current, (p) => weeklyAt(ledger, p.userId, index)!, byNickname).map(({ item, rank }) => {
    const weekly = weeklyAt(ledger, item.userId, index)!;
    return {
      ...item,
      rank,
      value: weekly,
      cumulative: cumulativeAt(ledger, item.userId, index)!,
      weekly,
      change: null,
      isNew: false,
    };
  });
}

/** How much the user needs to reach the next better place (null for the leader or when not ranked). */
export function gapToNextPlace(rows: RankedRow[], userId: number): number | null {
  const me = rows.find((r) => r.userId === userId);
  if (!me || me.rank === 1) return null;
  let best: number | null = null;
  for (const r of rows) {
    if (r.value > me.value && (best === null || r.value < best)) best = r.value;
  }
  return best === null ? null : best - me.value;
}
