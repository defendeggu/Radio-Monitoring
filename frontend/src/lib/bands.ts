// Quick band selection for the waterfall and the CW page.
// CW segments of the HF bands follow the IARU Region 1 HF band plan.

export interface Band {
  id: string;
  label: string;
  start: number; // Hz
  end: number; // Hz
  cw?: boolean; // CW segment of an amateur HF band
}

const MHZ = 1e6;

export const CW_BANDS: Band[] = [
  { id: '160m', label: '160 m', start: 1.81 * MHZ, end: 1.838 * MHZ, cw: true },
  { id: '80m', label: '80 m', start: 3.5 * MHZ, end: 3.57 * MHZ, cw: true },
  { id: '40m', label: '40 m', start: 7.0 * MHZ, end: 7.04 * MHZ, cw: true },
  { id: '30m', label: '30 m', start: 10.1 * MHZ, end: 10.13 * MHZ, cw: true },
  { id: '20m', label: '20 m', start: 14.0 * MHZ, end: 14.07 * MHZ, cw: true },
  { id: '17m', label: '17 m', start: 18.068 * MHZ, end: 18.095 * MHZ, cw: true },
  { id: '15m', label: '15 m', start: 21.0 * MHZ, end: 21.07 * MHZ, cw: true },
  { id: '12m', label: '12 m', start: 24.89 * MHZ, end: 24.915 * MHZ, cw: true },
  { id: '10m', label: '10 m', start: 28.0 * MHZ, end: 28.07 * MHZ, cw: true },
];

export const VHF_BANDS: Band[] = [
  { id: 'air', label: 'Flugfunk', start: 118 * MHZ, end: 137 * MHZ },
  { id: '2m', label: '2 m', start: 144 * MHZ, end: 146 * MHZ },
  { id: '70cm', label: '70 cm', start: 430 * MHZ, end: 440 * MHZ },
  { id: 'pmr', label: 'PMR446', start: 446 * MHZ, end: 446.2 * MHZ },
];

/** NCDXF/IARU International Beacon Project: CW beacons with a fixed schedule (good test signals). */
export const NCDXF_BEACONS = [14.1, 18.11, 21.15, 24.93, 28.2].map((f) => f * MHZ);

export function centreOf(band: Band): number {
  return Math.round((band.start + band.end) / 2);
}

/** HF amateur band (CW segment) containing `hz`, with a 10 kHz margin. */
export function cwBandOf(hz: number): Band | undefined {
  return CW_BANDS.find((b) => hz >= b.start - 10_000 && hz <= b.end + 50_000);
}
