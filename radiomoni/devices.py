"""
SDR devices connected to this machine, each with its own SDR lock.

The list comes from sysfs (/sys/bus/usb/devices: vendor/product id and serial),
which opens no device and so never disturbs a job that is running. A USRP is
not on USB; it is addressed by its IP address.

    hackrf:<serial>   rtlsdr:<serial>   airspyhf:<serial>   usrp:<ip>

The id uses the USB serial when it is unique among devices of that type and
the index otherwise (many RTL-SDR sticks all report "00000001"; give them
unique serials with `rtl_eeprom -s`). Tools only get a device selector (-d …)
when more than one device of a type is connected, so a single SDR per type
behaves exactly as before.

`resolve()` turns the request fields (device_id, or device_type + address)
into a Device. "auto" keeps the old order HackRF > Airspy HF+ > RTL-SDR.
"""

import logging
import os
import re
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Optional

from radiomoni import config
from radiomoni.sdr_hardware import SDRType, detect_sdr

logger = logging.getLogger(__name__)

USB_IDS: dict[tuple[str, str], SDRType] = {
    ('1d50', '6089'): SDRType.HACKRF,
    ('0bda', '2838'): SDRType.RTLSDR,
    ('0bda', '2832'): SDRType.RTLSDR,
    ('03eb', '800c'): SDRType.AIRSPYHF,
    # SDRplay RSPs (image with WITH_SDRPLAY=1)
    ('1df7', '2500'): SDRType.SDRPLAY, ('1df7', '3000'): SDRType.SDRPLAY, ('1df7', '3010'): SDRType.SDRPLAY,
    ('1df7', '3020'): SDRType.SDRPLAY, ('1df7', '3030'): SDRType.SDRPLAY, ('1df7', '3050'): SDRType.SDRPLAY,
    ('1df7', '3060'): SDRType.SDRPLAY,
}
RSP_MODELS = {'2500': 'RSP1', '3000': 'RSP1A', '3010': 'RSP2', '3020': 'RSPduo', '3030': 'RSPdx', '3050': 'RSP1B',
              '3060': 'RSPdx-R2'}
AUTO_ORDER = (SDRType.HACKRF, SDRType.AIRSPYHF, SDRType.RTLSDR, SDRType.SDRPLAY)
LABELS = {SDRType.HACKRF: 'HackRF One', SDRType.RTLSDR: 'RTL-SDR', SDRType.AIRSPYHF: 'Airspy HF+',
          SDRType.USRP: 'USRP N200', SDRType.SDRPLAY: 'SDRplay RSP'}
CACHE_SECONDS = 10.0


class NoSdrError(RuntimeError):
    """No SDR hardware at all (HTTP 503); an unknown device id is a ValueError (400)."""


@dataclass(frozen=True)
class Device:
    id: str
    type: SDRType
    index: int = 0                      # position among devices of this type
    serial: Optional[str] = None
    address: Optional[str] = None       # USRP only
    label: str = ''
    usb_path: Optional[str] = None
    shared: bool = False                # more than one device of this type: tools need a selector
    serial_unique: bool = True
    tuner: Optional[str] = None         # RSPduo: 'A' or 'B' (each tuner is a device with its own lock)

    def args(self, tool: str) -> list[str]:
        """Device selector for a command line tool; empty when this is the only device of its type."""
        if self.type == SDRType.SDRPLAY:          # sdrplay_rx always needs serial (and tuner)
            return ['--device', (self.serial or '') + (f':{self.tuner}' if self.tuner else '')]
        if not self.shared:
            return []
        if self.type == SDRType.HACKRF and self.serial:
            return ['-d', self.serial]
        if self.type == SDRType.RTLSDR:
            key = self.serial if self.serial and self.serial_unique else str(self.index)
            if tool == 'rtl_433':
                return ['-d', f':{key}' if self.serial and self.serial_unique else key]
            if tool == 'readsb':
                return ['--device', key]
            if tool == 'rtl_ais':
                return ['-d', str(self.index)]
            return ['-d', key]
        return []

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d['type'] = self.type.value
        return d


def _read(path: str) -> Optional[str]:
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return f.read().strip() or None
    except OSError:
        return None


