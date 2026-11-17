"""Validate human-labelled physical presses against one fresh device capture.

Does NOT guess serializer ordering or inject keys. The user records one explicit
press per label during a hardware diagnostic; this tool cross-checks release and
source identity and writes the numeric map consumed by legacy_keys.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

DEFAULT_BITS = {'SELECT': 0, 'START': 3, 'UP': 4, 'RIGHT': 5, 'DOWN': 6, 'LEFT': 7,
                'L1': 10, 'R1': 11, 'X': 12, 'A': 13, 'B': 14, 'Y': 15}
EVENT = re.compile(r'^input_event device=(r36-(?:serial|direct)-keys) code=([0-9]+) value=([012])$')


def validate(raw, labels, run_id):
    lines = raw.decode('ascii').splitlines()
    if lines.count('run_id=' + run_id) != 1 or lines.count('R36 INPUT INVENTORY V1') != 1 or lines.count('R36 INPUT INVENTORY END') != 1:
        raise ValueError('missing, duplicate or stale input capture identity')
    if lines.count('input_inventory=PASS') != 1 or lines.count('input_probe_rc=0') != 1 or 'input_syn_dropped=1' in lines:
        raise ValueError('input capture did not complete without dropped events')
    if set(labels) != set(DEFAULT_BITS):
        raise ValueError('exactly twelve named physical buttons must be labelled')
    # Annotations identify an event ordinal in this capture, not just a raw code
    # that happened to occur elsewhere. Physical labels are supplied by a person.
    events = [m.groups() for line in lines if (m := EVENT.fullmatch(line))]
    observed, mapping = set(), []
    for name, bit in DEFAULT_BITS.items():
        index = labels[name]
        if type(index) is not int or not 0 <= index < len(events):
            raise ValueError('invalid labelled event ordinal: ' + name)
        device, code, value = events[index]
        code = int(code)
        if value != '1' or code >= 768:
            raise ValueError('label must identify a real press: ' + name)
        if code in observed:
            raise ValueError('same evdev code labelled as two physical buttons')
        # The single-number production mapping cannot distinguish equal codes
        # on different sources; reject those rather than silently aliasing.
        if any(d != device and int(c) == code for d, c, _ in events):
            raise ValueError('same evdev code appears on multiple sources')
        if not any(d == device and int(c) == code and v == '0' for d, c, v in events[index + 1:]):
            raise ValueError('no subsequent release: ' + name)
        observed.add(code)
        mapping.append((code, bit, name, device, index))
    return mapping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('annotations', type=Path, help='JSON: physical button name -> zero-based EV_KEY event ordinal')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raw = args.capture.read_bytes()
    mapping = validate(raw, json.loads(args.annotations.read_text()), args.run_id)
    args.out.mkdir(exist_ok=False)
    (args.out / 'evdev-to-legacy.map').write_text(''.join(f'{code} {bit}\n' for code, bit, *_ in sorted(mapping)))
    record = {'capture_sha256': hashlib.sha256(raw).hexdigest(), 'run_id': args.run_id,
              'physical_labels_source': str(args.annotations), 'default_legacy_bit_schema': DEFAULT_BITS,
              'mapping': [{'code': c, 'bit': b, 'name': n, 'device': d, 'event_ordinal': i} for c, b, n, d, i in mapping],
              'scope': 'human-labelled capture validation; not independent proof that physical labels are accurate',
              'legacy_navigation_verified': False}
    (args.out / 'calibration.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
