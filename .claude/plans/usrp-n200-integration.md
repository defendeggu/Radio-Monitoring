# Plan: USRP N200 Integration

## Was kann der USRP N200 mehr?

| Eigenschaft | RTL-SDR | HackRF | Airspy HF+ | **USRP N200** |
|---|---|---|---|---|
| ADC-Auflösung | 8-bit | 8-bit | 16-bit | **14-bit** |
| Dyn. Bereich | ~48 dB | ~48 dB | ~96 dB | **~84 dB** |
| Max. Bandbreite | 3.2 MS/s | 20 MS/s | 912 kS/s | **25 MS/s** |
| Verbindung | USB | USB | USB | **Gigabit Ethernet (IP)** |
| Frequenz (WBX) | 24 MHz–1.77 GHz | 1 MHz–6 GHz | 0.5 kHz–260 MHz | **50 MHz–2.2 GHz** |
| Duplex | RX only | halb (TX/RX) | RX only | **voll (TX+RX)** |

**Hauptvorteile gegenüber den anderen SDRs in diesem Projekt:**
1. **14-bit ADC**: Wesentlich besserer Dynamikbereich und Empfindlichkeit als RTL-SDR/HackRF (8-bit). Schwache Signale sind besser vom Rauschen zu trennen.
2. **Gigabit Ethernet**: Kein USB-Engpass, stabiler Hochdurchsatz, kann räumlich entfernt aufgestellt werden (z.B. Dach mit Antenne, PC im Keller).
3. **Professionelle Kalibrierung**: Bessere Frequenzgenauigkeit (optional TCXO/OCXO-Referenz).

**Mehrere POCSAG-/FasterWhisper-Frequenzen gleichzeitig?**
- **Technisch ja**: Mit 25 MS/s Bandbreite kann man 25 MHz Spektrum auf einmal aufnehmen. Mehrere POCSAG-Kanäle (typisch 12.5–25 kHz breit, oft innerhalb weniger MHz) könnten per Software-Demux parallel dekodiert werden.
- **Aber**: Die aktuelle Pipeline ist single-channel. Multi-channel-Dekodierung würde einen grossen Pipeline-Umbau erfordern (mehrere virtuelle Empfänger parallel).
- **Im aktuellen Scope**: Eine Frequenz zur Zeit, gleich wie die anderen SDRs. Multi-channel als zukünftiges Feature markiert.

---

## Context

Der Benutzer hat einen Ettus Research USRP N200, der per Gigabit Ethernet (IP-Adresse) angesprochen wird — nicht per USB wie die bisherigen SDRs. Das Projekt unterstützt bisher nur USB-SDRs (RTL-SDR, HackRF, Airspy HF+). Weder Frontend noch Backend haben Felder für IP-Adressen oder explizite Gerätewahl.

---

## Implementierungsplan

### 1. `sdr_hardware.py` — USRPCapture-Klasse

**SDRType Enum erweitern** (ca. Zeile 51):
```python
USRP = "usrp"
```

**Neue Klasse `USRPCapture(SDRCapture)`** mit:
- `__init__(self, frequency, sample_rate, gain, device_address: str)`
- `is_available()` → `uhd_usrp_probe --args="addr=<ip>"` (Timeout 5s)
- `get_frequency_range()` → `(50_000_000, 2_200_000_000)` (WBX-Daughterboard; konfigurierbar)
- `get_max_sample_rate()` → `25_000_000`
- `capture_iq()` → `uhd_rx_cfile --args="addr=<ip>" -f <freq> -s <rate> -g <gain> -N <samples> <outfile>`
  - Output-Format: complex float32 (Standard von uhd_rx_cfile) → direkt `np.fromfile(..., dtype=np.complex64)` lesbar
- `capture_audio()` → `capture_iq()` + `_demodulate()` (wie HackRF)

**`get_sdr_instance()` erweitern** — neue Parameter:
```python
def get_sdr_instance(frequency, sample_rate=2_000_000, gain=20,
                     sdr_type=None, device_address=None)
```
- Bei `SDRType.USRP`: `device_address` ist Pflicht (ValueError wenn fehlt)
- Sample Rate auf 25 MS/s clampen

**`detect_sdr()` erweitern** — neue Parameter:
```python
def detect_sdr(preferred_type=None, device_address=None) -> SDRType
```
- Wenn `preferred_type="usrp"` und `device_address` gesetzt → USRP direkt prüfen, ohne USB-Scan

### 2. `web_interface.html` — Globale SDR-Gerätewahl