def scan_usb(root: Optional[str] = None) -> list[Device]:
    """SDRs on USB, in a stable order (bus path), with ids and selectors."""
    root = root or config.SYSFS_USB_ROOT
    found: list[tuple[SDRType, str, Optional[str], str]] = []
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return []
    for name in entries:
        if ':' in name:              # interfaces, not devices
            continue
        base = os.path.join(root, name)
        vid, pid = _read(os.path.join(base, 'idVendor')), _read(os.path.join(base, 'idProduct'))
        sdr_type = USB_IDS.get(((vid or '').lower(), (pid or '').lower()))
        if sdr_type is None:
            continue
        serial = _read(os.path.join(base, 'serial'))
        if sdr_type == SDRType.HACKRF and serial and not re.fullmatch(r'[0-9a-fA-F]+', serial):
            serial = None             # "RunningFromRAM" (firmware loaded to RAM) is no serial number
        found.append((sdr_type, name, serial, (pid or '').lower()))
    devices: list[Device] = []
    for sdr_type in AUTO_ORDER:
        of_type = [f for f in found if f[0] == sdr_type]
        serials = [f[2] for f in of_type]
        for index, (_, path, serial, pid) in enumerate(of_type):
            unique = bool(serial) and serials.count(serial) == 1
            key = serial if unique else str(index)
            suffix = f' #{index + 1}' if len(of_type) > 1 else ''
            common = dict(type=sdr_type, index=index, serial=serial, usb_path=path, shared=len(of_type) > 1,
                          serial_unique=unique)
            if sdr_type == SDRType.SDRPLAY:
                model = RSP_MODELS.get(pid, 'RSP')
                same_model = [f for f in of_type if f[3] == pid]       # number only RSPs of the same model
                suffix = f' #{same_model.index((_, path, serial, pid)) + 1}' if len(same_model) > 1 else ''
                if model == 'RSPduo':           # two tuners: two devices with their own locks
                    for tuner in ('A', 'B'):
                        devices.append(Device(id=f'sdrplay:{key}:{tuner}', label=f'RSPduo{suffix} Tuner {tuner}',
                                              tuner=tuner, **common))  # type: ignore[arg-type]
                    continue
                devices.append(Device(id=f'sdrplay:{key}', label=model + suffix, **common))  # type: ignore[arg-type]
                continue
            devices.append(Device(id=f'{sdr_type.value}:{key}', label=LABELS[sdr_type] + suffix,
                                  **common))  # type: ignore[arg-type]
    return devices


_cache: tuple[float, list[Device]] = (0.0, [])
_fallback_cache: dict[str, tuple[float, Optional[Device]]] = {}
_lock = threading.Lock()


def list_devices(refresh: bool = False) -> list[Device]:
    global _cache
    with _lock:
        stamp, devices = _cache
        if refresh or time.monotonic() - stamp > CACHE_SECONDS:
            devices = scan_usb()
            _cache = (time.monotonic(), devices)
        return list(devices)


def fallback_device(sdr_type: SDRType) -> Device:
    """A device the tools found although sysfs did not list it (no sysfs, tests)."""
    return Device(id=f'{sdr_type.value}:0', type=sdr_type, label=LABELS.get(sdr_type, sdr_type.value))


def resolve(device_type: Optional[str] = 'auto', device_address: Optional[str] = None,
            device_id: Optional[str] = None) -> Device:
    """The device a job runs on. Raises ValueError when it does not exist."""
    if device_id:
        if device_id.startswith('usrp:'):
            return Device(id=device_id, type=SDRType.USRP, address=device_id.split(':', 1)[1], label=LABELS[SDRType.USRP])
        for d in list_devices():
            if d.id == device_id:
                return d
        for d in list_devices(refresh=True):
            if d.id == device_id:
                return d
        raise ValueError(f'SDR device {device_id} is not connected')
    wanted = (device_type or 'auto').lower()
    if wanted == 'usrp':
        if not device_address:
            raise ValueError('USRP N200 requires device_address (IP address)')
        return Device(id=f'usrp:{device_address}', type=SDRType.USRP, address=str(device_address),
                      label=LABELS[SDRType.USRP])
    devices = list_devices()
    if wanted == 'auto':
        for sdr_type in AUTO_ORDER:
            match = next((d for d in devices if d.type == sdr_type), None)
            if match:
                return match
    else:
        match = next((d for d in devices if d.type.value == wanted), None)
        if match:
            return match
    stamp, cached = _fallback_cache.get(wanted, (0.0, None))
    if time.monotonic() - stamp > CACHE_SECONDS:
        detected = detect_sdr(preferred_type=None if wanted == 'auto' else wanted, device_address=device_address)
        cached = None if detected == SDRType.UNKNOWN else fallback_device(detected)
        _fallback_cache[wanted] = (time.monotonic(), cached)
    if cached is None:
        raise NoSdrError('No SDR hardware detected')
    return cached


def clear_cache() -> None:
    global _cache
    with _lock:
        _cache = (0.0, [])
        _fallback_cache.clear()


def default_id() -> str:
    """Lock id of the device that jobs without a device choice use."""
    try:
        return resolve('auto').id
    except (ValueError, NoSdrError):
        return 'default'

