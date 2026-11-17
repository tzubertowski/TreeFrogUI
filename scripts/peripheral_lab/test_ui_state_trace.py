import pytest
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from verify_ui_state_trace import state_result
from test_ui_core_trace import cases
from prepare_ui_state_profile import header, profile


def test_empty_field_profile_is_rejected_before_reading_binary():
    with pytest.raises(ValueError, match='at least one field'):
        profile(Path('not-opened.so'), ())


def state_cases():
    control, traced = cases()
    lines = [
        'ui-state: profile_bound build_id=test',
        'ui-state: run=1 phase=enter counter=0 flag=0',
        'ui-state: run=1 phase=leave counter=1 flag=1',
        'ui-state: run=2 phase=enter counter=1 flag=1',
        'ui-state: run=2 phase=leave counter=2 flag=1',
    ]
    valid = dict(traced, stderr='\n'.join(lines) + '\n' + traced['stderr'])
    rejected = dict(traced, stderr='ui-state: profile_rejected observation_disabled=1\n' + traced['stderr'])
    return control, valid, rejected


def test_state_forwarding_and_wrong_profile_control():
    assert state_result(*state_cases())


def test_empty_fields_and_unreadable_state_are_rejected():
    control, valid, rejected = state_cases()
    valid['stderr'] = valid['stderr'].replace(' counter=0 flag=0', '')
    assert not state_result(control, valid, rejected)
    control, valid, rejected = state_cases()
    valid['stderr'] = valid['stderr'].replace('counter=1', 'counter=UNREADABLE')
    assert not state_result(control, valid, rejected)


def test_wrong_profile_must_not_read_state():
    control, valid, rejected = state_cases()
    rejected['stderr'] += 'ui-state: run=1 phase=enter counter=0 flag=0\n'
    assert not state_result(control, valid, rejected)


def test_observer_is_read_only_and_uses_bounded_profile():
    text = (HERE / 'ui_state_trace.h').read_text()
    assert 'O_RDONLY | O_CLOEXEC' in text
    assert 'pread(state_memory' in text
    assert 'pwrite' not in text and 'PROT_WRITE' not in text
    assert 'state_file_matches(info->dli_fname)' in text
    assert 'memcmp(signature' in text and 'memcmp(note' in text
    assert 'count % 600' in text


def test_profile_header_has_file_identity_and_fields():
    data = {'file_fnv64': 1, 'file_bytes': 100, 'run_offset': 4, 'note_offset': 8,
            'build_id': 'test', 'run_signature': '01020304', 'note_bytes': '05060708',
            'fields': [{'label': 'counter', 'offset': 12, 'size': 4}]}
    text = header(data)
    assert 'R36_STATE_FILE_BYTES 100u' in text
    assert '{"counter", 12u, 4u}' in text
