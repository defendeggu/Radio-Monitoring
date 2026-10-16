<script lang="ts">
  import { Copy } from '@lucide/svelte';
  import { API_BASE, api } from '../lib/api';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import { toasts } from '../lib/stores.svelte';

  interface Operation {
    summary: string;
    tags: string[];
    description?: string;
    deprecated?: boolean;
    parameters?: {
      name: string;
      in: string;
      required: boolean;
      schema: { type?: string; anyOf?: unknown[] };
    }[];
    requestBody?: { content: { 'application/json': { schema: { $ref: string } } } };
  }
  interface SchemaProp {
    type?: string;
    description?: string;
    default?: unknown;
    enum?: unknown[];
    minimum?: number;
    maximum?: number;
    anyOf?: SchemaProp[];
    $ref?: string;
  }
  interface Doc {
    info: { title: string; version: string; description: string };
    paths: Record<string, Record<string, Operation>>;
    components: {
      schemas: Record<
        string,
        { properties?: Record<string, SchemaProp>; required?: string[]; enum?: unknown[] }
      >;
    };
  }

  let doc = $state<Doc | null>(null);
  let filter = $state('');

  $effect(() => {
    api
      .get<Doc>('/openapi.json')
      .then((d) => (doc = d))
      .catch(toasts.error.bind(toasts));
  });

  const ops = $derived.by(() => {
    if (!doc) return [] as { tag: string; method: string; path: string; op: Operation }[];
    const list = [];
    for (const [path, methods] of Object.entries(doc.paths)) {
      for (const [method, op] of Object.entries(methods))
        list.push({ tag: op.tags[0] ?? 'Other', method, path, op });
    }
    const f = filter.toLowerCase();
    return list.filter((o) => !f || o.path.includes(f) || o.op.summary.toLowerCase().includes(f));
  });
  const tags = $derived([...new Set(ops.map((o) => o.tag))]);

  function schemaOf(op: Operation) {
    const ref = op.requestBody?.content['application/json'].schema.$ref;
    return ref ? doc?.components.schemas[ref.split('/').pop()!] : undefined;
  }

  function typeText(p: SchemaProp): string {
    if (p.enum) return p.enum.map((e) => JSON.stringify(e)).join(' | ');
    if (p.anyOf) return p.anyOf.map(typeText).join(' | ');
    if (p.$ref) return p.$ref.split('/').pop()!;
    const range =
      p.minimum !== undefined || p.maximum !== undefined ? ` (${p.minimum ?? ''}…${p.maximum ?? ''})` : '';
    return (p.type ?? 'any') + range;
  }

  function curl(method: string, path: string): string {
    const origin = window.location.origin;
    const m = method.toUpperCase();
    return `curl -X ${m} -H "X-API-Key: $API_KEY"${m === 'POST' || m === 'PUT' ? ` -H "Content-Type: application/json" -d '{}'` : ''} ${origin}${API_BASE}${path}`;
  }

  const methodColor: Record<string, string> = {
    get: 'bg-sky-500/15 text-sky-700 dark:text-sky-300',
    post: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
    put: 'bg-amber-500/15 text-amber-700 dark:text-amber-300',
    delete: 'bg-red-500/15 text-red-700 dark:text-red-300',
  };
</script>

<PageHeader title="API" description="REST-API von RadioMoni — generiert aus den Validierungs-Schemas">
  {#snippet actions()}
    <a class="btn-secondary" href="{API_BASE}/openapi.json" target="_blank" rel="noopener">openapi.json</a>
  {/snippet}
</PageHeader>

{#if doc}
  <p class="mb-4 text-sm text-slate-500">{doc.info.title} {doc.info.version} — {doc.info.description}</p>
  <input class="input mb-6" bind:value={filter} placeholder="Endpunkte filtern…" aria-label="Filter" />
  {#each tags as tag (tag)}
    <section class="mb-6">
      <h2 class="mb-2 text-sm font-semibold">{tag}</h2>
      <div class="space-y-2">
        {#each ops.filter((o) => o.tag === tag) as o (o.method + o.path)}
          {@const schema = schemaOf(o.op)}
          <details class="card !p-3">
            <summary class="flex cursor-pointer flex-wrap items-center gap-3">
              <span
                class="w-16 rounded px-2 py-0.5 text-center font-mono text-xs uppercase {methodColor[
                  o.method
                ] ?? ''}">{o.method}</span
              >
              <code class="text-sm {o.op.deprecated ? 'line-through opacity-60' : ''}">{o.path}</code>
              <span class="text-sm text-slate-500">{o.op.summary}</span>
            </summary>
            <div class="mt-3 space-y-3 text-sm">
              {#if o.op.description}<p class="text-slate-500">{o.op.description}</p>{/if}
              {#if o.op.parameters?.length}
                <table class="table">
                  <thead><tr><th>Parameter</th><th>in</th><th>Typ</th></tr></thead>
                  <tbody>
                    {#each o.op.parameters as p (p.in + p.name)}
                      <tr
                        ><td class="font-mono">{p.name}{p.required ? ' *' : ''}</td><td>{p.in}</td><td
                          class="font-mono text-xs">{typeText(p.schema as SchemaProp)}</td
                        ></tr
                      >
                    {/each}
                  </tbody>
                </table>
              {/if}
              {#if schema?.properties}
                <table class="table">
                  <thead><tr><th>Body-Feld</th><th>Typ</th><th>Standard</th></tr></thead>
                  <tbody>
                    {#each Object.entries(schema.properties) as [field, prop] (field)}
                      <tr>
                        <td class="font-mono">{field}{schema.required?.includes(field) ? ' *' : ''}</td>
                        <td class="font-mono text-xs"
                          >{typeText(prop)}{#if prop.description}<div class="font-sans text-slate-500">
                              {prop.description}
                            </div>{/if}</td
                        >
                        <td class="font-mono text-xs"
                          >{prop.default !== undefined ? JSON.stringify(prop.default) : ''}</td
                        >
                      </tr>
                    {/each}
                  </tbody>
                </table>
              {/if}
              <div class="flex items-center gap-2">
                <code
                  class="flex-1 overflow-x-auto rounded bg-slate-100 p-2 text-xs whitespace-nowrap dark:bg-slate-800"
                  >{curl(o.method, o.path)}</code
                >
                <button
                  class="btn-secondary !px-2"
                  onclick={() => navigator.clipboard?.writeText(curl(o.method, o.path))}
                  aria-label="Kopieren"><Copy size={14} /></button
                >
              </div>
            </div>
          </details>
        {/each}
      </div>
    </section>
  {/each}
{:else}
  <p class="text-sm text-slate-500">Lade API-Beschreibung…</p>
{/if}
