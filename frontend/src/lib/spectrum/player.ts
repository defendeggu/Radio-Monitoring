// Plays the live audio blocks of a waterfall or CW session (see public/pcm-worklet.js).

export class LivePlayer {
  private context: AudioContext | null = null;
  private node: AudioWorkletNode | null = null;
  private gain: GainNode | null = null;
  level = 0; // peak of the last block, 0..1 (for a meter)

  /** Must be called from a user gesture (browsers block audio otherwise). */
  async start(volume: number): Promise<void> {
    if (this.context) return;
    const context = new AudioContext();
    await context.audioWorklet.addModule('/pcm-worklet.js');
    const node = new AudioWorkletNode(context, 'pcm-player', { outputChannelCount: [2] });
    const gain = context.createGain();
    gain.gain.value = volume;
    node.connect(gain).connect(context.destination);
    this.context = context;
    this.node = node;
    this.gain = gain;
  }

  get running(): boolean {
    return this.context !== null;
  }

  setVolume(volume: number): void {
    if (this.gain) this.gain.gain.value = volume;
  }

  push(pcm: Int16Array, rate: number): void {
    if (!this.node) return;
    const samples = new Float32Array(pcm.length);
    let peak = 0;
    for (let i = 0; i < pcm.length; i++) {
      samples[i] = pcm[i] / 32768;
      const a = Math.abs(samples[i]);
      if (a > peak) peak = a;
    }
    this.level = peak;
    this.node.port.postMessage({ samples, rate }, [samples.buffer]);
  }

  /** Drop buffered audio (after retuning, so the old frequency is not heard). */
  reset(): void {
    this.node?.port.postMessage('reset');
  }

  async stop(): Promise<void> {
    const context = this.context;
    this.context = this.node = this.gain = null;
    this.level = 0;
    await context?.close();
  }
}
