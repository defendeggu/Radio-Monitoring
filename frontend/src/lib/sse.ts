// Server-Sent Events over fetch() so the X-API-Key header can be sent
// (the browser's EventSource API cannot set headers).

import { authHeaders, buildUrl } from './api';
import type { LiveEvent } from './types';

export interface SseFrame {
  event: string;
  data: string;
}

/** Incremental parser for the text/event-stream format. */
export class SseParser {
  private buffer = '';

  feed(chunk: string): SseFrame[] {
    this.buffer += chunk.replace(/\r\n/g, '\n');
    const frames: SseFrame[] = [];
    let idx: number;
    while ((idx = this.buffer.indexOf('\n\n')) >= 0) {
      const block = this.buffer.slice(0, idx);
      this.buffer = this.buffer.slice(idx + 2);
      let event = 'message';
      const data: string[] = [];
      for (const line of block.split('\n')) {
        if (line.startsWith(':')) continue; // comment / keepalive
        const colon = line.indexOf(':');
        const field = colon >= 0 ? line.slice(0, colon) : line;
        const value = colon >= 0 ? line.slice(colon + 1).replace(/^ /, '') : '';
        if (field === 'event') event = value;
        else if (field === 'data') data.push(value);
      }
      if (data.length) frames.push({ event, data: data.join('\n') });
    }
    return frames;
  }
}

export interface LiveConnection {
  close(): void;
}

/**
 * Connect to /events and call onEvent for each event. Reconnects with backoff.
 * onState reports 'connecting' | 'open' | 'closed'.
 */
export function connectEvents(
  onEvent: (event: LiveEvent) => void,
  onState: (state: 'connecting' | 'open' | 'closed') => void = () => {},
  types?: string[],
): LiveConnection {
  let stopped = false;
  let controller: AbortController | null = null;
  let delay = 1000;

  const run = async () => {
    while (!stopped) {
      onState('connecting');
      controller = new AbortController();
      try {
        const response = await fetch(buildUrl('/events', types ? { types: types.join(',') } : undefined), {
          headers: authHeaders({ Accept: 'text/event-stream' }),
          signal: controller.signal,
        });
        if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
        onState('open');
        delay = 1000;
        const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
        const parser = new SseParser();
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          for (const frame of parser.feed(value)) {
            try {
              onEvent(JSON.parse(frame.data) as LiveEvent);
            } catch {
              /* ignore malformed frame */
            }
          }
        }
      } catch {
        /* network error or aborted */
      }
      if (stopped) break;
      onState('closed');
      await new Promise((r) => setTimeout(r, delay));
      delay = Math.min(delay * 2, 30_000);
    }
  };
  void run();

  return {
    close() {
      stopped = true;
      controller?.abort();
      onState('closed');
    },
  };
}