Ein **globaler SDR-Abschnitt** oben im Formular (oder als sticky Header), gültig für alle Tabs:

```html
<!-- SDR Device Selection (global, alle Tabs) -->
<div class="sdr-device-selector">
  <label>SDR Gerät:</label>
  <select id="globalSdrDevice">
    <option value="auto">Auto-Erkennung</option>
    <option value="hackrf">HackRF One</option>
    <option value="rtlsdr">RTL-SDR</option>
    <option value="airspyhf">Airspy HF+</option>
    <option value="usrp">USRP N200 (Ethernet)</option>
  </select>
  <input type="text" id="usrpIpAddress" placeholder="z.B. 192.168.10.2"
         style="display:none" pattern="\d+\.\d+\.\d+\.\d+">
  <span id="usrpIpHint" style="display:none">IP-Adresse des USRP N200</span>
</div>
```

JavaScript:
- Show/hide IP-Feld bei Wahl von "usrp"
- IP-Validierung (Format + nicht leer) vor Absenden
- `device_type` und `device_address` zu allen API-Aufrufen hinzufügen (Voice, APRS, POCSAG, Repeater)
- `localStorage` für IP-Adresse (Persistenz zwischen Sitzungen)

### 3. `blueprints/streaming.py` — API-Parameter

Alle Streaming-Endpunkte (`/stream-decode`, `/stream/aprs/start`, `/stream/pocsag/start`) um zwei optionale Parameter erweitern:
```python
device_type = data.get('device_type', 'auto')    # 'auto'|'hackrf'|'rtlsdr'|'airspyhf'|'usrp'
device_address = data.get('device_address')       # IP-Adresse für USRP, sonst None
```

Validierung in den Endpunkten:
- Wenn `device_type == 'usrp'` und `device_address` fehlt/leer → HTTP 400

### 4. `streaming_decoder_service.py` — UHD-Kommando

`BaseStreamingDecoder.__init__()` und Subklassen (`StreamingAPRSDecoder`, `StreamingPOCSAGDecoder`) um `device_type` und `device_address` erweitern.

In der Kommandogenerierung (dort wo `hackrf_transfer`, `rtl_sdr`, `airspyhf_rx` gebaut werden):
```python
elif self.sdr_type == SDRType.USRP:
    cmd = [
        'uhd_rx_cfile',
        '--args', f'addr={self.device_address}',
        '-f', str(self.frequency),
        '-s', str(self.sample_rate),
        '-g', str(self.gain),
        '-N', str(num_samples),
        '-t', 'float',   # complex float32 output
        output_file
    ]
```

IQ-Verarbeitung: `np.fromfile(f, dtype=np.complex64)` — kein weiteres Normalisieren nötig (bereits float).

### 5. `tests/test_sdr_hardware.py` — USRP-Tests

```python
class TestUSRPCapture(unittest.TestCase):
    def test_frequency_range(self): ...
    def test_max_sample_rate(self): ...
    def test_is_available_no_uhd(self): ...  # FileNotFoundError → False
    def test_requires_device_address(self): ...  # ValueError ohne IP
    def test_iq_format_complex64(self): ...
```

---

## Kritische Dateien

| Datei | Änderung |
|---|---|
| `sdr_hardware.py` | `SDRType.USRP` Enum, `USRPCapture` Klasse, `get_sdr_instance()`, `detect_sdr()` |
| `web_interface.html` | SDR-Gerätewahl Dropdown + IP-Feld + JS-Logik |
| `blueprints/streaming.py` | `device_type`, `device_address` Parameter in allen Endpunkten |
| `streaming_decoder_service.py` | UHD-Kommando, Parameter-Weitergabe |
| `tests/test_sdr_hardware.py` | USRPCapture-Tests |

---

## Voraussetzung auf dem Server

UHD muss installiert sein:
```bash
# Ubuntu/Debian
sudo apt install uhd-host python3-uhd
# Oder über Ettus-Repository
```

Der Server muss Netzwerkzugriff auf den USRP N200 haben (selbes Subnetz oder geroutetes Netz).

---

## Verifikation

1. `python -m pytest tests/test_sdr_hardware.py -v` → alle Tests grün
2. Im Frontend USRP auswählen, IP eingeben, POCSAG-Streaming starten
3. In den Docker-Logs prüfen: `uhd_rx_cfile --args="addr=<ip>" ...` wird korrekt aufgerufen
4. `/sdr/detect` Endpunkt mit `device_type=usrp&device_address=<ip>` testen
