"""Validate sequential human-confirmed physical button capture without guessed bits.

Only associate labels when the entire expected sequence has exactly one complete
press/release per unique device/code, no overlap/repeats/drops and fresh identity.
A missing event invalidates positional labels for the whole capture.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ORDER = ('UP', 'RIGHT', 'DOWN', 'LEFT', 'A', 'B', 'X', 'Y', 'START', 'SELECT',
         'L1', 'R1', 'L2', 'R2', 'FN', 'VOLUME_UP', 'VOLUME_DOWN', 'POWER')
EVENT = re.compile(r'^input_event device=(r36-(?:serial|direct)-keys) code=(\d+) value=([012])$')


def analyze(raw, run_id, human_order_confirmed=False):
    lines = raw.decode('ascii').splitlines()
    fresh = lines.count('run_id=' + run_id) == 1
    complete = (lines.count('R36 INPUT INVENTORY V1') == 1
                and lines.count('R36 INPUT INVENTORY END') == 1
                and lines.count('input_inventory=PASS') == 1
                and lines.count('input_probe_rc=0') == 1
                and lines.count('input_capture_ms=60000') == 1
                and lines.count('probe_rc=0 errno=0') == 1
                and lines[-1:] == ['R36 DISPLAY PROBE END'])
    events = []
    bad = []
    for line in lines:
        if line.startswith('input_event '):
            m = EVENT.fullmatch(line)
            if not m:
                bad.append('malformed event')
                continue
            device, code, value = m.groups()
            events.append((device, int(code), int(value)))
    footer = [re.fullmatch(r'input_events_recorded=(\d+) dropped=(\d+)', line)
              for line in lines if line.startswith('input_events_recorded=')]
    if len(footer) != 1 or not footer[0] or int(footer[0][1]) != len(events) or int(footer[0][2]):
        bad.append('event count mismatch or dropped events')
    if 'input_syn_dropped=1' in lines or 'input_event_limit=1' in lines:
        bad.append('capture discontinuity')
    active = None
    pairs, seen = [], set()
    for ordinal, (device, code, value) in enumerate(events):
        key = (device, code)
        if code >= 768:
            bad.append('out-of-range code')
        if value == 2:
            # Kernel repeat records do not count as extra physical presses.
            if active is None or active[:2] != key:
                bad.append('repeat without active press')
            continue
        if value == 1:
            if active is not None:
                bad.append('overlapping or duplicate press')
            active = (device, code, ordinal)
        elif active is None or active[:2] != key:
            bad.append('release without matching press')
        else:
            if key in seen:
                bad.append('same button pressed more than once')
            seen.add(key)
            pairs.append({'device': device, 'code': code, 'press_ordinal': active[2],
                          'release_ordinal': ordinal})
            active = None
    if active is not None:
        bad.append('unreleased press')
    if len(pairs) != len(ORDER):
        bad.append('expected18 complete unique presses, got' + str(len(pairs)))
    verified = fresh and complete and not bad and human_order_confirmed
    return {'capture_sha256': hashlib.sha256(raw).hexdigest(), 'run_id': run_id,
            'fresh': fresh, 'complete': complete, 'events': len(events),
            'complete_pairs': len(pairs), 'raw_pairs': pairs,
            'human_order_confirmed': human_order_confirmed,
            'physical_labels_verified': bool(verified),
            'labels': [dict(pair, physical=name) for name, pair in zip(ORDER, pairs)] if verified else [],
            'errors': sorted(set(bad)), 'legacy_bits_assigned': False,
            'navigation_verified': False, 'power_action_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--human-order-confirmed', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error('output must be new with existing parent')
    result = analyze(args.capture.read_bytes(), args.run_id, args.human_order_confirmed)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('events', 'complete_pairs', 'physical_labels_verified', 'errors')}, indent=2))


if __name__ == '__main__':
    main()
