import { describe, expect, it } from 'vitest';
import { markerKind, tags, type SkimmerSpot } from './contest';

const base: SkimmerSpot = {
  callsign: 'DL1ABC',
  frequency: 14025000,
  khz: 14025,
  band: '20m',
  mode: 'CW',
  snr_db: 18,
  wpm: 24,
  type: 'CQ',
  skimmers: ['HB9XYZ-#'],
  skimmer_count: 1,
  first_seen: 0,
  last_seen: 0,
  age_seconds: 5,
  source: 'skimmer',
  country: 'Fed. Rep. of Germany',
  continent: 'EU',
  cq_zone: 14,
  itu_zone: 28,
  wpx: 'DL1',
  in_scp: true,
  portable: false,
  swiss: false,
  dupe: false,
  new_mults: [],
  rank: 150,
  rare: false,
  priority: 'normal',
  in_contest: true,
};

describe('contest spot tags', () => {
  it('has no tags for an ordinary new station', () => {
    expect(tags(base)).toEqual([]);
    expect(markerKind(base)).toBe('spot');
  });

  it('merges several new multipliers into one badge', () => {
    const spot = {
      ...base,
      priority: 'high' as const,
      new_mults: [
        { type: 'cq_zone', value: '14', label: 'CQ zone 14' },
        { type: 'dxcc', value: '230', label: 'DXCC Fed. Rep. of Germany' },
      ],
    };
    const result = tags(spot);
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({ label: 'MULT', title: 'CQ zone 14, DXCC Fed. Rep. of Germany' });
    expect(markerKind(spot)).toBe('mult');
  });

  it('marks rare, dupe, portable, Swiss and unknown stations', () => {
    const spot = { ...base, rare: true, rank: 3, dupe: true, portable: true, swiss: true, in_scp: false };
    expect(tags(spot, ['portable', 'swiss']).map((t) => t.label)).toEqual([
      'RARE #3',
      'DUPE',
      '/P',
      'HB',
      '?SCP',
    ]);
    expect(tags(spot).map((t) => t.label)).not.toContain('/P'); // only when the contest highlights it
    expect(markerKind({ ...base, priority: 'dupe' })).toBe('dupe');
  });
});
