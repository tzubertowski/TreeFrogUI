"""Tests for on-console Check Disk (r36_chkdsk_console.c / r36_chkdsk_console.h) and MIPS build."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
ZIG = Path(r"C:\Users\palpa\Tools\zig-x86_64-windows-0.17.0\zig.exe")


def test_r36_chkdsk_kmsg_detector_safety_refusal_and_repair_lifecycle(tmp_path):
    src = ROOT / "scripts/kernel_lab/r36_chkdsk_console.c"
    kmsg_clean = tmp_path / "kmsg_clean.txt"
    kmsg_clean.write_text(
        "6,10,1000,-;mmc0: new high speed SDXC card at address 0001\n"
        "4,11,1200,-;FAT-fs (mmcblk0p1): utf8 is not a recommended IO charset\n"
    )
    kmsg_dirty = tmp_path / "kmsg_dirty.txt"
    kmsg_dirty.write_text(
        "6,10,1000,-;mmc0: new high speed SDXC card at address 0001\n"
        "4,12,1300,-;FAT-fs (mmcblk0p1): Volume was not properly unmounted. Some data may be corrupt. Please run fsck.\n"
    )

    harness = tmp_path / "chkdsk_test.c"
    harness.write_text(
        f'''
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int host_open(const char *p, int flags, ...) {{
    (void)flags;
    if (!strcmp(p, "/dev/fb0")) return 90;
    return open(p, flags);
}}
static int host_close(int fd) {{
    if (fd == 90) return 0;
    return close(fd);
}}
static ssize_t host_write(int fd, const void *buf, size_t count) {{ return write(fd, buf, count); }}

static uint16_t mock_fb[640 * 480];
static int fb_draws = 0;
static void *mock_mmap(void *addr, size_t len, int prot, int flags, int fd, long off) {{
    (void)addr; (void)prot; (void)flags; (void)off;
    assert(fd == 90 && len == sizeof(mock_fb));
    return mock_fb;
}}
static int mock_munmap(void *addr, size_t len) {{
    assert(addr == mock_fb && len == sizeof(mock_fb));
    fb_draws++;
    return 0;
}}

#define R36_CHKDSK_MOCK 1
#define R36_CHKDSK_LIBRARY_ONLY 1

static int mock_swap_is_active = 1;
static int mock_is_mounted = 1;
static int mock_umount_fails = 0;
static int mock_snapshot_fails = 0;
static int mock_wdt_paused = 0;
static int mock_fsck_calls = 0;
static int mock_fsck_repair_calls = 0;
static int mock_fsck_forged_marker = 0;
static int mock_dirty = 1;
static int mock_remounts = 0;
static int mock_swapons = 0;

struct r36_chkdsk_opts;
static int r36_chkdsk_swap_active(const char *swaps_path, const char *swapfile) {{
    (void)swaps_path; (void)swapfile; return mock_swap_is_active;
}}
static int r36_chkdsk_block_offline(const struct r36_chkdsk_opts *o);
static int r36_chkdsk_pause_watchdog(void) {{ mock_wdt_paused = 1; return 0; }}
static void r36_chkdsk_resume_watchdog(void) {{ mock_wdt_paused = 0; }}
static int r36_chkdsk_snapshot(const char *dev, const char *snap) {{
    (void)dev; (void)snap; return mock_snapshot_fails ? -1 : 0;
}}

static int mock_swapoff(const char *p) {{ (void)p; mock_swap_is_active = 0; return 0; }}
static int mock_swapon(const char *p, int flags) {{ (void)p; (void)flags; mock_swap_is_active = 1; mock_swapons++; return 0; }}
static int mock_umount2(const char *target, int flags) {{
    (void)target; (void)flags;
    if (mock_umount_fails) {{ errno = EBUSY; return -1; }}
    mock_is_mounted = 0;
    return 0;
}}
static int mock_mount(const char *src, const char *tgt, const char *fs, unsigned long fl, const void *data) {{
    (void)src; (void)tgt; (void)fs; (void)fl; (void)data;
    mock_is_mounted = 1;
    mock_remounts++;
    return 0;
}}
static void mock_sync(void) {{}}

static int r36_chkdsk_exec_fsck(const char *tool, const char *dev, int repair, int *signalled) {{
    (void)tool; (void)dev;
    *signalled = 0;
    mock_fsck_calls++;
    assert(!mock_is_mounted && !mock_swap_is_active);
    if (mock_fsck_forged_marker) return -1;
    if (repair) {{
        assert(mock_wdt_paused == 1);
        mock_fsck_repair_calls++;
        mock_dirty = 0;
        return 1;
    }}
    return mock_dirty ? 1 : 0;
}}

#define open    host_open
#define close   host_close
#define write   host_write
#define mmap    mock_mmap
#define munmap  mock_munmap
#define swapoff mock_swapoff
#define swapon  mock_swapon
#define umount2 mock_umount2
#define mount   mock_mount
#define sync    mock_sync

#include "{src.as_posix()}"

static int r36_chkdsk_block_offline(const struct r36_chkdsk_opts *o) {{
    (void)o;
    return (!mock_is_mounted && !mock_swap_is_active) ? 1 : 0;
}}

int main(void) {{
    /* 1. Kernel FS / memory error detector */
    assert(r36_kmsg_line_indicates_fs_error("mmc0: new high speed SDXC card") == 0);
    assert(r36_kmsg_line_indicates_fs_error("FAT-fs (mmcblk0p1): utf8 is not a recommended IO charset") == 0);
    assert(r36_kmsg_line_indicates_fs_error("FAT-fs (mmcblk0p1): Volume was not properly unmounted. Some data may be corrupt.") == 1);
    assert(r36_kmsg_line_indicates_fs_error("Buffer I/O error on dev mmcblk0p1, logical block 0") == 1);
    assert(r36_kmsg_line_indicates_fs_error("EXT4-fs error (device loop0): ext4_lookup") == 1);

    struct r36_chkdsk_opts opts;
    r36_chkdsk_default_opts(&opts);
    opts.tty_path = NULL;

    /* 2. --if-kernel-error skips when kmsg has no FS error */
    opts.require_kmsg_error = 1;
    opts.kmsg_path = "{kmsg_clean.as_posix()}";
    assert(r36_chkdsk_run(&opts) == R36_CHKDSK_NO_ERROR_DETECTED);
    assert(mock_fsck_calls == 0);

    /* 3. Safety refusal if SD cannot be unmounted */
    opts.kmsg_path = "{kmsg_dirty.as_posix()}";
    mock_umount_fails = 1;
    mock_is_mounted = 1;
    assert(r36_chkdsk_run(&opts) == R36_CHKDSK_REFUSED_MOUNTED);
    assert(mock_fsck_calls == 0);

    /* 4. Missing/forged completion marker aborts without repairing */
    mock_umount_fails = 0;
    mock_is_mounted = 1;
    mock_swap_is_active = 1;
    mock_fsck_forged_marker = 1;
    assert(r36_chkdsk_run(&opts) == R36_CHKDSK_CHECK_FAILED);
    assert(mock_fsck_repair_calls == 0);

    /* 5. Full safe chkdsk: swapoff -> umount -> check(1) -> pause wdt -> repair(1) -> verify(0) -> resume wdt -> remount -> swapon */
    mock_fsck_forged_marker = 0;
    mock_fsck_calls = 0;
    mock_dirty = 1;
    mock_is_mounted = 1;
    mock_swap_is_active = 1;
    assert(r36_chkdsk_run(&opts) == R36_CHKDSK_REPAIRED_VERIFIED);
    assert(mock_fsck_calls == 3 && mock_fsck_repair_calls == 1);
    assert(mock_wdt_paused == 0 && mock_is_mounted == 1 && mock_swap_is_active == 1);
    assert(mock_remounts >= 1 && mock_swapons >= 1);
    assert(fb_draws >= 4);
    assert(mock_fb[0] == 0x0260u);          /* OK green background on completion */
    assert(mock_fb[308 * 640 + 60] == 0x07E0u); /* 100% progress bar green */

    /* 6. Clean pass runs check only, no repair */
    mock_fsck_calls = 0;
    mock_fsck_repair_calls = 0;
    opts.require_kmsg_error = 0;
    assert(r36_chkdsk_run(&opts) == R36_CHKDSK_CLEAN);
    assert(mock_fsck_calls == 1 && mock_fsck_repair_calls == 0);

    puts("R36_CHKDSK_CONSOLE=PASS");
    return 0;
}}
'''
    )

    exe = tmp_path / "chkdsk_test.exe"
    subprocess.run(
        [
            "gcc",
            "-std=gnu11",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{(ROOT / 'scripts/kernel_lab')}",
            str(harness),
            "-o",
            str(exe),
        ],
        check=True,
        capture_output=True,
        timeout=20,
    )
    res = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=5)
    assert "R36_CHKDSK_CONSOLE=PASS" in res.stdout

    if ZIG.exists():
        mips_elf = tmp_path / "r36-chkdsk.elf"
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
