from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'boot_crypto'))
from peripheral_result import frontend_backend_result
RAW=(b'R36 FRONTEND BACKEND PROBE V1\nrun_id=fresh\nrelease=7.2.0-rc5-r36disp\n'
     b'frontend_module_load_rc=0\nFRONTEND_ABI_DRM_HARNESS=PASS\n'
     b'frontend_child_exit=0 signalled=0\nfrontend_probe_rc=0\nfull_UI_verified=0\nR36 FRONTEND BACKEND PROBE END\n')

def test_real_backend_not_full_UI():
    r=frontend_backend_result(RAW,'fresh','7.2.0-rc5-r36disp')
    assert r['video_backend_verified'] and not r['full_UI_verified'] and not r['real_games_verified']

@pytest.mark.parametrize('raw',[RAW+b'trailing\n',RAW.replace(b'run_id=fresh',b'run_id=old'),RAW.replace(b'frontend_child_exit=0',b'frontend_child_exit=1'),RAW.replace(b'FRONTEND_ABI_DRM_HARNESS=PASS\n',b'')])
def test_failed_partial_or_stale_backend_never_pass(raw):
    assert not frontend_backend_result(raw,'fresh','7.2.0-rc5-r36disp')['video_backend_verified']
