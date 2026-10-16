<script lang="ts" module>
  export interface MapPoint {
    id: string;
    lat: number;
    lon: number;
    label: string;
    detail?: string;
    color?: string;
  }
</script>

<script lang="ts">
  import L from 'leaflet';

  let { points, height = '420px' }: { points: MapPoint[]; height?: string } = $props();

  let el: HTMLDivElement;
  let map: L.Map | null = null;
  let layer: L.LayerGroup | null = null;
  let fitted = false;

  $effect(() => {
    map = L.map(el, { zoomControl: true, attributionControl: true }).setView([46.8, 8.2], 7);
    // The OSM tile policy blocks requests without a Referer, and nginx sends
    // "Referrer-Policy: no-referrer" for the whole app. Send only the origin
    // (no path or query) with the tile requests.
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; OpenStreetMap contributors',
      referrerPolicy: 'strict-origin-when-cross-origin',
    }).addTo(map);
    layer = L.layerGroup().addTo(map);
    return () => {
      map?.remove();
      map = null;
    };
  });

  $effect(() => {
    if (!map || !layer) return;
    layer.clearLayers();
    const bounds: L.LatLngExpression[] = [];
    for (const p of points) {
      if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
      const marker = L.circleMarker([p.lat, p.lon], {
        radius: 6,
        color: p.color ?? '#06b6d4',
        weight: 2,
        fillOpacity: 0.6,
      });
      // popup content is built with DOM text nodes — radio data is never interpreted as HTML
      const popup = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = p.label;
      popup.appendChild(title);
      if (p.detail) {
        const detail = document.createElement('div');
        detail.textContent = p.detail;
        popup.appendChild(detail);
      }
      marker.bindPopup(popup);
      marker.bindTooltip(p.label);
      marker.addTo(layer);
      bounds.push([p.lat, p.lon]);
    }
    if (bounds.length && !fitted) {
      map.fitBounds(L.latLngBounds(bounds), { padding: [30, 30], maxZoom: 11 });
      fitted = true;
    }
  });
</script>

<div
  bind:this={el}
  style="height: {height}"
  class="z-0 w-full overflow-hidden rounded-xl"
  role="region"
  aria-label="Karte"
></div>
