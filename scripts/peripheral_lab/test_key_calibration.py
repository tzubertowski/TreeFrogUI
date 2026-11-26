from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibrate_legacy_keys import DEFAULT_BITS, validate


def capture():
    lines = ['run_id=abc', 'R36 INPUT INVENTORY V1']
    labels = {}
    for i, name in enumerate(DEFAULT_BITS):
        labels[name] = i * 2
        lines += [f'input_event device=r36-serial-keys code={704+i} value=1',
                  f'input_event device=r36-serial-keys code={704+i} value=0']
    lines += ['input_inventory=PASS', 'R36 INPUT INVENTORY END', 'input_probe_rc=0']
    return ('\n'.join(lines) + '\n').encode(), labels


def test_calibration_uses_only_explicit_press_labels():
    raw, labels = capture()
    result = validate(raw, labels, 'abc')
    assert len(result) == 12
    assert next(r for r in result if r[2] == 'B')[1] == 14


@pytest.mark.parametrize('fault', ['stale', 'drop', 'missing_label', 'release_label', 'duplicate_code', 'no_release'])
def test_ambiguous_or_incomplete_capture_rejected(fault):
    raw, labels = capture()
    if fault == 'stale': raw = raw.replace(b'run_id=abc', b'run_id=old')
    if fault == 'drop': raw += b'input_syn_dropped=1\n'
    if fault == 'missing_label': labels.pop('A')
    if fault == 'release_label': labels['A'] += 1
    if fault == 'duplicate_code': labels['B'] = labels['A']
    if fault == 'no_release': raw = raw.replace(b'code=704 value=0', b'code=704 value=2')
    with pytest.raises(ValueError): validate(raw, labels, 'abc')
