import { describe, expect, it } from 'vitest';
import { SseParser } from './sse';

describe('SseParser', () => {
  it('parses events split across chunks', () => {
    const p = new SseParser();
    expect(p.feed('retry: 3000\n\n')).toEqual([]);
    expect(p.feed('event: aprs\ndata: {"a"')).toEqual([]);
    expect(p.feed(':1}\n\n: keepalive\n\nevent: alert\ndata: x\n\n')).toEqual([
      { event: 'aprs', data: '{"a":1}' },
      { event: 'alert', data: 'x' },
    ]);
  });

  it('joins multi-line data and handles CRLF', () => {
    const p = new SseParser();
    expect(p.feed('data: line1\r\ndata: line2\r\n\r\n')).toEqual([
      { event: 'message', data: 'line1\nline2' },
    ]);
  });
});
