// Contest skimmer: types of /skimmer/spots and /contest/status, tags and colours of a spot.

export interface SkimmerSpot {
  callsign: string;
  frequency: number;
  khz: number;
  band: string | null;
  mode: string;
  snr_db: number;
  wpm: number | null;
  type: string;
  skimmers: string[];
  skimmer_count: number;
  first_seen: number;
  last_seen: number;
  age_seconds: number;
  source: 'skimmer' | 'rbn';
  sources?: string[];
  country: string | null;
  continent: string | null;
  cq_zone: number | null;
  itu_zone: number | null;
  wpx: string | null;
  in_scp: boolean | null;
  portable: boolean;
  swiss: boolean;
  dupe: boolean;
  new_mults: { type: string; value: string; label: string }[];
  rank: number | null;
  rare: boolean;
  priority: 'high' | 'normal' | 'dupe';
  in_contest: boolean;
  text?: string; // SSB: what Whisper heard
  audio_file?: string; // SSB: the segment that gave the spot
}

/** Bands with an SSB (phone) segment for the skimmer (radiomoni/skimmer/session.py SSB_SEGMENTS). */
export const SSB_BAND_IDS = [
  '160m',
  '80m',
  '40m',
  '20m',
  '17m',
  '15m',
  '12m',
  '10m',
  '6m',
  '2m',
  '70cm',
  '23cm',
];

export interface ContestRules {
  id: string;
  name: string;
  modes: string[];
  bands: string[];
  dupe: string;
  multipliers: { type: string; per: string }[];
  highlight: string[];
  url: string;
  when: string;
  notes: string;
  assistance: string;
}

export interface Tag {
  label: string;
  tone: 'red' | 'amber' | 'slate' | 'sky' | 'violet';
  title?: string;
}

/** Badges for a spot: new multipliers, rarity, dupe, portable, Swiss station, unknown to MASTER.SCP. */
export function tags(spot: SkimmerSpot, highlight: string[] = []): Tag[] {
  const out: Tag[] = [];
  for (const m of spot.new_mults ?? []) out.push({ label: 'MULT', tone: 'red', title: m.label });
  if (spot.rare) out.push({ label: `RARE #${spot.rank}`, tone: 'amber' });
  if (spot.dupe) out.push({ label: 'DUPE', tone: 'slate' });
  if (spot.portable && highlight.includes('portable')) out.push({ label: '/P', tone: 'sky' });
  if (spot.swiss && highlight.includes('swiss')) out.push({ label: 'HB', tone: 'violet' });
  if (spot.in_scp === false) out.push({ label: '?SCP', tone: 'slate', title: 'not in MASTER.SCP' });
  // one MULT badge is enough, the title lists all of them
  const mults = out.filter((t) => t.label === 'MULT');
  if (mults.length > 1) {
    mults[0].title = mults.map((t) => t.title).join(', ');
    return out.filter((t) => t.label !== 'MULT' || t === mults[0]);
  }
  return out;
}

/** Waterfall marker kind: new multiplier / rare = mult (red), dupe (grey), otherwise spot (amber). */
export function markerKind(spot: SkimmerSpot): 'mult' | 'dupe' | 'spot' {
  if (spot.priority === 'high') return 'mult';
  if (spot.priority === 'dupe') return 'dupe';
  return 'spot';
}

export const TONES: Record<Tag['tone'], string> = {
  red: 'bg-red-100 text-red-700 dark:bg-red-950/60 dark:text-red-300',
  amber: 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300',
  slate: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
  sky: 'bg-sky-100 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300',
  violet: 'bg-violet-100 text-violet-700 dark:bg-violet-950/60 dark:text-violet-300',
};
