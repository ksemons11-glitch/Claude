import { describe, expect, it } from 'vitest';
import { assignRanks, buildLedger, gapToNextPlace, q4Ranking, weeklyAt, weeklyRanking, type Participant } from './ranking';

const people: Participant[] = ['Ala', 'Bartek', 'Celina', 'Darek', 'Ewa'].map((nickname, i) => ({
  userId: i + 1,
  nickname,
  avatarUrl: '',
}));

describe('assignRanks', () => {
  it('gives equal scores the same place and skips the following one', () => {
    const ranked = assignRanks([10, 20, 20, 5], (x) => x, () => 0);
    expect(ranked.map((r) => [r.item, r.rank])).toEqual([
      [20, 1],
      [20, 1],
      [10, 3],
      [5, 4],
    ]);
  });
});

describe('weekly revenue', () => {
  it('is the difference between cumulative values (spec example: 12k then 29k → 17k)', () => {
    const ledger = buildLedger(people, [
      { userId: 1, periodIndex: 0, value: 12_000 },
      { userId: 1, periodIndex: 1, value: 29_000 },
    ], 3);
    expect(weeklyAt(ledger, 1, 0)).toBe(12_000);
    expect(weeklyAt(ledger, 1, 1)).toBe(17_000);
    expect(weeklyAt(ledger, 1, 2)).toBeNull();
  });

  it("does not count a late joiner's first entry as a weekly increase", () => {
    const ledger = buildLedger(people, [
      { userId: 2, periodIndex: 2, value: 50_000 },
      { userId: 2, periodIndex: 3, value: 56_000 },
    ], 4);
    expect(weeklyAt(ledger, 2, 2)).toBeNull();
    expect(weeklyAt(ledger, 2, 3)).toBe(6_000);
    expect(q4Ranking(people, ledger, 2).map((r) => [r.nickname, r.value, r.weekly, r.isNew])).toEqual([['Bartek', 50_000, null, true]]);
    expect(weeklyRanking(people, ledger, 2)).toEqual([]);
    expect(weeklyRanking(people, ledger, 3).map((r) => r.value)).toEqual([6_000]);
  });

  it('carries the last value forward over a skipped week', () => {
    const ledger = buildLedger(people, [
      { userId: 1, periodIndex: 0, value: 10_000 },
      { userId: 1, periodIndex: 2, value: 25_000 },
    ], 3);
    expect(weeklyAt(ledger, 1, 1)).toBeNull();
    expect(weeklyAt(ledger, 1, 2)).toBe(15_000);
  });
});

describe('q4Ranking', () => {
  const ledger = buildLedger(people, [
    { userId: 1, periodIndex: 0, value: 50_000 },
    { userId: 2, periodIndex: 0, value: 40_000 },
    { userId: 3, periodIndex: 0, value: 30_000 },
    { userId: 1, periodIndex: 1, value: 55_000 },
    { userId: 3, periodIndex: 1, value: 60_000 },
    { userId: 4, periodIndex: 1, value: 40_000 },
  ], 2);

  it('sorts by cumulative revenue with ties and position changes', () => {
    const rows = q4Ranking(people, ledger, 1);
    expect(rows.map((r) => [r.nickname, r.rank, r.value, r.change, r.isNew])).toEqual([
      ['Celina', 1, 60_000, 2, false],
      ['Ala', 2, 55_000, -1, false],
      ['Bartek', 3, 40_000, -1, false],
      ['Darek', 3, 40_000, null, true],
    ]);
  });

  it('excludes people who never reported', () => {
    expect(q4Ranking(people, ledger, 1).some((r) => r.nickname === 'Ewa')).toBe(false);
  });

  it('computes the gap to the next place', () => {
    const rows = q4Ranking(people, ledger, 1);
    expect(gapToNextPlace(rows, 3)).toBeNull();
    expect(gapToNextPlace(rows, 1)).toBe(5_000);
    expect(gapToNextPlace(rows, 4)).toBe(15_000);
  });
});

describe('weeklyRanking', () => {
  it('ranks by the amount earned in that week, not the total', () => {
    const ledger = buildLedger(people, [
      { userId: 1, periodIndex: 0, value: 100_000 },
      { userId: 2, periodIndex: 0, value: 5_000 },
      { userId: 1, periodIndex: 1, value: 104_000 },
      { userId: 2, periodIndex: 1, value: 25_000 },
    ], 2);
    const rows = weeklyRanking(people, ledger, 1);
    expect(rows.map((r) => [r.nickname, r.rank, r.value])).toEqual([
      ['Bartek', 1, 20_000],
      ['Ala', 2, 4_000],
    ]);
  });
});
