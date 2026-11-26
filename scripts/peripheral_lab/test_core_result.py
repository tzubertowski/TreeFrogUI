from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'boot_crypto'))
from peripheral_result import core_result

RAW=(b'run_id=fresh\nkernel=7.2.0-rc5-r36lab #12\nR36 DISPLAY PROBE V1\n'
     b'R36 CORE CONSOLE PROBE V1\ncore_begin=gambatte\nLIBRETRO_SYNTHETIC_EXECUTION=PASS\ncore_end=gambatte exit=0 signalled=0\n'
     b'core_begin=fceumm\nLIBRETRO_SYNTHETIC_EXECUTION=PASS\ncore_end=fceumm exit=0 signalled=0\n'
     b'console_core_execution=PASS\nR36 CORE CONSOLE PROBE END\ncore_probe_rc=0\nprobe_rc=0 errno=0\nR36 DISPLAY PROBE END\n')


def test_headless_is_not_full_UI_or_physical_IO():
    r=core_result(RAW,'fresh','7.2.0-rc5-r36lab')
    assert r['headless_core_execution_verified']
    assert not r['full_UI_verified'] and not r['physical_video_audio_input_verified'] and not r['real_games_verified']


@pytest.mark.parametrize('raw',[
    RAW.replace(b'run_id=fresh',b'run_id=old'), RAW+b'trailing\n',
    RAW.replace(b'core_end=fceumm exit=0',b'core_end=fceumm exit=1'),
    RAW.replace(b'LIBRETRO_SYNTHETIC_EXECUTION=PASS\n',b'',1),
    RAW.replace(b'R36 CORE CONSOLE PROBE END\n',b''),
])
def test_partial_core_execution_never_passes(raw):
    assert not core_result(raw,'fresh','7.2.0-rc5-r36lab')['headless_core_execution_verified']
