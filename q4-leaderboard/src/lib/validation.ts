export const MAX_REVENUE = 1_000_000_000;

/**
 * Parses a PLN amount typed by a person: "12000", "12 000", "12 000,50 zł",
 * "12.000", "12,000.50". Returns whole złoty (rounded) or null when invalid.
 */
export function parseMoney(input: string): number | null {
  const s = input.replace(/zł|pln/gi, '').replace(/[\s  ]/g, '');
  if (s === '') return null;
  let normalized: string | null = null;
  if (/^\d+([.,]\d{1,2})?$/.test(s)) normalized = s.replace(',', '.');
  else if (/^\d{1,3}(\.\d{3})+(,\d{1,2})?$/.test(s)) normalized = s.replace(/\./g, '').replace(',', '.');
  else if (/^\d{1,3}(,\d{3})+(\.\d{1,2})?$/.test(s)) normalized = s.replace(/,/g, '');
  if (normalized === null) return null;
  const value = Math.round(Number(normalized));
  return Number.isFinite(value) ? value : null;
}

const plnFmt = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 0 });
export const formatPln = (n: number) => `${plnFmt.format(n)} zł`;

export const NICK_RE = /^[\p{L}\p{N}][\p{L}\p{N} _.\-]{1,22}[\p{L}\p{N}]$/u;

export function validateNickname(raw: string): string | null {
  const nick = raw.trim().replace(/\s+/g, ' ');
  if (nick.length < 3 || nick.length > 24) return 'Nick musi mieć od 3 do 24 znaków.';
  if (!NICK_RE.test(nick)) return 'Nick może zawierać litery, cyfry, spację oraz znaki _ . -';
  return null;
}

export function validateDiscord(raw: string): string | null {
  const v = raw.trim();
  if (v.length < 2 || v.length > 40) return 'Podaj swój nick z Discorda (2–40 znaków).';
  return null;
}

export function validatePassword(pw: string): string | null {
  if (pw.length < 8) return 'Hasło musi mieć co najmniej 8 znaków.';
  if (pw.length > 100) return 'Hasło jest za długie.';
  return null;
}

export function normalizeEmail(raw: string): string {
  return raw.trim().toLowerCase();
}

export function validateEmail(email: string): string | null {
  if (email.length > 255 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Podaj poprawny adres e-mail.';
  return null;
}
