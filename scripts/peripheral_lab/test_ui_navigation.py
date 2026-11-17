from pathlib import Path
import copy

import pytest
from prepare_ui_navigation import direction_map, EXPECTED_BITS

HERE = Path(__file__).resolve().parent


def records():
    physical = {'physical_labels_verified': True, 'human_order_confirmed': True,
                'capture_sha256': 'hash', 'run_id': 'fresh',
                'mapping': [{'physical': name, 'code': 704 + i} for i, name in enumerate(EXPECTED_BITS)]}
    calibration = {'capture_sha256': 'hash', 'run_id': 'fresh',
                   'mapping': [{'name': name, 'code': 704 + i, 'bit': bit}
                               for i, (name, bit) in enumerate(EXPECTED_BITS.items())]}
    return physical, calibration


def test_direction_map_excludes_confirm_and_special_buttons():
    p, c = records()
    assert direction_map(p, c) == '704 4\n705 5\n706 6\n707 7\n'


@pytest.mark.parametrize('case', ['stale', 'unconfirmed', 'wrong_bit', 'wrong_code', 'duplicate'])
def test_map_requires_measured_identity_and_exact_four_directions(case):
    p, c = records()
    if case == 'stale': c['run_id'] = 'old'
    if case == 'unconfirmed': p['human_order_confirmed'] = False
    if case == 'wrong_bit': c['mapping'][0]['bit'] = 13
    if case == 'wrong_code': c['mapping'][0]['code'] = 99
    if case == 'duplicate': c['mapping'].append(copy.deepcopy(c['mapping'][0]))
    with pytest.raises(ValueError): direction_map(p, c)


def test_bridge_owns_segment_and_is_stopped_before_SD_writes():
    main = (HERE / 'ui_console_init.c').read_text()
    bridge = (HERE / 'ui_navigation_bridge.h').read_text()
    assert '#ifdef R36_UI_NAVIGATION' in main
    assert 'if(navigation_start(key))goto finish_log;' in main
    assert 'if(!navigation_alive())' in main
    assert main.index('if(navigation_stop())goto wait_reset;') < main.index('MS_REMOUNT,')
    assert 'keys_diagnostic_ready=1' in bridge
    assert 'waitpid(navigation_pid' in bridge and 'SIGKILL' in bridge
    assert 'r36-navigation.map' in bridge
    assert 'r36-ui-keys.txt' in main


def test_publisher_enforces_no_confirm_buttons_and_bounded_logs():
    text = (HERE / 'legacy_keys.c').read_text()
    assert 'R36_KEYS_NAVIGATION_ONLY' in text
    assert 'bit < 4 || bit > 7' in text and 'count == 4' in text
    assert 'diagnostic_records++ < 128' in text
    assert 'IPC_CREAT | IPC_EXCL' in text
    assert 'SYN_DROPPED' in text
