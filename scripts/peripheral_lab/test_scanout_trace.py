from pathlib import Path
import subprocess
import shutil
import sys

import pytest
from scanout_result import scanout_result

HERE = Path(__file__).resolve().parent


def log():
    return ('ui-core: video=1 RGB565_hash=0f4e3334 nonzero_bytes=585299\n'
            'r36-scanout: callback_source=0f4e3334 scaled_target=0f4e3334 identity_geometry=1\n'
            + ''.join(('r36-scanout: phase=%s active=02f90400 programmed=02f90400 boot=02f92a80 pixel=01500000 format=6 size=640x480 pitch=1280 on=1 timing=1 timeouts=0\n'
                       'r36-scanout: phase=%s expected=0f4e3334 mapped=0f4e3334 dma=0f4e3334 raster_progress=1 digital_match=1 physical_visual=NOT_TESTED\n') % (p, p)
                      for p in ('first', 'before_cleanup')))


def test_digital_only_both_phases_required():
    result = scanout_result(log())
    assert result['digital_chain_verified']
    assert not result['physical_visual_verified']
    partial = scanout_result(log().split('r36-scanout: phase=before_cleanup')[0])
    assert not partial['digital_chain_verified']
    assert partial['first_frame_verified']


@pytest.mark.parametrize('old,new', [('dma=0f4e3334', 'dma=00000000'),
                                    ('raster_progress=1', 'raster_progress=0'),
                                    ('digital_match=1', 'digital_match=0'),
                                    ('programmed=02f90400', 'programmed=02f90420'),
                                    ('pixel=01500000', 'pixel=1883a000'),
                                    ('nonzero_bytes=585299', 'nonzero_bytes=0'),
                                    ('RGB565_hash=0f4e3334', 'RGB565_hash=00000000')])
def test_bad_evidence_rejected(old, new):
    assert not scanout_result(log().replace(old, new))['digital_chain_verified']


def test_duplicate_and_failure_rejected():
    assert not scanout_result(log() + log())['digital_chain_verified']
    assert not scanout_result(log() + 'observation_failed=1')['digital_chain_verified']


def test_opt_in_observation_never_writes_physical_memory():
    text = (HERE / 'video_scanout_trace.h').read_text()
    assert 'O_RDONLY | O_SYNC | O_CLOEXEC' in text
    assert 'PROT_READ, MAP_SHARED' in text
    assert 'PROT_WRITE' not in text and 'pwrite' not in text
    backend = (HERE / 'video_drm_backend.c').read_text()
    assert '#ifdef R36_SCANOUT_TRACE' in backend
    assert backend.index('scanout_trace("before_cleanup"') < backend.index('    cleanup();', backend.index('void video_driver_deinit'))


def test_live_phase_requires_actual_late_timing_and_one_frame():
    text = log().replace('before_cleanup', 'late_live')
    assert not scanout_result(text, 'late_live')['digital_chain_verified']
    text += 'ui-live: checkpoint_elapsed_ms=10025 run=9000\nr36-scanout: live_submitted_frames=1\n'
    assert scanout_result(text, 'late_live')['digital_chain_verified']
    assert not scanout_result(text.replace('10025', '25'), 'late_live')['digital_chain_verified']
    assert not scanout_result(text.replace('live_submitted_frames=1', 'live_submitted_frames=2'), 'late_live')['digital_chain_verified']


def test_checkpoint_only_observes_already_loaded_driver_after_real_core_run():
    text = (HERE / 'ui_live_checkpoint.h').read_text()
    assert 'RTLD_NOLOAD' in text and 'CLOCK_MONOTONIC' in text
    assert '10000000000LL' in text and 'checkpoint_attempted = 1' in text
    assert 'pthread_create' not in text and 'usleep(' not in text
    observer = (HERE / 'ui_core_trace.c').read_text()
    assert observer.index('core_run();') < observer.index('checkpoint_poll(count);')


def test_actual_c_observer_negative_controls(tmp_path):
    if sys.platform != 'linux' or not shutil.which('gcc'):
        pytest.skip('requires native Linux GCC/sys/mman.h; WSL run recorded separately')
    binary = tmp_path / 'scanout-test.exe'
    subprocess.run(['gcc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                    str(HERE / 'video_scanout_trace_test.c'), '-o', str(binary)], check=True)
    p = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
    assert 'SCANOUT_OBSERVER_MOCK=PASS' in p.stdout
    assert 'phase=match expected=' in p.stderr and 'digital_match=1' in p.stderr
    assert 'phase=corrupt expected=' in p.stderr and 'digital_match=0' in p.stderr
    assert 'phase=bad_health observation_failed=1' in p.stderr
    assert 'phase=no_memory observation_failed=1' in p.stderr
