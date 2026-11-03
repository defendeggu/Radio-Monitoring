/* global AudioWorkletProcessor, registerProcessor, sampleRate */
// Live audio of the waterfall: PCM blocks arrive over the port (Float32Array at
// their own rate), are resampled linearly to the context rate and played from a
// jitter buffer. On underrun it plays silence, on overrun it drops the oldest audio.

class PcmPlayer extends AudioWorkletProcessor {
  constructor() {
    super();
    this.capacity = sampleRate * 4;
    this.ring = new Float32Array(this.capacity);
    this.read = 0;
    this.size = 0;
    this.target = sampleRate * 0.3; // start playing at 300 ms buffered
    this.playing = false;
    this.port.onmessage = (event) => {
      if (event.data === 'reset') {
        this.read = this.size = 0;
        this.playing = false;
        return;
      }
      this.push(event.data.samples, event.data.rate);
    };
  }

  push(samples, rate) {
    const ratio = rate / sampleRate;
    const n = Math.floor(samples.length / ratio);
    for (let i = 0; i < n; i++) {
      const x = i * ratio;
      const j = Math.floor(x);
      const a = samples[j];
      const b = j + 1 < samples.length ? samples[j + 1] : a;
      if (this.size === this.capacity) {
        this.read = (this.read + 1) % this.capacity;
        this.size--;
      }
      this.ring[(this.read + this.size) % this.capacity] = a + (b - a) * (x - j);
      this.size++;
    }
    if (this.size > sampleRate * 1.5) {
      const drop = this.size - this.target; // too much latency: skip ahead
      this.read = (this.read + drop) % this.capacity;
      this.size -= drop;
    }
  }

  process(_inputs, outputs) {
    const out = outputs[0][0];
    if (!this.playing && this.size >= this.target) this.playing = true;
    for (let i = 0; i < out.length; i++) {
      if (this.playing && this.size > 0) {
        out[i] = this.ring[this.read];
        this.read = (this.read + 1) % this.capacity;
        this.size--;
      } else {
        out[i] = 0;
        this.playing = false;
      }
    }
    for (let c = 1; c < outputs[0].length; c++) outputs[0][c].set(out);
    return true;
  }
}

registerProcessor('pcm-player', PcmPlayer);
