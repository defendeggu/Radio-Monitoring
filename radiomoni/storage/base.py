"""
Storage backend abstraction.

Two implementations:
- ElasticsearchService (storage/elasticsearch.py): full stack with Logstash,
  Kibana dashboards and ILM.
- SQLiteStorage (storage/sqlite.py): "light" profile without ELK, for small
  hosts such as a Raspberry Pi.

Select with STORAGE_BACKEND=elasticsearch|sqlite. All API code uses
get_storage() and never talks to a backend directly.
"""

import threading
from abc import ABC, abstractmethod
from typing import Any, Optional

from radiomoni import config

# Kinds of "event" documents that are stored generically (one index/table each)
EVENT_KINDS = ('adsb', 'ais', 'ism', 'alerts', 'cw', 'skimmer', 'onair', 'aprstrips', 'aprsplaces')
# Kinds written with put_docs (fixed ids, index by the document's own date): aprs-stats trips and places
PUT_KINDS = ('aprstrips', 'aprsplaces')
RECEPTIONS = ('rf', 'internet')


def enrich_aprs(doc: dict[str, Any]) -> dict[str, Any]:
    """Add the Maidenhead grid locator (e.g. JN47pi) for packets with a position."""
    lat, lon = doc.get('latitude'), doc.get('longitude')
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and 'maidenhead' not in doc:
        try:
            from radiomoni.maidenhead_grid import latlon_to_maidenhead
            doc['maidenhead'] = latlon_to_maidenhead(float(lat), float(lon))
        except ValueError:
            pass
    return doc


def prepare_aprs(doc: dict[str, Any]) -> dict[str, Any]:
    """Before storing an APRS document: reception (default: heard over the air) and locator."""
    doc.setdefault('reception', 'rf')
    doc.setdefault('reception_source', 'rf' if doc['reception'] == 'rf' else None)
    return enrich_aprs(doc)


def aprs_stored(doc: dict[str, Any]) -> None:
    """After storing an APRS document: send packets heard over the air to aprs-stats (never raises)."""
    if doc.get('reception') != 'rf':
        return
    try:
        from radiomoni.aprsstats import feed
        feed.submit(doc)
    except Exception:  # the feed must never break storing
        pass


class StorageBackend(ABC):
    """Interface every storage backend implements."""

    name: str = 'abstract'

    # --- health / stats -----------------------------------------------------
    @abstractmethod
    def health_check(self) -> dict[str, Any]: ...

    @abstractmethod
    def get_overall_stats(self) -> dict[str, Any]: ...

    @abstractmethod
    def get_dashboard_stats(self, hours: int = 24) -> dict[str, Any]:
        """Counts per data type for the last `hours`, an hourly timeline and the latest items."""

    # --- captures -----------------------------------------------------------
    @abstractmethod
    def index_capture(self, capture: dict[str, Any]) -> Optional[str]: ...

    @abstractmethod
    def search_captures(self, query: Optional[str] = None, frequency_min: Optional[int] = None,
                        frequency_max: Optional[int] = None, modulation: Optional[str] = None,
                        language: Optional[str] = None, sdr_type: Optional[str] = None,
                        hours: int = 24, limit: int = 100, offset: int = 0,
                        mode: Optional[str] = None) -> dict[str, Any]: ...

    @abstractmethod
    def get_capture_by_id(self, capture_id: str) -> Optional[dict[str, Any]]: ...

    @abstractmethod
    def get_frequency_usage(self, limit: int = 20) -> list[dict[str, Any]]: ...

    # --- APRS ---------------------------------------------------------------
    @abstractmethod
    def index_aprs(self, message: dict[str, Any]) -> Optional[str]: ...

    @abstractmethod
    def search_aprs(self, callsign: Optional[str] = None, packet_type: Optional[str] = None,
                    hours: int = 24, limit: int = 100, reception: Optional[str] = None) -> dict[str, Any]:
        """reception: 'rf' (also documents without the field, stored before 5.8.0) or 'internet'."""

    @abstractmethod
    def update_aprs(self, doc_id: str, timestamp: Optional[str], fields: dict[str, Any]) -> bool:
        """Add fields to a stored APRS document (by uuid; timestamp helps find its daily index)."""

    @abstractmethod
    def get_aprs_stats(self, hours: int = 24) -> dict[str, Any]: ...

    # --- POCSAG -------------------------------------------------------------
    @abstractmethod
    def index_pocsag(self, message: dict[str, Any]) -> Optional[str]: ...

    @abstractmethod
    def search_pocsag(self, address: Optional[int] = None, message_type: Optional[str] = None,
                      hours: int = 24, limit: int = 100, text_only: bool = False) -> dict[str, Any]:
        """text_only: leave out tone-only messages (no text)."""

    @abstractmethod
    def get_pocsag_stats(self, hours: int = 24) -> dict[str, Any]: ...

    # --- repeaters ----------------------------------------------------------
    @abstractmethod
    def index_repeater_activity(self, activity: dict[str, Any]) -> Optional[str]: ...

    @abstractmethod
    def get_repeater_activity_summary(self, hours: int = 24, band: Optional[str] = None,
                                      canton: Optional[str] = None, limit: int = 20) -> list[dict[str, Any]]: ...

    @abstractmethod
    def index_repeater(self, repeater: dict[str, Any]) -> Optional[str]: ...

    @abstractmethod
    def get_repeaters(self, band: Optional[str] = None, canton: Optional[str] = None,
                      mode: Optional[str] = None, status: Optional[str] = None,
                      limit: int = 100) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_repeater_by_id(self, repeater_id: Any) -> Optional[dict[str, Any]]: ...

    # --- generic events (ADS-B, AIS, ISM sensors, alerts) ---------------------
    @abstractmethod
    def index_event(self, kind: str, doc: dict[str, Any]) -> Optional[str]: ...

    @abstractmethod
    def search_events(self, kind: str, hours: int = 24, limit: int = 100,
                      term: Optional[dict[str, Any]] = None) -> dict[str, Any]: ...

    @abstractmethod
    def put_docs(self, kind: str, docs: list[dict[str, Any]], replace: bool = False) -> int:
        """Write documents with fixed ids (uuid), idempotent: the same id again replaces it.
        Elasticsearch: daily index by the document's @timestamp. replace=True: the documents are the
        complete current set of this kind (one index radio-<kind>-current, everything else is removed).
        Returns the number written."""


_instance: Optional[StorageBackend] = None
_lock = threading.Lock()


def get_storage() -> StorageBackend:
    """Return the configured storage backend (singleton)."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                if config.STORAGE_BACKEND == 'sqlite':
                    from radiomoni.storage.sqlite import SQLiteStorage
                    _instance = SQLiteStorage(config.SQLITE_PATH)
                elif config.STORAGE_BACKEND == 'elasticsearch':
                    from radiomoni.storage.elasticsearch import create_elasticsearch_service
                    _instance = create_elasticsearch_service()
                else:
                    raise RuntimeError(f"Unknown STORAGE_BACKEND: {config.STORAGE_BACKEND!r}")
    return _instance


def set_storage(backend: Optional[StorageBackend]) -> None:
    """Replace the singleton (tests)."""
    global _instance
    _instance = backend
