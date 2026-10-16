// Minimal hash router: #/aprs, #/voice ...

class Router {
  path = $state(current().path);
  params = $state<URLSearchParams>(current().params);

  constructor() {
    if (typeof window !== 'undefined') {
      window.addEventListener('hashchange', () => {
        const c = current();
        this.path = c.path;
        this.params = c.params;
      });
    }
  }

  go(path: string, params?: Record<string, string | number>) {
    const qs = params
      ? '?' + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]))
      : '';
    window.location.hash = `#/${path}${qs}`;
  }
}

function current(): { path: string; params: URLSearchParams } {
  if (typeof window === 'undefined') return { path: 'dashboard', params: new URLSearchParams() };
  const [path, query] = window.location.hash.replace(/^#\/?/, '').split('?');
  return { path: path || 'dashboard', params: new URLSearchParams(query ?? '') };
}

export const router = new Router();
