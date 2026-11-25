"""
aprs-stats (https://github.com/defendeggu/aprs-stats) as part of the stack.

aprs-stats keeps APRS positions of chosen stations in PostGIS: live from
APRS-IS (internet), imported from aprs.fi, and - fed by RadioMoni - heard over
the air. It computes kilometres, trips, places and the Swiss municipalities
and cantons visited.

RadioMoni
- sends every APRS packet it decodes over the air to aprs-stats (feed.py),
- copies what aprs-stats has (internet packets, imports, trips, places) into
  its own storage, so it shows up in the UI and in Kibana (sync.py).

Every APRS document carries `reception` = `rf` | `internet` and
`reception_source` = `rf` | `aprs_is` | `import` | `beacon`.
"""

RECEPTION_RF = 'rf'
RECEPTION_INTERNET = 'internet'
INTERNET_SOURCES = ('aprs_is', 'import', 'beacon')
