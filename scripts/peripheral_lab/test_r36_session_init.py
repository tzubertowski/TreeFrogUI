"""Verify full Linux 7.2 session supervisor (r36_session_init.c) and MIPS32r2 static build."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ZIG = Path(r"C:\Users\palpa\Tools\zig-x86_64-windows-0.17.0\zig.exe")


def test_r36_session_init_bootstrap_launch_and_shutdown(tmp_path):
    src = ROOT / "scripts/peripheral_lab/r36_session_init.c"
    tfenv = tmp_path / "tfdevice.env"
    launch = tmp_path / "frogui_launch.txt"
    pwr_flag = tmp_path / "poweroff.req"
    drv = tmp_path / "driver_r36_combined.so"
    drv.write_bytes(b"ELF")

    harness = tmp_path / "session_test.c"
    harness.write_text(
        f'''
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int host_open(const char *p, int flags, ...) {{ (void)flags; return open(p, flags); }}
static int host_close(int fd) {{ return close(fd); }}
static ssize_t host_write(int fd, const void *buf, size_t count) {{ return write(fd, buf, count); }}
static int host_unlink(const char *p) {{ return unlink(p); }}

#define R36_SESSION_MOCK 1
#define R36_SESSION_LIBRARY_ONLY 1

static int mock_chkdsk_rc = 0;
static int mock_mount_calls = 0;
static int mock_umount_calls = 0;
static int mock_swapoff_calls = 0;
static int mock_reboot_calls = 0;
static int next_pid = 100;
static int fork_seq = 0;
static char spawned_cmds[16][128];
static int spawned_count = 0;
static int stopped_pids[16];
static int stopped_count = 0;

static int mock_access(const char *p, int mode) {{
    (void)mode;
    if (!strcmp(p, "/dev/mmcblk0p1")) return 0;
    if (!strcmp(p, "/sbin/r36-chkdsk")) return 0;
    if (!strcmp(p, "/sbin/r36-sysd")) return 0;
    if (!strcmp(p, "/mnt/sdcard/cubegm/r36-legacy-keys")) return 0;
    if (!strcmp(p, "/sbin/r36-usb-mtp-adb")) return 0;
    if (!strcmp(p, "{drv.as_posix()}")) return 0;
    if (!strcmp(p, "{pwr_flag.as_posix()}")) return access(p, mode);
    return -1;
}}

static int mock_mount(const char *s, const char *t, const char *fs, unsigned long fl, const void *d) {{
    (void)s; (void)t; (void)fs; (void)fl; (void)d;
    mock_mount_calls++;
    return 0;
}}
static int mock_umount(const char *t) {{ (void)t; mock_umount_calls++; return 0; }}
static int mock_swapoff(const char *s) {{ (void)s; mock_swapoff_calls++; return 0; }}
static int mock_reboot(unsigned int cmd) {{ (void)cmd; mock_reboot_calls++; return 0; }}
static int mock_chdir(const char *p) {{ (void)p; return 0; }}
static void mock_sync(void) {{}}
static int mock_usleep(unsigned int u) {{ (void)u; return 0; }}
static int mock_setenv(const char *k, const char *v, int ov) {{ (void)k; (void)v; (void)ov; return 0; }}
static int mock_fork(void) {{ fork_seq++; return ++next_pid; }}
static int mock_execv(const char *p, char *const argv[]) {{ (void)p; (void)argv; return 0; }}
static int mock_kill(int pid, int sig) {{ (void)sig; stopped_pids[stopped_count++] = pid; return 0; }}
static int mock_waitpid(int pid, int *st, int opts) {{
    (void)opts;
    if (st) {{
        int rc = (spawned_count == 1) ? mock_chkdsk_rc : 0;
        *st = (rc & 0xff) << 8;
    }}
    return (opts != 0) ? 0 : pid;
}}

/* Override r36_spawn_prog cleanly by wrapping fork/waitpid via mock_spawn trace */
#define open    host_open
#define close   host_close
#define write   host_write
#define unlink  host_unlink
#define access  mock_access
#define mount   mock_mount
#define umount  mock_umount
#define swapoff mock_swapoff
#define reboot  mock_reboot
#define chdir   mock_chdir
#define sync    mock_sync
#define usleep  mock_usleep
#define setenv  mock_setenv
#define fork    mock_fork
#define execv   mock_execv
#define kill    mock_kill
#define waitpid mock_waitpid

/* Capture spawned argv[0] via macro intercept of r36_spawn_prog? Better: wrap after include! */
#include "{src.as_posix()}"

int main(void) {{
    struct r36_session_cfg cfg;
    struct r36_session_ctx ctx;
    (void)spawned_cmds; (void)fork_seq;

    r36_session_default_cfg(&cfg);
    cfg.driver_so = "{drv.as_posix()}";
    cfg.tfdevice_env_path = "{tfenv.as_posix()}";
    cfg.launch_file = "{launch.as_posix()}";
    cfg.poweroff_flag = "{pwr_flag.as_posix()}";

    /* 1. Failed pre-mount chkdsk MUST abort before mount() is ever called */
    mock_chkdsk_rc = 2;
    spawned_count = 1;
    assert(r36_session_bootstrap(&ctx, &cfg) == -2);
    assert(mock_mount_calls == 0 && ctx.sd_mounted == 0);

    /* 2. Clean bootstrap mounts SD, writes /tmp/tfdevice.env, spawns sysd + keys + usb */
    mock_chkdsk_rc = 0;
    spawned_count = 0;
    assert(r36_session_bootstrap(&ctx, &cfg) == 0);
    assert(mock_mount_calls == 1 && ctx.sd_mounted == 1);
    assert(ctx.sysd_pid > 0 && ctx.keys_pid > 0 && ctx.usb_pid > 0);

    /* 3. Step 1 launches UI */
    assert(r36_session_step(&ctx) == 0);
    assert(ctx.ui_pid > 0);
    int first_ui_pid = ctx.ui_pid;

    /* 4. Launch request stops UI, runs core synchronously, and restarts UI */
    FILE *lf = fopen("{launch.as_posix()}", "w");
    assert(lf != NULL);
    fprintf(lf, "libretro\\n/mnt/sdcard/cubegm/cores/gambatte_libretro.so\\n/mnt/sdcard/roms/gb/test.gb\\n");
    fclose(lf);
    assert(r36_session_step(&ctx) == 0);
    assert(ctx.ui_pid > first_ui_pid);
    assert(stopped_count >= 1 && stopped_pids[0] == first_ui_pid);

    /* 5. Poweroff request cleanly stops all children, swapoff, umount, RB_POWER_OFF */
    FILE *pf = fopen("{pwr_flag.as_posix()}", "w");
    assert(pf != NULL);
    fputs("1\\n", pf);
    fclose(pf);
    assert(r36_session_step(&ctx) == 1 && ctx.shutdown_requested == 1);
    assert(r36_session_shutdown(&ctx) == 0);
    assert(mock_swapoff_calls == 1 && mock_umount_calls == 1 && mock_reboot_calls == 1);
    assert(ctx.sd_mounted == 0 && ctx.sysd_pid == 0 && ctx.keys_pid == 0 && ctx.usb_pid == 0 && ctx.ui_pid == 0);

    puts("R36_SESSION_INIT=PASS");
    return 0;
}}
'''
    )

    exe = tmp_path / "session_test.exe"
    subprocess.run(
        ["gcc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", str(harness), "-o", str(exe)],
        check=True,
        capture_output=True,
        timeout=20,
    )
    res = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=5)
    assert "R36_SESSION_INIT=PASS" in res.stdout
    assert "TF_DEVICE=GB350" in tfenv.read_text()

    if ZIG.exists():
        mips_elf = tmp_path / "r36-session-init.elf"
        subprocess.run(
            [
                str(ZIG),
                "cc",
                "-target",
                "mipsel-linux.4.4-musleabi",
                "-march=mips32r2",
                "-msoft-float",
                "-static",
                "-Os",
                "-Wall",
                "-Wextra",
                "-Werror",
                str(src),
                "-o",
                str(mips_elf),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        assert mips_elf.stat().st_size > 0
