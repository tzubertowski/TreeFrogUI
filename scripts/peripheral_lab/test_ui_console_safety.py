from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def test_ui_bootstrap_is_readonly_and_does_not_fake_IO():
    text=(ROOT/'scripts/peripheral_lab/ui_console_init.c').read_text()
    assert 'MS_RDONLY|MS_NOATIME' in text
    assert 'menu_sounds=off' in text
    assert 'MS_BIND' in text and '/tmp/r36-ui-settings.txt' in text
    assert 'PICOARCH_DRIVER' in text
    assert '"/sd/cubegm/picoarch"' in text and 'frogui_libretro.so' in text
    assert '*keys=0' in text and 'IPC_CREAT|IPC_EXCL' in text
    assert 'navigation_verified=0' in text and 'audio_verified=0' in text
    assert 'UI_visual_confirmation=REQUIRED' in text
    assert 'watchdog' not in text.lower() or 'pause' in text
    assert '/sysrq-trigger' not in text and 'system(' not in text
    assert 'SNDRV' not in text and 'cubevol' not in text


def test_report_rw_only_after_child_group_cleanup():
    text=(ROOT/'scripts/peripheral_lab/ui_console_init.c').read_text()
    assert text.index('waitpid(-child,&helper_status,0)') < text.index('MS_REMOUNT,')
    assert 'if(!done&&got!=child)goto wait_reset;' in text
    assert 'setpgid(child,child)' in text
    assert 'kill(-child,SIGTERM)' in text and 'kill(-child,SIGKILL)' in text
    assert 'MS_REMOUNT|MS_RDONLY' in text


def test_sparse_BSS_policy_is_RAM_only_bounded_not_SD_swap():
    text=(ROOT/'scripts/peripheral_lab/ui_console_init.c').read_text()
    assert '/proc/sys/vm/overcommit_memory' in text
    assert 'setrlimit(RLIMIT_AS,&address_limit)' in text
    assert '192u*1024u*1024u' in text
    assert 'swapon(' not in text
    assert 'ui_memory=%s' in text


def test_observation_has_bounded_window_and_thread_samples():
    text=(ROOT/'scripts/peripheral_lab/ui_console_init.c').read_text()
    assert '#define R36_UI_WINDOW_TICKS 160' in text
    assert 'tick<R36_UI_WINDOW_TICKS' in text and 'tick==40||tick==80||tick==120' in text
    assert 'R36_UI_WINDOW_TICKS > 600' in text
    assert '/task/%.32s/wchan' in text
    assert 'usleep(100000)' in text
    assert 'r36-wdt' not in text


def test_direct_exec_preserves_original_interpreter_and_resource_paths():
    text=(ROOT/'scripts/peripheral_lab/ui_console_init.c').read_text()
    assert '#ifdef R36_UI_DIRECT_EXEC' in text
    assert 'execl("/mnt/sdcard/cubegm/picoarch","/mnt/sdcard/cubegm/picoarch"' in text
    assert 'chdir("/mnt/sdcard/cubegm")' in text
    for name in ('bin','sbin','etc'):
        assert f'symlink("/sd/rootfs/{name}","/{name}")' in text
    assert '"/sbin/init"' not in text


def test_stdio_fds_reserved_before_kmsg_and_report_dup2():
    text=(ROOT/'scripts/peripheral_lab/ui_console_init.c').read_text()
    devtmpfs=text.index('mount("devtmpfs","/dev"')
    devnull=text.index('open("/dev/null",O_RDWR)')
    kmsg=text.index('open("/dev/kmsg",O_WRONLY|O_CLOEXEC)')
    report=text.index('open("/tmp/ui-report.txt"')
    assert devtmpfs < devnull < kmsg < report
    assert 'F_DUPFD_CLOEXEC,3' in text
    assert 'if(fd>2)close(fd);' in text

