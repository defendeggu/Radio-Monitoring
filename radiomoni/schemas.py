"""
Request schemas (pydantic v2).

Every endpoint that accepts input validates it here. The models also feed the
OpenAPI document (see api_docs.py), so validation rules and docs never drift.
"""

from ipaddress import IPv4Address, IPv6Address
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from radiomoni import config

DeviceType = Literal['auto', 'hackrf', 'rtlsdr', 'airspyhf', 'usrp']
Modulation = Literal['FM', 'AM', 'USB', 'LSB']
CaptureMode = Literal['voice', 'aprs', 'pocsag', 'raw']
StreamMode = Literal['aprs', 'pocsag']
DataSource = Literal['aprs', 'pocsag', 'voice', 'adsb', 'ais', 'ism', 'any']

# Widest range across supported hardware; get_sdr_instance() narrows it per device.
MIN_FREQ = 500
MAX_FREQ = 6_000_000_000


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class SdrParams(StrictModel):
    """Common SDR tuning parameters."""
    frequency: int = Field(..., ge=MIN_FREQ, le=MAX_FREQ, description='Center frequency in Hz')
    gain: int = Field(20, ge=0, le=76, description='RF gain in dB')
    sample_rate: int = Field(2_000_000, ge=200_000, le=25_000_000, description='IQ sample rate in Hz')
    device_type: DeviceType = 'auto'
    device_address: Optional[Union[IPv4Address, IPv6Address]] = Field(
        None, description='IP address of a USRP N200 (required when device_type=usrp)')

    @field_validator('frequency', mode='before')
    @classmethod
    def _freq_from_float(cls, v: Any) -> Any:
        # Accept 144.8e6 or "144800000.0" but not fractional Hz
        if isinstance(v, (float, str)):
            try:
                f = float(v)
            except ValueError:
                return v
            if f.is_integer():
                return int(f)
        return v

    @model_validator(mode='after')
    def _usrp_needs_address(self) -> 'SdrParams':
        if self.device_type == 'usrp' and self.device_address is None:
            raise ValueError('USRP N200 requires device_address (IP address)')
        return self

    @property
    def device_address_str(self) -> Optional[str]:
        return str(self.device_address) if self.device_address is not None else None


class WhisperOptions(StrictModel):
    language: Optional[str] = Field(None, pattern=r'^[a-z]{2,3}$', description='ISO language code, empty = auto')
    task: Literal['transcribe', 'translate'] = 'transcribe'
    beam_size: int = Field(config.WHISPER_BEAM_SIZE, ge=1, le=10)
    vad_filter: bool = True
    initial_prompt: Optional[str] = Field(
        None, max_length=500, description='Vocabulary hint, e.g. callsigns or place names')

    @field_validator('language', mode='before')
    @classmethod
    def _empty_language(cls, v: Any) -> Any:
        return None if v in ('', 'auto') else v


class CaptureRequest(SdrParams, WhisperOptions):
    """One-shot capture, optionally decoded or transcribed."""
    mode: CaptureMode = 'voice'
    modulation: Modulation = 'FM'
    duration: int = Field(30, ge=1, le=600, description='Capture length in seconds')

    @model_validator(mode='after')
    def _duration_limit(self) -> 'CaptureRequest':
        limit = config.MAX_CAPTURE_SECONDS.get(self.mode, 600)
        if self.duration > limit:
            raise ValueError(f'{self.mode.upper()} captures are limited to {limit} seconds')
        return self


class RawCaptureRequest(SdrParams):
    """Capture audio only (no decoding)."""
    modulation: Modulation = 'FM'
    duration: int = Field(30, ge=1, le=600)


class StreamRequest(SdrParams):
    mode: StreamMode = 'aprs'
    duration: int = Field(3600, ge=10, le=config.MAX_STREAM_DURATION)


class ChannelModel(StrictModel):
    mode: StreamMode
    frequency: int = Field(..., ge=50_000_000, le=2_200_000_000)
    label: str = Field('', max_length=32, pattern=r'^[\w .\-]*$')


