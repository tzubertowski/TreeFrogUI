import pytest
from analyze_physical_capture import analyze, ORDER


def capture():
    lines = ['run_id=fresh', 'R36 INPUT INVENTORY V1', 'input_capture_ms=60000']
    for i in range(len(ORDER)):
        lines += [f'input_event device=r36-serial-keys code={704+i} value=1',
                  f'input_event device=r36-serial-keys code={704+i} value=0']
    lines += ['input_inventory=PASS', 'input_events_recorded=36 dropped=0',
              'R36 INPUT INVENTORY END', 'input_probe_rc=0',
              'probe_rc=0 errno=0', 'R36 DISPLAY PROBE END']
    return ('\n'.join(lines) + '\n').encode()


def test_all18_complete_human_confirmed_pairs():
    result = analyze(capture(), 'fresh', True)
    assert result['physical_labels_verified'] and len(result['labels']) == 18
    assert result['labels'][-1]['physical'] == 'POWER'
    assert not result['legacy_bits_assigned'] and not result['navigation_verified']


def test_no_labels_without_human_confirmation_or_fresh_identity():
    assert not analyze(capture(), 'fresh')['labels']
    assert not analyze(capture(), 'stale', True)['labels']


@pytest.mark.parametrize('old,new', [
    (b'code=704 value=0', b'code=705 value=0'),
    (b'code=705', b'code=704'),
    (b'input_inventory=PASS', b'input_inventory=FAIL'),
    (b'dropped=0', b'dropped=1'),
    (b'input_events_recorded=36', b'input_events_recorded=35'),
    (b'code=721 value=0\n', b'code=721 value=2\n'),
])
def test_incomplete_repeated_or_dropped_capture_gets_no_positional_labels(old, new):
    result = analyze(capture().replace(old, new), 'fresh', True)
    assert not result['physical_labels_verified'] and result['labels'] == []


def test_kernel_repeat_allowed_only_with_matching_held_key():
    raw = capture().replace(b'code=704 value=0', b'code=704 value=2\ninput_event device=r36-serial-keys code=704 value=0').replace(b'recorded=36', b'recorded=37')
    assert analyze(raw, 'fresh', True)['physical_labels_verified']
