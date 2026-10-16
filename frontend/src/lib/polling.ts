import { api } from './api';
import type { CaptureJob } from './types';

/** Poll a capture job until it completes or fails. Returns the final job. */
export async function waitForCapture(
  captureId: string,
  onUpdate: (job: CaptureJob) => void,
  signal?: AbortSignal,
  interval = 1500,
): Promise<CaptureJob> {
  let errors = 0;
  for (;;) {
    if (signal?.aborted) throw new DOMException('aborted', 'AbortError');
    try {
      const job = await api.get<CaptureJob>(`/capture-status/${captureId}`);
      errors = 0;
      onUpdate(job);
      if (job.status === 'completed' || job.status === 'failed') return job;
    } catch (e) {
      if (++errors >= 5) throw e;
    }
    await new Promise((r) => setTimeout(r, interval));
  }
}