class MultiChannelRequest(StrictModel):
    device_address: Union[IPv4Address, IPv6Address]
    center_freq: int = Field(..., ge=50_000_000, le=2_200_000_000)
    wideband_rate: int = Field(5_000_000, ge=1_000_000, le=25_000_000)
    gain: int = Field(30, ge=0, le=76)
    duration: int = Field(3600, ge=10, le=config.MAX_STREAM_DURATION)
    channels: list[ChannelModel] = Field(..., min_length=2, max_length=8)


class RepeaterScanRequest(StrictModel):
    duration_per_repeater: int = Field(120, ge=5, le=config.MAX_REPEATER_SCAN_SECONDS)
    band: Optional[Literal['2m', '70cm', '23cm', '6m', '10m', 'all']] = None
    canton: Optional[str] = Field(None, pattern=r'^[A-Za-z]{2}$')
    repeater_ids: Optional[list[Union[int, str]]] = Field(None, max_length=500)
    sample_rate: int = Field(2_000_000, ge=200_000, le=20_000_000)
    gain: int = Field(20, ge=0, le=76)
    total_duration: Optional[int] = Field(
        None, ge=60, le=config.MAX_STREAM_DURATION,
        description='Total scan time in seconds: the repeaters are scanned in rounds until it is over. '
                    'Empty = one round')
    until_stopped: bool = Field(False, description='Scan in rounds until POST /scan-repeaters/<id>/stop')

    @model_validator(mode='after')
    def _one_end_condition(self) -> 'RepeaterScanRequest':
        if self.until_stopped and self.total_duration is not None:
            raise ValueError('use either total_duration or until_stopped')
        return self

    @field_validator('repeater_ids')
    @classmethod
    def _ids(cls, v: Optional[list[Union[int, str]]]) -> Optional[list[Union[int, str]]]:
        if v is None:
            return v
        for rid in v:
            if isinstance(rid, str) and (len(rid) > 64 or not rid.replace('-', '').isalnum()):
                raise ValueError('repeater_ids must be numbers or UUIDs')
        return v


class DecodeFileRequest(StrictModel):
    audio_file: str = Field(..., min_length=1, max_length=255)
    frequency: Optional[int] = Field(None, ge=MIN_FREQ, le=MAX_FREQ)
    index_to_es: bool = True


class TranscribeRequest(WhisperOptions):
    audio_file: str = Field(..., min_length=1, max_length=255)


class VoxRequest(SdrParams):
    """Squelch-controlled voice recording (N5)."""
    modulation: Literal['FM', 'AM'] = 'FM'
    duration: int = Field(3600, ge=30, le=config.MAX_STREAM_DURATION)
    sample_rate: int = Field(1_024_000, ge=200_000, le=10_000_000)
    squelch_db: float = Field(10.0, ge=3.0, le=40.0, description='Open when power exceeds noise floor by this much')
    hang_time_ms: int = Field(1500, ge=100, le=10_000)
    min_segment_ms: int = Field(800, ge=100, le=30_000)
    max_segment_s: int = Field(60, ge=5, le=300)
    transcribe: bool = True
    language: Optional[str] = Field(None, pattern=r'^[a-z]{2,3}$')

    @field_validator('language', mode='before')
    @classmethod
    def _empty_language(cls, v: Any) -> Any:
        return None if v in ('', 'auto') else v


class ExternalDecoderRequest(StrictModel):
    """ADS-B (readsb, RTL-SDR or HackRF), AIS (rtl_ais) or ISM sensors (rtl_433); AIS and ISM need an RTL-SDR."""
    decoder: Literal['adsb', 'ais', 'ism']
    frequency: Optional[int] = Field(None, ge=24_000_000, le=1_766_000_000,
                                     description='Only for ism (default 433.92 MHz)')
    gain: Optional[int] = Field(None, ge=0, le=50, description='Empty = automatic gain')
    ppm: int = Field(0, ge=-200, le=200, description='Frequency correction in ppm')
    duration: int = Field(3600, ge=30, le=config.MAX_STREAM_DURATION)


