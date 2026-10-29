"""
Flask blueprints of the RadioMoni API.

- health      liveness / readiness
- sdr         detection, status, force-stop
- capture     captures, transcription, search
- recordings  recording files (audio player, download, delete)
- aprs        APRS search / stats / map / decode
- pocsag      POCSAG search / stats / decode
- repeater    repeater activity scans
- streaming   streaming sessions, multi-channel, VOX, external decoders
- decoders    ADS-B / AIS / ISM data
- stats       statistics, dashboard, live events (SSE)
- library     bookmarks, alert rules, schedules
- export      CSV / GeoJSON / KML / ZIP export
"""

from radiomoni.blueprints.aprs import aprs_bp
from radiomoni.blueprints.capture import capture_bp
from radiomoni.blueprints.decoders import decoders_bp
from radiomoni.blueprints.export import export_bp
from radiomoni.blueprints.health import health_bp
from radiomoni.blueprints.library import library_bp
from radiomoni.blueprints.pocsag import pocsag_bp
from radiomoni.blueprints.recordings import recordings_bp
from radiomoni.blueprints.repeater import repeater_bp
from radiomoni.blueprints.sdr import sdr_bp
from radiomoni.blueprints.stats import stats_bp
from radiomoni.blueprints.streaming import streaming_bp

ALL_BLUEPRINTS = [health_bp, sdr_bp, capture_bp, recordings_bp, aprs_bp, pocsag_bp, repeater_bp,
                  streaming_bp, decoders_bp, stats_bp, library_bp, export_bp]

__all__ = ['ALL_BLUEPRINTS']
