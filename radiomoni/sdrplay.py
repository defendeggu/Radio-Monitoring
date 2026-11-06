"""
SDRplay RSP devices (RSPduo, RSP1A, RSPdx …) through SoapySDR and the SDRplay API.

The image has them only when built with WITH_SDRPLAY=1 (the API is proprietary
and is downloaded from sdrplay.com during your own build, see docs/hardware.md).
`sdrplay_rx` (tools/sdrplay_rx.c) streams interleaved int16 IQ to stdout, like
airspyhf_rx; this module builds its command line.

RSPduo: the two tuners are two devices (sdrplay:<serial>:A and :B), each with
its own lock. The first job on either tuner opens the RSPduo as master (mode
MA), a job on the other tuner while it runs as slave (mode SL). Both then run
at up to 2 MS/s. The slave depends on the master: when the master stops, the
slave's stream ends too, so stopping a master with a running slave needs a
confirmation (dependent_sessions) and a waterfall on a master tuner does not
give way while a slave runs.

    tuner A   antenna "Tuner 1 Hi-Z" below 30 MHz (SDRPLAY_HIZ), else "Tuner 1 50 ohm"
    tuner B   antenna "Tuner 2 50 ohm" (bias-T only here, SDRPLAY_BIAS_T)
    gain      0–76 dB → LNA state (RFGR, 0 = most gain) for the band; IF gain by AGC
    notch     MW/FM broadcast notch (rfnotch_ctrl) below 30 MHz with SDRPLAY_NOTCH=auto
"""

from typing import Any, Optional

from radiomoni import config

TOOL = 'sdrplay_rx'
HF_LIMIT = 30_000_000
DUO_MAX_RATE = 2_000_000          # master/slave: both tuners at up to 2 MS/s
SINGLE_MAX_RATE = 10_000_000

# highest LNA state per band (RSPduo; Hi-Z port has fewer states), from the SDRplay API specification
_DUO_LNA = ((12_000_000, 6), (60_000_000, 6), (420_000_000, 9), (1_000_000_000, 9), (2_000_000_000, 8))
_DUO_LNA_HIZ = 4


def parse_selector(args: list[str]) -> tuple[Optional[str], Optional[str]]:
    """(serial, tuner) from the device selector ['--device', 'SERIAL[:A|B]']."""
    if len(args) >= 2 and args[0] == '--device':
        serial, _, tuner = args[1].partition(':')
        return serial or None, tuner or None
    return None, None


def device_id(serial: str, tuner: Optional[str]) -> str:
    return f'sdrplay:{serial}:{tuner}' if tuner else f'sdrplay:{serial}'


def other_tuner(tuner: str) -> str:
    return 'B' if tuner == 'A' else 'A'


def role(serial: str, tuner: Optional[str]) -> str:
    """ST for single-tuner devices; MA unless the other RSPduo tuner already runs (then SL)."""
    if not tuner:
        return 'ST'
    from radiomoni import sdr_lock
    other = sdr_lock.current_holder(device_id(serial, other_tuner(tuner)))
    return 'SL' if other else 'MA'


def antenna(tuner: Optional[str], frequency: int) -> Optional[str]:
    if tuner == 'B':
        return 'Tuner 2 50 ohm'
    if tuner == 'A':
        return 'Tuner 1 Hi-Z' if frequency < HF_LIMIT and config.SDRPLAY_HIZ else 'Tuner 1 50 ohm'
    return None                      # single-tuner RSPs: the driver's default port


def lna_state(gain: int, frequency: int, hiz: bool = False) -> int:
    """RadioMoni gain 0–76 dB → LNA state (0 = most gain, the highest state attenuates most)."""
    highest = _DUO_LNA_HIZ if hiz else next((n for limit, n in _DUO_LNA if frequency <= limit), 8)
    g = min(max(int(gain), 0), 76)
    return int(round((76 - g) / 76 * highest))


def command(selector: list[str], frequency: int, sample_rate: int, gain: int,
            samples: Optional[int] = None, output: str = '-') -> tuple[list[str], dict[str, Any]]:
    """Command line for sdrplay_rx and the facts about the run (mode, antenna) for the lock."""
    serial, tuner = parse_selector(selector)
    mode = role(serial, tuner) if serial else 'ST'
    ant = antenna(tuner, frequency)
    cmd = [TOOL, *selector, '--mode', mode, '-f', str(int(frequency)), '-s', str(int(sample_rate)),
           '--lna', str(lna_state(gain, frequency, hiz=bool(ant and 'Hi-Z' in ant)))]
    if config.SDRPLAY_AGC:
        cmd.append('--agc')
    if ant:
        cmd += ['--antenna', ant]
    notch = config.SDRPLAY_NOTCH
    if notch == 'on' or (notch == 'auto' and frequency < HF_LIMIT):
        cmd += ['--setting', 'rfnotch_ctrl=true']
    if notch == 'on':
        cmd += ['--setting', 'dabnotch_ctrl=true']
    if tuner == 'B' or not tuner:
        cmd += ['--setting', f"biasT_ctrl={'true' if config.SDRPLAY_BIAS_T else 'false'}"]
    if samples:
        cmd += ['-n', str(int(samples))]
    cmd += ['-o', output]
    return cmd, {'sdrplay_mode': mode, 'antenna': ant}


def note_role(selector: list[str], facts: dict[str, Any]) -> None:
    """Remember master/slave in the device's lock (status page, dependency checks)."""
    serial, tuner = parse_selector(selector)
    if serial:
        from radiomoni import sdr_lock
        sdr_lock.annotate(device_id(serial, tuner), facts)


def dependents(device: str) -> list[dict[str, Any]]:
    """Holders that depend on this RSPduo tuner (it is the master and the other tuner runs as slave)."""
    parts = device.split(':')
    if len(parts) != 3 or parts[0] != 'sdrplay':
        return []
    from radiomoni import sdr_lock
    own = sdr_lock.current_holder(device)
    if not own or (own.get('details') or {}).get('sdrplay_mode') != 'MA':
        return []
    other = sdr_lock.current_holder(device_id(parts[1], other_tuner(parts[2])))
    return [other] if other else []