class BookmarkModel(StrictModel):
    name: str = Field(..., min_length=1, max_length=80)
    frequency: int = Field(..., ge=MIN_FREQ, le=MAX_FREQ)
    modulation: Modulation = 'FM'
    mode: Literal['voice', 'aprs', 'pocsag', 'vox', 'adsb', 'ais', 'ism'] = 'voice'
    notes: str = Field('', max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator('tags')
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        cleaned = [t.strip()[:30] for t in v if t.strip()]
        return cleaned


class AlertRuleModel(StrictModel):
    name: str = Field(..., min_length=1, max_length=80)
    enabled: bool = True
    source: DataSource = 'any'
    field: Literal['any', 'callsign', 'address', 'text', 'icao', 'mmsi', 'model'] = 'any'
    match_type: Literal['contains', 'equals', 'regex'] = 'contains'
    pattern: str = Field(..., min_length=1, max_length=200)
    case_sensitive: bool = False
    channels: list[Literal['ntfy', 'telegram', 'webhook', 'email']] = Field(default_factory=list, max_length=4)
    cooldown_seconds: int = Field(300, ge=0, le=86_400)

    @model_validator(mode='after')
    def _regex_compiles(self) -> 'AlertRuleModel':
        if self.match_type == 'regex':
            import re
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f'invalid regular expression: {e}')
        return self


class ScheduleModel(StrictModel):
    name: str = Field(..., min_length=1, max_length=80)
    enabled: bool = True
    cron: str = Field(..., max_length=100, description='Cron expression: "minute hour day month weekday"')
    action: Literal['stream', 'capture', 'vox', 'decoder']
    params: dict[str, Any]

    @field_validator('cron')
    @classmethod
    def _cron_valid(cls, v: str) -> str:
        from apscheduler.triggers.cron import CronTrigger
        try:
            CronTrigger.from_crontab(v, timezone=config.TIMEZONE)
        except ValueError as e:
            raise ValueError(f'invalid cron expression: {e}')
        return v

    @model_validator(mode='after')
    def _params_valid(self) -> 'ScheduleModel':
        # Validate params against the model of the action so bad jobs fail at creation.
        ACTION_MODELS[self.action].model_validate(self.params)
        return self


ACTION_MODELS: dict[str, type[StrictModel]] = {
    'stream': StreamRequest,
    'capture': CaptureRequest,
    'vox': VoxRequest,
    'decoder': ExternalDecoderRequest,
}


class QueryModel(BaseModel):
    """Query-string models ignore unknown parameters (e.g. cache busters)."""
    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)


class HoursLimitQuery(QueryModel):
    hours: int = Field(24, ge=1, le=24 * 365)
    limit: int = Field(100, ge=1, le=1000)


class AprsSearchQuery(HoursLimitQuery):
    callsign: Optional[str] = Field(None, max_length=12, pattern=r'^[A-Za-z0-9/-]+$')
    type: Optional[str] = Field(None, max_length=20)


class PocsagSearchQuery(HoursLimitQuery):
    address: Optional[int] = Field(None, ge=0, le=2_097_151)
    type: Optional[str] = Field(None, max_length=20)


class EventSearchQuery(HoursLimitQuery):
    icao: Optional[str] = Field(None, max_length=8, pattern=r'^[A-Fa-f0-9]+$')
    mmsi: Optional[str] = Field(None, max_length=12, pattern=r'^[0-9]+$')
    model: Optional[str] = Field(None, max_length=60)
    sensor_id: Optional[str] = Field(None, max_length=120)


class RepeaterListQuery(QueryModel):
    band: Optional[str] = Field(None, max_length=10)
    canton: Optional[str] = Field(None, pattern=r'^[A-Za-z]{2}$')
    mode: str = Field('FM', max_length=10)
    status: str = Field('active', max_length=20)
    limit: int = Field(100, ge=1, le=1000)


class RepeaterSummaryQuery(QueryModel):
    hours: int = Field(24, ge=1, le=24 * 365)
    band: Optional[str] = Field(None, max_length=10)
    canton: Optional[str] = Field(None, pattern=r'^[A-Za-z]{2}$')
    limit: int = Field(20, ge=1, le=200)


class SearchQuery(QueryModel):
    query: Optional[str] = Field(None, max_length=200)
    freq_min: Optional[int] = Field(None, ge=0)
    freq_max: Optional[int] = Field(None, ge=0)
    modulation: Optional[str] = Field(None, max_length=10)
    language: Optional[str] = Field(None, max_length=5)
    sdr_type: Optional[str] = Field(None, max_length=20)
    mode: Optional[str] = Field(None, max_length=20)
    hours: int = Field(24, ge=1, le=24 * 365)
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0, le=10_000)
