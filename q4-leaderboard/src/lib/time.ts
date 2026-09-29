// All timestamps are stored in UTC. The event runs on Polish time, so every
// calendar computation and every date shown to users goes through Europe/Warsaw.
export const TZ = 'Europe/Warsaw';

const offsetFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone: TZ,
  timeZoneName: 'longOffset',
});

/** Offset of Warsaw time from UTC (in minutes) at the given instant. */
export function warsawOffsetMinutes(date: Date): number {
  const part = offsetFormatter.formatToParts(date).find((p) => p.type === 'timeZoneName')?.value ?? 'GMT';
  const m = /GMT([+-])(\d{1,2}):?(\d{2})?/.exec(part);
  if (!m) return 0;
  const sign = m[1] === '-' ? -1 : 1;
  return sign * (Number(m[2]) * 60 + Number(m[3] ?? 0));
}

/** Converts a Warsaw wall-clock time into the corresponding UTC instant (DST aware). */
export function warsawToUtc(y: number, month: number, d: number, h = 0, mi = 0, s = 0): Date {
  const naive = Date.UTC(y, month - 1, d, h, mi, s);
  let t = naive - warsawOffsetMinutes(new Date(naive)) * 60_000;
  t = naive - warsawOffsetMinutes(new Date(t)) * 60_000;
  return new Date(t);
}

const partsFormatter = new Intl.DateTimeFormat('en-GB', {
  timeZone: TZ,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

export function warsawParts(date: Date) {
  const get = (type: string) => Number(partsFormatter.formatToParts(date).find((p) => p.type === type)?.value);
  return { y: get('year'), m: get('month'), d: get('day'), h: get('hour'), mi: get('minute') };
}

const pad = (n: number) => String(n).padStart(2, '0');

/** Value for <input type="datetime-local"> in Warsaw time. */
export function toLocalInput(date: Date): string {
  const p = warsawParts(date);
  return `${p.y}-${pad(p.m)}-${pad(p.d)}T${pad(p.h)}:${pad(p.mi)}`;
}

/** Parses a datetime-local value ("2026-10-11T23:59") interpreted as Warsaw time. */
export function fromLocalInput(value: string, seconds = 0): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value.trim());
  if (!m) return null;
  return warsawToUtc(Number(m[1]), Number(m[2]), Number(m[3]), Number(m[4]), Number(m[5]), seconds);
}

/** Parses "YYYY-MM-DD". */
export function parseIsoDate(value: string): { y: number; m: number; d: number } | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (!m) return null;
  return { y: Number(m[1]), m: Number(m[2]), d: Number(m[3]) };
}

const dateTimeFmt = new Intl.DateTimeFormat('pl-PL', {
  timeZone: TZ,
  weekday: 'short',
  day: '2-digit',
  month: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
});
const dateFmt = new Intl.DateTimeFormat('pl-PL', { timeZone: TZ, day: '2-digit', month: '2-digit' });
const fullFmt = new Intl.DateTimeFormat('pl-PL', {
  timeZone: TZ,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
});

export const formatDateTime = (d: Date) => dateTimeFmt.format(d);
export const formatDate = (d: Date) => dateFmt.format(d);
export const formatFull = (d: Date) => fullFmt.format(d);
