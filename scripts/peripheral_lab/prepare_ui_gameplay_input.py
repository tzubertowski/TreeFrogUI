"""Validate and emit the 12-button gameplay SysV map from measured physical capture."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
GAMEPLAY_BITS = {
    'SELECT': 0, 'START': 3,
    'UP': 4, 'RIGHT': 5, 'DOWN': 6, 'LEFT': 7,
    'L1': 10, 'R1': 11,
    'X': 12, 'A': 13, 'B': 14, 'Y': 15,
}
LIBRETRO_JOYPAD_ORDER = (
    'B', 'Y', 'SELECT', 'START',
    'UP', 'DOWN', 'LEFT', 'RIGHT',
    'A', 'X', 'L1', 'R1',
)
EXTRA_DIRECT_BUTTONS = {'L2', 'R2', 'FN', 'VOL+', 'VOL-', 'POWER'}


def gameplay_map(physical, calibration):
    if not physical.get('physical_labels_verified') or not physical.get('human_order_confirmed'):
        raise ValueError('physical 18-button capture is not human-confirmed')
    if (physical.get('capture_sha256') != calibration.get('capture_sha256') or
            physical.get('run_id') != calibration.get('run_id')):
        raise ValueError('calibration does not come from the verified physical capture')

    by_physical = {}
    extra_codes = set()
    for row in physical.get('mapping', []):
        name = row.get('physical')
        if name in by_physical:
            raise ValueError(f'duplicate physical button entry: {name}')
        by_physical[name] = row
        if name in EXTRA_DIRECT_BUTTONS:
            extra_codes.add(int(row['code']))

    entries = calibration.get('mapping', [])
    if len(entries) != 12:
        raise ValueError('gameplay map requires exactly 12 calibrated buttons')

    by_name = {}
    for row in entries:
        name = row.get('name')
        if name in by_name or name not in GAMEPLAY_BITS:
            raise ValueError(f'unexpected or duplicate gameplay button: {name}')
        by_name[name] = row

    if set(by_name) != set(GAMEPLAY_BITS):
        raise ValueError('missing required gameplay buttons')

    pairs = []
    codes = set()
    for name, expected_bit in GAMEPLAY_BITS.items():
        cal = by_name[name]
        phys = by_physical.get(name)
        if not phys:
            raise ValueError(f'physical capture missing button: {name}')
        code = int(cal['code'])
        bit = int(cal['bit'])
        if bit != expected_bit or code != int(phys['code']):
            raise ValueError(f'gameplay mapping mismatch for {name}')
        if cal.get('device') and phys.get('device') and cal['device'] != phys['device']:
            raise ValueError(f'device mismatch for {name}')
        if not 0 <= code < 768 or code in codes or code in extra_codes:
            raise ValueError(f'invalid or colliding evdev code for {name}: {code}')
        codes.add(code)
        pairs.append((code, bit))

    return ''.join(f'{code} {bit}\n' for code, bit in sorted(pairs))
