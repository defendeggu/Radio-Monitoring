# aprs-stats: APRS-Statistik

[aprs-stats](https://github.com/defendeggu/aprs-stats) wertet die APRS-Positionen ausgewählter Stationen aus: Kilometer, Fahrten mit Start und Ziel, Aufenthaltsorte, besuchte Schweizer Gemeinden und Kantone, Pfade. Es läuft als **eigene Container** im RadioMoni-Stack (Compose-Profil `aprsstats`) und ist mit RadioMoni verbunden:

- **Funk → aprs-stats:** Jedes APRS-Paket, das RadioMoni über Funk dekodiert, geht an aprs-stats. aprs-stats behält die Pakete seiner Stationen (Quelle `rf`).
- **Internet → aprs-stats:** Der Collector von aprs-stats liest die eingetragenen Stationen live bei APRS-IS mit. Ältere Daten lassen sich als aprs.fi-Export importieren.
- **aprs-stats → RadioMoni und Kibana:** Ein Abgleich holt alles, was über das Internet kam, nach `radio-aprs-*` und ergänzt die Funk-Pakete um Gemeinde und Kanton. Fahrten kommen nach `radio-aprstrips-*`, Orte nach `radio-aprsplaces-current`.

```
APRS-IS ──► aprs-stats-collector ──► aprsstats-db (PostGIS) ◄── aprs.fi-Import
                                        ▲      │
  RadioMoni (Funk) ── POST /api/ingest ─┘      │ /api/feed/… (Token)
                                               ▼
                         RadioMoni-Abgleich ──► radio-aprs-*, radio-aprstrips-*, radio-aprsplaces-current
```

## Funk oder Internet: die Kennzeichnung

Jedes APRS-Dokument trägt zwei Felder:

| Feld | Werte |
|---|---|
| `reception` | `rf` (über Funk, eigener Empfänger) oder `internet` |
| `reception_source` | `rf`, `aprs_is` (APRS-IS), `import` (aprs.fi-Export), `beacon` (eigene Bake von aprs-stats) |

- Pakete von vor 5.8.0 haben die Felder nicht. Sie kamen alle über Funk und zählen überall als `rf`. `python -m radiomoni.aprs_reparse --set-reception` setzt das Feld auch in den alten Dokumenten.
- **RadioMoni:** Auf der APRS-Seite gibt es eine Spalte *Empfang* (Funk/Internet mit Herkunft und iGate) und einen Filter *Alle / Funk / Internet*. Auf der Karte haben Internet-Stationen einen gestrichelten orangen Rand. Der Live-Feed im Dashboard markiert Internet-Pakete.
- **Kibana:** In der Datenansicht `radio-aprs-*` gibt es das Laufzeitfeld `empfang` (*Funk* / *Internet*, alte Dokumente *Funk*). Das APRS-Dashboard zeigt den Anteil, die Zeitlinie nach Empfang und die Spalte in der Liste.
- **Doppelt empfangen:** Hört RadioMoni ein Paket über Funk und kommt es auch über APRS-IS, speichert aprs-stats die Position nur einmal (gleiches Gerät, 90 s, 50 m). In RadioMoni und Kibana steht das Funk-Paket als *Funk*. Das Internet-Paket kommt zusätzlich als *Internet* dazu, mit `also_rf=true`, damit Pfad und iGate sichtbar bleiben.
- **Alarme:** Alarmregeln gelten nur für Pakete, die über Funk kamen.

## Einrichten

1. `./scripts/setup-env.sh` legt `APRSSTATS_DB_PASSWORD` und `APRSSTATS_API_TOKEN` an.
2. In `.env`:
   ```
   COMPOSE_PROFILES=elk,aprsstats
   APRSSTATS_URL=http://aprsstats-web:8000
   APRSSTATS_APRS_IS_LOGIN=<dein Rufzeichen>      # für das Mitlesen genügt Passcode -1
   ```
3. `docker compose up -d --build`. Vorher prüfen, dass keine SDR-Session läuft. Das Image wird aus aprs-stats `v0.6.0` gebaut; für Entwicklung `APRSSTATS_BUILD_CONTEXT=../aprs-stats/app`.
4. Mit ELK: `./scripts/setup-elk-users.sh` (Templates, Rolle) und `./scripts/import-kibana-dashboards.sh` (Dashboard *RadioMoni · APRS-Statistik*, neue APRS-Ansicht).
5. Auf der Seite von aprs-stats (Knopf *aprs-stats öffnen*, Port 8092) Stationen eintragen.

| Variable | Standard | Bedeutung |
|---|---|---|
| `APRSSTATS_URL` | leer | API von aprs-stats; leer = Anbindung aus |
| `APRSSTATS_DB_PASSWORD`, `APRSSTATS_API_TOKEN` | – | Datenbank-Passwort (nur Buchstaben und Ziffern) und Token der Anbindung |
| `APRSSTATS_APRS_IS_LOGIN`, `…_PASSCODE`, `…_SERVER`, `…_PORT` | –, `-1`, `rotate.aprs2.net`, `14580` | APRS-IS für den Collector; der eigene Passcode nur für Baken |
| `APRSSTATS_FEED_RF` | `true` | Funk-Pakete an aprs-stats schicken |
| `APRSSTATS_SYNC` | `true` | Daten von aprs-stats nach Elasticsearch/SQLite übernehmen (jede Minute; Fahrten alle 15 min, Orte stündlich) |
| `APRSSTATS_BIND`, `APRSSTATS_PORT` | `127.0.0.1`, `8092` | Seite von aprs-stats über nginx. Sie hat **keine Anmeldung**: `0.0.0.0` nur in einem vertrauenswürdigen Netz |
| `APRSSTATS_PUBLIC_URL` | leer | Adresse dieser Seite für den Link; leer = `http://<RadioMoni-Host>:APRSSTATS_PORT` |
| `APRSSTATS_TRIP_GAP_MINUTES`, `…_MAX_PLAUSIBLE_KMH`, `…_BOUNDARIES_AUTOLOAD`, `…_NOMINATIM_URL`, `…_NOMINATIM_EMAIL` | wie aprs-stats | Auswertung, siehe README von aprs-stats |

## Seite „APRS-Statistik“

Kacheln für heute, 7 Tage und alles: Kilometer, Positionen über Funk und Internet, Gemeinden und Kantone. Darunter die Fahrten der letzten 7 Tage (Start → Ziel, km, Dauer, Tempo) und der Zustand von APRS-IS-Verbindung, Abgleich und Funk-Einspeisung. Karte, Heatmap, Gemeinden, Orte benennen, Import und Baken bleiben auf der Seite von aprs-stats.

## Kibana

| Index | Inhalt |
|---|---|
| `radio-aprs-*` | alle APRS-Pakete, mit `reception`, `reception_source`, `igate`, `digis`, `also_rf`, `gemeinde`, `bfs_nr`, `kanton` |
| `radio-aprstrips-*` | eine Fahrt pro Gerät und Start: von, nach, km, Dauer, Tempo, Start- und Zielposition |
| `radio-aprsplaces-current` | die aktuellen Aufenthaltsorte (wird bei jedem Abgleich ersetzt) |

Das Dashboard *RadioMoni · APRS-Statistik* zeigt Kilometer pro Tag nach Gerät, Fahrten und Ziele auf der Karte, Orte, Gemeinden, Kantone und den Anteil Funk/Internet. Die Rolle `radio_api` darf in `radio-aprsplaces-*` löschen, damit die Orte ersetzt werden können.

## Umzug einer bestehenden aprs-stats-Installation

1. Sicherung des alten Stacks: `docker compose exec -T db pg_dump -U aprs aprs | gzip > aprs-stats.sql.gz` (im Verzeichnis von aprs-stats).
2. Alten Stack stoppen (`docker compose stop`): Port 8092 und die APRS-IS-Verbindung werden frei.
3. In RadioMoni das Profil `aprsstats` aufsetzen und starten, dann die Web- und Collector-Container stoppen (`docker compose stop aprsstats-web aprsstats-collector`).
4. Einspielen in die leere Datenbank: `gunzip -c aprs-stats.sql.gz | docker compose exec -T aprsstats-db psql -U aprs aprs`.
5. `docker compose up -d`. aprs-stats erweitert das Schema beim Start (`ext_ref`). Der erste Abgleich übernimmt alle Pakete und Importe nach Elasticsearch.

## Datenschutz und Grenzen

- Positionsdaten sind persönliche Daten, auch die eigenen. Die Seite von aprs-stats hat keine Anmeldung; darum ist sie standardmässig nur auf diesem Rechner erreichbar.
- Pfade und iGates gibt es nur für Pakete aus APRS-IS. APRS-IS liefert pro Paket meist nur den ersten Weg ins Netz. Der aprs.fi-Export enthält keine Pfade.
- Gemeinde und Kanton kennt aprs-stats nur in der Schweiz, in Liechtenstein und den Enklaven, aus den swisstopo-Grenzen (swissBOUNDARIES3D).
- aprs-stats sendet nichts über Funk. Eine Bake geht nur ans Internet (APRS-IS) und nur, wenn du sie in aprs-stats einrichtest.

---

<a id="english-version"></a>

## English Version

[aprs-stats](https://github.com/defendeggu/aprs-stats) evaluates the APRS positions of chosen stations: kilometres, trips with start and destination, places, Swiss municipalities and cantons visited, paths. It runs as **containers of its own** in the RadioMoni stack (compose profile `aprsstats`) and is connected to RadioMoni:

- **Radio → aprs-stats:** every APRS packet RadioMoni decodes over the air goes to aprs-stats, which keeps the packets of its stations (source `rf`).
- **Internet → aprs-stats:** its collector follows the stations on APRS-IS. Older data can be imported from aprs.fi.
- **aprs-stats → RadioMoni and Kibana:** a sync copies everything that came over the internet to `radio-aprs-*` and adds municipality and canton to the packets heard over the air. Trips go to `radio-aprstrips-*`, places to `radio-aprsplaces-current`.

**Marking:** every APRS document has `reception` (`rf` or `internet`) and `reception_source` (`rf`, `aprs_is`, `import`, `beacon`). Older documents without the field count as `rf`; `python -m radiomoni.aprs_reparse --set-reception` sets it.
- **RadioMoni:** the APRS page has a *Reception* column and an *All / Radio / Internet* filter, and internet stations have a dashed amber outline on the map.
- **Kibana:** the `radio-aprs-*` data view has the runtime field `empfang` (*Funk* / *Internet*).
- **Received twice:** a packet heard over the air and also received from APRS-IS counts once in aprs-stats. In Kibana the internet copy carries `also_rf=true`.
- **Alerts:** alert rules apply only to packets heard over the air.

**Setup:** run `./scripts/setup-env.sh`, then set `COMPOSE_PROFILES=elk,aprsstats`, `APRSSTATS_URL=http://aprsstats-web:8000` and `APRSSTATS_APRS_IS_LOGIN` in `.env`. Then run `docker compose up -d --build`, `./scripts/setup-elk-users.sh` and `./scripts/import-kibana-dashboards.sh`. The variables are listed in the German table above. aprs-stats' own page has no login and is bound to `127.0.0.1:8092` by default.

**Moving an existing installation:**
1. Back up the old database with `pg_dump`.
2. Stop the old stack.
3. Start the `aprsstats` profile, then stop `aprsstats-web` and `aprsstats-collector`.
4. Restore the dump into `aprsstats-db`.
5. Run `docker compose up -d`.
