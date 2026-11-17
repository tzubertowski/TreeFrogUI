from pathlib import Path
import struct
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from prepare_input_calibration import validate, ADDITIONS
sys.path.insert(0, str(HERE.parent / 'boot_crypto'))
from loader_fs_probe import make_probe


def test_only_explicit_polled_input_nodes_are_added():
    before = {'/r36-direct-keys/function-key': {'gpios': struct.pack('>III', 10, 2, 1)}}
    after = dict(before)
    for name, (pin, code) in ADDITIONS.items():
        after['/r36-direct-keys/' + name] = {'linux,code': struct.pack('>I', code),
                                            'gpios': struct.pack('>III', 10, pin, 1)}
    assert validate(before, after) == 10
    after['/unrelated-output'] = {'status': b'okay\0'}
    with pytest.raises(ValueError, match='outside'):
        validate(before, after)


@pytest.mark.parametrize('seconds', [0, 29, 121, True, 90.0])
def test_extended_watchdog_bounds_before_assembly(seconds):
    with pytest.raises(ValueError, match='watchdog'):
        make_probe(0, 0, 0, bytes(64), b'', watchdog_seconds=seconds)


def test_capture_extended_without_unbounded_recording():
    text = (HERE / 'input_probe.h').read_text()
    assert '#define R36_INPUT_CAPTURE_MS 12000' in text
    assert 'R36_INPUT_CAPTURE_MS > 60000' in text
    assert 'end = input_time_ms() + R36_INPUT_CAPTURE_MS' in text
    assert 'SYN_DROPPED' in text and 'total++ >= 1024' in text
    driver = (HERE.parent / 'boot_crypto/run_restored_cold_trial.py').read_text()
    assert "manifest.get('watchdog_seconds', 30)" in driver
    assert 'time.sleep(watchdog_seconds + 5)' in driver
