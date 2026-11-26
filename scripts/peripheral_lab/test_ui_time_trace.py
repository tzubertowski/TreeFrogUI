from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def test_trace_observes_time_without_altering_delays():
    text=(ROOT/'scripts/peripheral_lab/ui_time_trace.c').read_text()
    assert 'RTLD_NEXT,"nanosleep"' in text
    assert 'RTLD_NEXT,"clock_gettime"' in text
    assert 'real_nanosleep(request,remaining)' in text
    assert 'real_usleep(microseconds)' in text
    assert 'real_clock_gettime(clock,value)' in text
    assert 'real_gettimeofday(value,zone)' in text
    assert '>=160' in text
    assert 'clock_settime' not in text
    assert 'request->tv_sec =' not in text and 'request->tv_nsec =' not in text
    assert 'static __thread unsigned int thread_records' in text
    assert 'microseconds>100000' in text and 'request->tv_sec>0' in text
    assert 'SYS_gettid' in text


def test_trace_preload_is_child_only_and_opt_in():
    text=(ROOT/'scripts/peripheral_lab/ui_console_init.c').read_text()
    begin=text.index('if(!child){')
    preload=text.index('setenv("LD_PRELOAD"')
    execute=text.index('execl("/sd/rootfs/lib/ld.so.1"',begin)
    assert begin<preload<execute
    assert '#elif defined(R36_UI_TIME_TRACE)' in text
    assert '#error "Use one diagnostic preload at a time"' in text
