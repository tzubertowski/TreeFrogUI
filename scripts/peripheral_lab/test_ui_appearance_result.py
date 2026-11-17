from pathlib import Path
import sys

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'boot_crypto'))
from peripheral_result import ui_appearance_result

RAW=(b'R36 UNCHANGED UI PROBE V1\nrun_id=fresh\nrelease=7.2.0-rc5-r36disp\n'
     b'ui_module_load_rc=0\nui_alive_at_deadline=1\nui_child_exit=-1 signalled=1\n'
     b'navigation_verified=0\naudio_verified=0\nUI_visual_confirmation=REQUIRED\nR36 UNCHANGED UI PROBE END\n')
CHILD=b'r36-drm: submitted_frames=1 source=640x480 pitch=1280\nr36-drm: submitted_frames=60 source=640x480 pitch=1280\n'


def test_frame_evidence_does_not_claim_physical_UI_navigation_or_audio():
    r=ui_appearance_result(RAW,CHILD,'fresh','7.2.0-rc5-r36disp')
    assert r['UI_process_and_frame_evidence'] and r['frames_logged']==60
    assert r['physical_visual_confirmation_required']
    assert not r['full_UI_verified'] and not r['navigation_verified'] and not r['audio_verified']


@pytest.mark.parametrize('raw,child',[(RAW,b''),(RAW.replace(b'ui_alive_at_deadline=1',b'ui_alive_at_deadline=0'),CHILD),(RAW+b'trailing',CHILD),(RAW.replace(b'run_id=fresh',b'run_id=old'),CHILD)])
def test_missing_stale_crashed_or_truncated_UI_not_accepted(raw,child):
    assert not ui_appearance_result(raw,child,'fresh','7.2.0-rc5-r36disp')['UI_process_and_frame_evidence']


def test_frame_before_core_load_failure_does_not_pass_UI_evidence():
    child=CHILD+b'TFDBG core_open dlopen failed: cannot map zero-fill pages\n'
    assert not ui_appearance_result(RAW,child,'fresh','7.2.0-rc5-r36disp')['UI_process_and_frame_evidence']
