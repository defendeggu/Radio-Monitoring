const ICONS = {
  success: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="shrink-0 text-emerald-400"><path d="M20 6 9 17l-5-5"/></svg>`,
  error:   `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="shrink-0 text-red-400"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
  warning: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="shrink-0 text-amber-400"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`,
  info:    `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="shrink-0 text-cyan-400"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>`,
};

const MAX_TOASTS = 5;

export function toast(message, type = 'info', duration = 5000) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  // Remove oldest if at max
  while (container.children.length >= MAX_TOASTS) {
    container.firstChild.remove();
  }

  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `
    ${ICONS[type] || ICONS.info}
    <span class="flex-1 text-sm leading-snug">${message}</span>
    <button class="shrink-0 text-slate-500 hover:text-slate-300 transition-colors" aria-label="Dismiss">
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
    </button>
  `;

  el.querySelector('button').addEventListener('click', () => dismiss(el));
  container.appendChild(el);

  if (duration > 0) {
    setTimeout(() => dismiss(el), duration);
  }
}

function dismiss(el) {
  if (!el.parentNode) return;
  el.style.transition = 'opacity 0.2s, transform 0.2s';
  el.style.opacity = '0';
  el.style.transform = 'translateX(0.5rem)';
  setTimeout(() => el.remove(), 200);
}
