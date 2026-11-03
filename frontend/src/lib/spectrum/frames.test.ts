import { describe, expect, it } from 'vitest';
import { colormap, colourIndex } from './colormap';
import { FrameParser } from './frames';

function frame(kind: number, payload: Uint8Array): Uint8Array {
  const out = new Uint8Array(5 + payload.length);
  const view = new DataView(out.buffer);
  view.setUint8(0, kind);
  view.setUint32(1, payload.length, true);
  out.set(payload, 5);
  return out;
}

function spectrumPayload(centre: number, span: number, bins: number[]): Uint8Array {
  const p = new Uint8Array(30 + bins.length);
  const v = new DataView(p.buffer);
  v.setBigUint64(0, BigInt(centre), true);
  v.setUint32(8, span, true);
  v.setFloat64(12, 1.5, true);
  v.setFloat32(20, -130, true);
  v.setFloat32(24, -10, true);
  v.setUint16(28, bins.length, true);
  p.set(bins, 30);
  return p;
}

function audioPayload(rate: number, pcm: number[]): Uint8Array {
  const p = new Uint8Array(16 + 2 * pcm.length);
  const v = new DataView(p.buffer);
  v.setUint32(0, rate, true);
  v.setFloat64(4, 2.5, true);
  v.setUint32(12, pcm.length, true);
  pcm.forEach((s, i) => v.setInt16(16 + 2 * i, s, true));
  return p;
}

describe('FrameParser', () => {
  it('parses spectrum, audio and JSON frames', () => {
    const json = new TextEncoder().encode('{"end":"preempted"}');
    const data = new Uint8Array([
      ...frame(1, spectrumPayload(14_025_000, 768_000, [0, 128, 255])),
      ...frame(2, audioPayload(12_000, [-32768, 0, 32767])),
      ...frame(3, json),
    ]);
    const frames = new FrameParser().feed(data);
    expect(frames.map((f) => f.kind)).toEqual(['spectrum', 'audio', 'json']);
    const [s, a, j] = frames;
    if (s.kind !== 'spectrum' || a.kind !== 'audio' || j.kind !== 'json') throw new Error('wrong kinds');
    expect(s.row.centre).toBe(14_025_000);
    expect(s.row.span).toBe(768_000);
    expect(Array.from(s.row.bins)).toEqual([0, 128, 255]);
    expect(s.row.dbMin).toBe(-130);
    expect(a.audio.rate).toBe(12_000);
    expect(Array.from(a.audio.pcm)).toEqual([-32768, 0, 32767]);
    expect(j.data.end).toBe('preempted');
  });

  it('waits for frames split across chunks', () => {
    const data = frame(1, spectrumPayload(145_000_000, 2_000_000, [1, 2, 3, 4]));
    const parser = new FrameParser();
    expect(parser.feed(data.slice(0, 3))).toEqual([]);
    expect(parser.feed(data.slice(3, 20))).toEqual([]);
    const frames = parser.feed(data.slice(20));
    expect(frames).toHaveLength(1);
  });
});

describe('colormap', () => {
  it('has 256 colours from dark to bright', () => {
    const lut = colormap('classic');
    expect(lut.length).toBe(768);
    expect(lut[0] + lut[1] + lut[2]).toBeLessThan(lut[765] + lut[766] + lut[767]);
  });

  it('maps dB values into the display range', () => {
    expect(colourIndex(-120, -100, -40)).toBe(0);
    expect(colourIndex(-70, -100, -40)).toBe(128);
    expect(colourIndex(0, -100, -40)).toBe(255);
  });
});
