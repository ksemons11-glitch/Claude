import { warsawToUtc } from './time';

export type Period = {
  id: number;
  weekNumber: number;
  startsAt: Date;
  endsAt: Date;
  entryDeadline: Date;
  isLocked: boolean;
};

export type PeriodDraft = Omit<Period, 'id' | 'isLocked'>;

const DAY = 86_400_000;

function calendarDay(y: number, m: number, d: number) {
  return Date.UTC(y, m - 1, d);
}

function split(dayMs: number) {
  const dt = new Date(dayMs);
  return { y: dt.getUTCFullYear(), m: dt.getUTCMonth() + 1, d: dt.getUTCDate() };
}

/**
 * Default reporting weeks: Monday–Sunday. Results can be entered and updated until the
 * week closes on Sunday 23:59:59 — sales keep coming in all week, so there is no earlier
 * deadline. A short first week (Q4 rarely starts on a Monday) is merged into the following
 * full week, and the last week runs until the Sunday after Q4 ends so the final results
 * can still be reported.
 */
export function generateDefaultPeriods(start: { y: number; m: number; d: number }, end: { y: number; m: number; d: number }): PeriodDraft[] {
  const startDay = calendarDay(start.y, start.m, start.d);
  const endDay = calendarDay(end.y, end.m, end.d);
  const periods: PeriodDraft[] = [];

  // First Sunday at least 6 days after the start date.
  let periodEnd = startDay + 6 * DAY;
  while (new Date(periodEnd).getUTCDay() !== 0) periodEnd += DAY;

  let periodStart = startDay;
  let week = 1;
  while (periodStart <= endDay) {
    const s = split(periodStart);
    const e = split(periodEnd);
    periods.push({
      weekNumber: week,
      startsAt: warsawToUtc(s.y, s.m, s.d, 0, 0, 0),
      endsAt: warsawToUtc(e.y, e.m, e.d, 23, 59, 59),
      entryDeadline: warsawToUtc(e.y, e.m, e.d, 23, 59, 59), // same as endsAt
    });
    periodStart = periodEnd + DAY;
    periodEnd = periodStart + 6 * DAY;
    week += 1;
  }
  return periods;
}

export type PeriodState =
  | { phase: 'before'; index: -1 }
  | { phase: 'running'; index: number }
  | { phase: 'finished'; index: number };

/** Locates "now" among ordered periods. `index` is the period entries are currently assigned to. */
export function currentPeriodState(periods: Period[], now: Date): PeriodState {
  if (periods.length === 0 || now < periods[0].startsAt) return { phase: 'before', index: -1 };
  let idx = 0;
  for (let i = 0; i < periods.length; i++) if (periods[i].startsAt <= now) idx = i;
  const last = periods.length - 1;
  if (idx === last && now > periods[last].endsAt) return { phase: 'finished', index: last };
  return { phase: 'running', index: idx };
}

/** Whether participants may still change the entry of this period. */
export function isPeriodOpen(period: Period, now: Date): boolean {
  return !period.isLocked && now >= period.startsAt && now <= period.endsAt;
}
