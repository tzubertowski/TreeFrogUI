import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('verify_ui_core_trace', Path(__file__).with_name('verify_ui_core_trace.py'))
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def cases():
    control = {'exit': 0, 'stdout': 'CORE_TRACE_FORWARDING=PASS\n', 'stderr': ''}
    traced = {'exit': 0, 'stdout': control['stdout'], 'stderr': '\n'.join((
        'ui-core: video_callback_installed=1',
        'ui-core: run_enter=1 videos=0',
        'ui-core: video=1 RGB565_hash=b0429dc4 nonzero_bytes=1',
        'ui-core: run_leave=1 videos=1',
        'ui-core: run_enter=2 videos=1',
        'ui-core: video=2 RGB565_hash=d0271dc7 nonzero_bytes=1',
        'ui-core: run_leave=2 videos=2',
        'ui-core: video_callback_installed=0',
    )) + '\n'}
    return control, traced


def test_forwarding_result_accepts_only_observed_exact_forwarding():
    assert VERIFY.forwarding_result(*cases())


def test_harness_pass_without_loaded_observer_is_not_trace_pass():
    control, traced = cases()
    traced['stderr'] = ''
    assert not VERIFY.forwarding_result(control, traced)


def test_frame_corruption_or_failed_process_is_rejected():
    control, traced = cases()
    traced['stderr'] = traced['stderr'].replace('d0271dc7', '00000000')
    assert not VERIFY.forwarding_result(control, traced)
    control, traced = cases()
    control['exit'] = 1
    assert not VERIFY.forwarding_result(control, traced)


def test_preload_is_child_only_exclusive_opt_in():
    text = (ROOT / 'scripts/peripheral_lab/ui_console_init.c').read_text()
    child = text.index('if(!child){')
    preload = text.index('setenv("LD_PRELOAD","/sd/cubegm/r36-ui-core-trace.so"')
    execute = text.index('#ifdef R36_UI_DIRECT_EXEC')
    assert child < preload < execute
    assert '#elif defined(R36_UI_CORE_TRACE)' in text
    assert '#error "Use one diagnostic preload at a time"' in text
    assert 'MS_RDONLY|MS_NOATIME' in text


def test_observer_forwards_original_calls_without_input_override():
    text = (ROOT / 'scripts/peripheral_lab/ui_core_trace.c').read_text()
    assert 'core_run();' in text
    assert 'core_set_video(callback ? observe_video : NULL);' in text
    assert 'frontend_video(data, w, h, pitch);' in text
    assert 'retro_set_input' not in text
    assert 'dlvsym(RTLD_NEXT, "dlsym", "GLIBC_2.0")' in text
