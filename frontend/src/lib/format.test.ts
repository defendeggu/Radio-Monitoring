import { describe, expect, it } from 'vitest';
import { bytes, duration, mhz, parseFrequency, relative } from './format';

describe('parseFrequency', () => {
  it.each([
    ['144.8', 144_800_000],
    ['144,800', 144_800_000],
    ['433.92M', 433_920_000],
    ['1090 MHz', 1_090_000_000],
    ['1.09g', 1_090_000_000],
    ['446006250', 446_006_250],
    ['7100k', 7_100_000],
  ])('%s → %d Hz', (input, hz) => expect(parseFrequency(input)).toBe(hz));

  it.each(['', 'abc', '1.2.3', '-5', '144.8 kHz?'])('rejects %j', (input) =>
    expect(parseFrequency(input)).toBeNull(),
  );
});

describe('formatters', () => {
  it('mhz', () => {
    expect(mhz(144_800_000)).toBe('144.8000 MHz');
    expect(mhz(null)).toBe('—');
  });
  it('duration', () => {
    expect(duration(5)).toBe('5s');
    expect(duration(125)).toBe('2m 05s');
    expect(duration(3725)).toBe('1h 02m');
  });
  it('bytes', () => {
    expect(bytes(512)).toBe('512 B');
    expect(bytes(1536)).toBe('1.5 KB');
  });
  it('relative', () => {
    const now = Date.parse('2026-10-16T10:00:00Z');
    expect(relative('2026-10-16T09:59:30Z', now)).toBe('gerade eben');
    expect(relative('2026-10-16T09:58:00Z', now)).toBe('vor 2m 00s');
  });
});
