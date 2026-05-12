import { getCaptureStatus } from './api.js';
import { toast } from './toast.js';

const STATUS_LABELS = {
  queued:     'Queued — waiting for SDR...',
  capturing:  'Capturing...',
  processing: 'Processing...',
};

/**
 * Poll /capture-status/<id> until terminal state, then call onDone(result) or onError(msg).
 * Returns a cancel function.
 *
 * progressConfig (optional):
 *   { barEl, labelEl, duration }
 *   Used to animate a progress bar based on estimated state progression.
 */
export function pollCaptureStatus({ captureId, onDone, onError, onStatus, progressConfig }) {
  const POLL_INTERVAL = 2000;
  let errorCount = 0;
  let captureStartTime = null;
  let intervalId = null;

  function setProgress(pct, label, pulse = false) {
    if (!progressConfig) return;
    const { barEl, labelEl } = progressConfig;
    if (barEl) {
      barEl.style.width = pct + '%';
      if (pulse) {
        barEl.classList.add('animate-pulse-bar');
      } else {
        barEl.classList.remove('animate-pulse-bar');
      }
    }
    if (labelEl && label) labelEl.textContent = label;
  }

  intervalId = setInterval(async () => {
    try {
      const session = await getCaptureStatus(captureId);
      errorCount = 0;

      const label = STATUS_LABELS[session.status];
      if (label && onStatus) onStatus(label);

      // Progress estimation
      if (session.status === 'queued') {
        setProgress(5, 'Queued...', true);
      } else if (session.status === 'capturing') {
        if (!captureStartTime) captureStartTime = Date.now();
        const elapsed = (Date.now() - captureStartTime) / 1000;
        const duration = progressConfig?.duration || 30;
        const pct = Math.min(5 + (elapsed / duration) * 65, 70);
        setProgress(pct, 'Capturing...');
      } else if (session.status === 'processing') {
        setProgress(85, 'Processing...', true);
      }

      if (session.status === 'completed') {
        clearInterval(intervalId);
        setProgress(100, 'Done!');
        setTimeout(() => {
          if (progressConfig?.containerEl) {
            progressConfig.containerEl.classList.add('hidden');
          }
        }, 1200);
        onDone(session.result);
      } else if (session.status === 'failed') {
        clearInterval(intervalId);
        setProgress(0, '');
        if (progressConfig?.containerEl) progressConfig.containerEl.classList.add('hidden');
        onError(session.error || 'Unknown error');
      }
    } catch (err) {
      errorCount++;
      if (errorCount >= 3) {
        clearInterval(intervalId);
        onError('Lost contact with server');
      }
    }
  }, POLL_INTERVAL);

  return () => clearInterval(intervalId);
}
