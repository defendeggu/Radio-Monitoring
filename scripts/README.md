# Repeater Import Scripts

## CSV Import (Empfohlen)

### Verwendung

```bash
# Im Container ausführen
docker exec radio-transcription-api python /app/scripts/import_repeaters_csv.py /app/scripts/example_repeaters.csv

# Oder von außerhalb (wenn Secrets verfügbar)
python scripts/import_repeaters_csv.py scripts/example_repeaters.csv
```

### CSV Format

```csv
callsign,frequency_mhz,offset_mhz,tone,mode,band,location,canton,status
HB9AB,145.625,-0.6,123.0,FM,2m,Zurich,ZH,active
```

**Pflichtfelder**:
- `callsign`: Rufzeichen (z.B. HB9AB)
- `frequency_mhz`: Ausgangsfrequenz in MHz (z.B. 145.625)
- `mode`: Betriebsart (FM, DMR, D-STAR, Fusion, P25)
- `band`: Band (2m, 70cm, 23cm)

**Optionale Felder**:
- `offset_mhz`: Offset in MHz (z.B. -0.6 für 600kHz Minus-Ablage)
- `tone`: CTCSS Ton in Hz (z.B. 123.0)
- `location`: Standort (z.B. "Uetliberg")
- `canton`: Kanton (z.B. ZH, BE, GR)
- `status`: Status (active, inactive, testing)

### Eigene CSV erstellen

1. Kopiere `example_repeaters.csv` zu `my_repeaters.csv`
2. Bearbeite die Datei mit deinen Repeatern
3. Importiere: `python import_repeaters_csv.py my_repeaters.csv`

### Tipps

- Das Script überspringt automatisch Duplikate (gleicher Callsign + Frequenz)
- Use `--allow-duplicates` um Duplikate zuzulassen
- Frequenzen werden automatisch von MHz in Hz konvertiert
- Offset wird automatisch zur Eingangsfrequenz berechnet

### Standard-Offsets

- **2m (144-146 MHz)**: ±0.6 MHz (±600 kHz)
- **70cm (430-440 MHz)**: ±7.6 MHz

### Beispiele

**Nur FM-Repeater importieren**:
```bash
# Filtere CSV vor Import
grep ",FM," repeaters.csv > fm_only.csv
python import_repeaters_csv.py fm_only.csv
```

**Status prüfen**:
```bash
# Im Container
docker exec radio-transcription-api sh -c 'psql -U $(cat /run/secrets/postgres_user) -d $(cat /run/secrets/postgres_db) -c "SELECT callsign, output_frequency/1000000.0 as freq_mhz, band, location_name FROM repeaters ORDER BY band, output_frequency;"'
```

## RepeaterBook Import (Automatisch)

⚠️ **Hinweis**: Dieser Import ist noch in Entwicklung und benötigt Anpassungen an die aktuelle HTML-Struktur von RepeaterBook.com.

```bash
# Wird später verfügbar sein
python import_repeaterbook_data.py --band 2m
```

## Repeater-Daten finden

- **RepeaterBook**: https://www.repeaterbook.com/row_repeaters/index.php?state_id=CH
- **USKA (Schweizer Amateurfunk)**: https://www.uska.ch/
- **HB9F Koordination**: http://www.hb9f.ch/
