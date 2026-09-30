import { describe, expect, it } from 'vitest';
import { currentPeriodState, generateDefaultPeriods, type Period } from './periods';
import { formatFull } from './time';

describe('generateDefaultPeriods (Q4 2026)', () => {
  const drafts = generateDefaultPeriods({ y: 2026, m: 10, d: 1 }, { y: 2026, m: 12, d: 31 });

  it('merges the short first week and ends on the Sunday after Q4', () => {
    expect(drafts).toHaveLength(13);
    expect(formatFull(drafts[0].startsAt)).toBe('01.10.2026, 00:00');
    expect(formatFull(drafts[0].endsAt)).toBe('11.10.2026, 23:59');
    expect(drafts[0].entryDeadline).toEqual(drafts[0].endsAt);
    expect(formatFull(drafts[1].startsAt)).toBe('12.10.2026, 00:00');
    expect(formatFull(drafts[12].startsAt)).toBe('28.12.2026, 00:00');
    expect(formatFull(drafts[12].endsAt)).toBe('03.01.2027, 23:59');
  });

  it('handles the DST change at the end of October', () => {
    // Week 3 (19–25.10) ends on the day clocks go back: 23:59:59 CET = 22:59:59 UTC.
    expect(drafts[2].endsAt.toISOString()).toBe('2026-10-25T22:59:59.000Z');
    expect(drafts[1].endsAt.toISOString()).toBe('2026-10-18T21:59:59.000Z');
  });
});

describe('currentPeriodState', () => {
  const periods: Period[] = generateDefaultPeriods({ y: 2026, m: 10, d: 1 }, { y: 2026, m: 12, d: 31 }).map((p, i) => ({
    ...p,
    id: i + 1,
    isLocked: false,
  }));

  it('detects before / running / finished', () => {
    expect(currentPeriodState(periods, new Date('2026-09-30T12:00:00Z')).phase).toBe('before');
    expect(currentPeriodState(periods, new Date('2026-10-12T10:00:00Z'))).toEqual({ phase: 'running', index: 1 });
    expect(currentPeriodState(periods, new Date('2027-01-05T10:00:00Z'))).toEqual({ phase: 'finished', index: 12 });
  });
});
