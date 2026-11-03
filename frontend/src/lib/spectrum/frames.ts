// Binary frames of GET /spectrum/<id>/stream (see radiomoni/decoders/spectrum.py).
//
//   u8 type, u32 length (little endian), payload
//   1 spectrum: u64 centre, u32 span, f64 time, f32 dB min, f32 dB max, u16 n, n × u8
//   2 audio:    u32 rate, f64 time, u32 n, n × i16
//   3 JSON

import { authHeaders, buildUrl } from '../api';

export interface SpectrumRow {
  centre: number;
  span: number;
  time: number;
  dbMin: number;
  dbMax: number;
  bins: Uint8Array;
}

export interface AudioBlock {
  rate: number;
  time: number;
  pcm: Int16Array;
}

export interface SpectrumState {
  session_id: string;
  mode: string;
  centre: number;
  span: number;
  channel: number;
  modulation: string;
  cw_bandwidth?: number;
  squelch_db?: number | null;
  sdr_type?: string;
  fft_size?: number;
  tunable: boolean;
}

export type Frame =
  | { kind: 'spectrum'; row: SpectrumRow }
  | { kind: 'audio'; audio: AudioBlock }
  | { kind: 'json'; data: { state?: SpectrumState; end?: string; reason?: string | null } };

const HEADER = 5;

/** Incremental parser: feed() any slice of the byte stream, get the complete frames. */
export class FrameParser {
  private buffer = new Uint8Array(0);

  feed(chunk: Uint8Array): Frame[] {
    const merged = new Uint8Array(this.buffer.length + chunk.length);
    merged.set(this.buffer);
    merged.set(chunk, this.buffer.length);
    const frames: Frame[] = [];
    let pos = 0;
    const view = new DataView(merged.buffer);
    while (pos + HEADER <= merged.length) {
      const kind = view.getUint8(pos);
      const length = view.getUint32(pos + 1, true);
      if (pos + HEADER + length > merged.length) break;
      const start = pos + HEADER;
      const frame = parsePayload(kind, merged, view, start, length);
      if (frame) frames.push(frame);
      pos = start + length;
    }
    this.buffer = merged.slice(pos);
    return frames;
  }
}

function parsePayload(
  kind: number,
  bytes: Uint8Array,
  view: DataView,
  start: number,
  length: number,
): Frame | null {
  if (kind === 1) {
    const n = view.getUint16(start + 28, true);
    return {
      kind: 'spectrum',
      row: {
        centre: Number(view.getBigUint64(start, true)),
        span: view.getUint32(start + 8, true),
        time: view.getFloat64(start + 12, true),
        dbMin: view.getFloat32(start + 20, true),
        dbMax: view.getFloat32(start + 24, true),
        bins: bytes.slice(start + 30, start + 30 + n),
      },
    };
  }
  if (kind === 2) {
    const n = view.getUint32(start + 12, true);
    const pcm = new Int16Array(n);
    for (let i = 0; i < n; i++) pcm[i] = view.getInt16(start + 16 + 2 * i, true);
    return {
      kind: 'audio',
      audio: { rate: view.getUint32(start, true), time: view.getFloat64(start + 4, true), pcm },
    };
  }
  if (kind === 3) {
    try {
      return { kind: 'json', data: JSON.parse(new TextDecoder().decode(bytes.slice(start, start + length))) };
    } catch {
      return null;
    }
  }
  return null;
}

export interface SpectrumConnection {
  close(): void;
}

/**
 * Open the binary stream of a session; reconnects while the session runs.
 * Ends (without reconnect) when the server sends an "end" frame.
 */
export function connectSpectrum(
  sessionId: string,
  listen: boolean,
  onFrame: (frame: Frame) => void,
  onState: (state: 'connecting' | 'open' | 'closed') => void = () => {},
): SpectrumConnection {
  let stopped = false;
  let controller: AbortController | null = null;
  let delay = 1000;

  const run = async () => {
    while (!stopped) {
      onState('connecting');
      controller = new AbortController();
      let ended = false;
      try {
        const response = await fetch(
          buildUrl(`/spectrum/${sessionId}/stream`, listen ? { audio: 1 } : undefined),
          { headers: authHeaders(), signal: controller.signal },
        );
        if (response.status === 404) break;
        if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
        onState('open');
        delay = 1000;
        const reader = response.body.getReader();
        const parser = new FrameParser();
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          for (const frame of parser.feed(value)) {
            if (frame.kind === 'json' && frame.data.end) ended = true;
            onFrame(frame);
          }
          if (ended) break;
        }
      } catch {
        /* network error or abort: retry below */
      }
      if (ended || stopped) break;
      onState('closed');
      await new Promise((r) => setTimeout(r, delay));
      delay = Math.min(delay * 2, 15_000);
    }
    onState('closed');
  };
  void run();

  return {
    close() {
      stopped = true;
      controller?.abort();
    },
  };
}
