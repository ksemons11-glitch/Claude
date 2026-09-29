import { describe, expect, it } from 'vitest';
import { formatPln, parseMoney, validateNickname } from './validation';

describe('parseMoney', () => {
  it.each([
    ['12000', 12000],
    ['12 000', 12000],
    ['12 000 zł', 12000],
    ['12 000,50', 12001],
    ['12000.49', 12000],
    ['12.000', 12000],
    ['1.234.567,89', 1234568],
    ['12,000', 12000],
    ['0', 0],
  ])('%s → %d', (input, expected) => {
    expect(parseMoney(input)).toBe(expected);
  });

  it.each(['', 'abc', '-500', '12,00,0', '1e5'])('rejects %s', (input) => {
    expect(parseMoney(input)).toBeNull();
  });
});

describe('validateNickname', () => {
  it('accepts Polish letters and spaces', () => {
    expect(validateNickname('Żółta Łódź_24')).toBeNull();
  });
  it('rejects too short or odd characters', () => {
    expect(validateNickname('ab')).not.toBeNull();
    expect(validateNickname('<script>')).not.toBeNull();
  });
});

describe('formatPln', () => {
  it('uses Polish grouping', () => {
    expect(formatPln(1234567).replace(/\s/g, ' ')).toBe('1 234 567 zł');
  });
});
