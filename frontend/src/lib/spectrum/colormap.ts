// Colour tables for the waterfall: 256 RGB entries, index 0 = weakest.

export type ColormapName = 'classic' | 'grey';

const STOPS: Record<ColormapName, [number, [number, number, number]][]> = {
  classic: [
    [0, [0, 0, 20]],
    [0.25, [0, 30, 160]],
    [0.5, [0, 190, 220]],
    [0.7, [240, 230, 40]],
    [0.88, [250, 70, 20]],
    [1, [255, 255, 255]],
  ],
  grey: [
    [0, [8, 8, 8]],
    [1, [250, 250, 250]],
  ],
};

/** Flat RGB table (3 × 256 bytes) built by linear interpolation of the stops. */
export function colormap(name: ColormapName): Uint8ClampedArray {
  const stops = STOPS[name];
  const lut = new Uint8ClampedArray(256 * 3);
  for (let i = 0; i < 256; i++) {
    const x = i / 255;
    let k = 0;
    while (k < stops.length - 2 && x > stops[k + 1][0]) k++;
    const [x0, c0] = stops[k];
    const [x1, c1] = stops[k + 1];
    const f = x1 > x0 ? (x - x0) / (x1 - x0) : 0;
    for (let c = 0; c < 3; c++) lut[i * 3 + c] = Math.round(c0[c] + f * (c1[c] - c0[c]));
  }
  return lut;
}

/** Map a dB value to a colour index 0..255 for the display range lo..hi. */
export function colourIndex(db: number, lo: number, hi: number): number {
  const v = Math.round(((db - lo) / Math.max(1e-6, hi - lo)) * 255);
  return v < 0 ? 0 : v > 255 ? 255 : v;
}
