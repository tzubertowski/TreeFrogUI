/* SPDX-License-Identifier: GPL-2.0
 * On-console Check Disk (chkdsk-style) utility for R36S FAT32 SD card:
 *  - Detects kernel /dev/kmsg filesystem/card errors after abrupt poweroffs
 *  - Safely swapoff + unmounts /mnt/sdcard before touching /dev/mmcblk0p1
 *  - Refuses to run fsck if device remains mounted or exclusively held
 *  - Takes pre-repair 8 MiB metadata snapshot, pauses watchdog during repair,
 *    runs patched r36-fsck-cp437-v2 (-c 437 -a -f), verifies (-c 437 -n),
 *    resumes watchdog, and remounts /mnt/sdcard cleanly.
 */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#ifndef _FILE_OFFSET_BITS
#define _FILE_OFFSET_BITS 64
#endif

#include <errno.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef R36_CHKDSK_MOCK
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/swap.h>
#include <sys/sysmacros.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#else
#ifndef O_RDONLY
#define O_RDONLY 0
#endif
#ifndef O_WRONLY
#define O_WRONLY 1
#endif
#ifndef O_RDWR
#define O_RDWR 2
#endif
#ifndef O_CREAT
#define O_CREAT 0x40
#endif
#ifndef O_EXCL
#define O_EXCL 0x80
#endif
#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif
#ifndef O_SYNC
#define O_SYNC 0
#endif
#ifndef STDOUT_FILENO
#define STDOUT_FILENO 1
#endif
#ifndef WIFEXITED
#define WIFEXITED(s) (((s) & 0x7f) == 0)
#define WEXITSTATUS(s) (((s) >> 8) & 0xff)
#endif
#endif

#ifdef R36_CHKDSK_MOCK
#define R36_SCREEN_STATUS_MOCK 1
#endif
#include "r36_chkdsk_console.h"
#include "r36_screen_status.h"

struct r36_chkdsk_opts {
    const char *device;
    const char *mountpoint;
    const char *fstype;
    const char *mount_opts;
    const char *swapfile;
    const char *fsck_tool;
    const char *snapshot_path;
    const char *mountinfo_path;
    const char *swaps_path;
    const char *kmsg_path;
    const char *tty_path;
    const char *fb_path;
    int check_only;
    int require_kmsg_error;
    int image_mode;
    int use_watchdog;
};

#ifndef R36_CHKDSK_MOCK
static volatile uint32_t *r36_chk_wdt;
static uint32_t r36_chk_old_ctrl;
#endif

static void r36_chkdsk_default_opts(struct r36_chkdsk_opts *o)
{
    memset(o, 0, sizeof(*o));
    o->device = "/dev/mmcblk0p1";
    o->mountpoint = "/mnt/sdcard";
    o->fstype = "vfat";
    o->mount_opts = "utf8";
    o->swapfile = "/mnt/sdcard/cubegm/pagefile.sys";
    o->fsck_tool = "/sbin/fsck.fat";
    o->snapshot_path = "/tmp/fat-before-metadata.bin";
    o->mountinfo_path = "/proc/self/mountinfo";
    o->swaps_path = "/proc/swaps";
    o->kmsg_path = "/dev/kmsg";
    o->tty_path = "/dev/tty0";
    o->fb_path = "/dev/fb0";
    o->use_watchdog = 1;
}

static void r36_chkdsk_ui(const struct r36_chkdsk_opts *o, enum r36_screen_tone tone,
                          const char *line1, const char *line2, int pct)
{
    if (o && o->fb_path)
        (void)r36_screen_status_show(o->fb_path, tone, "[R36S CHKDSK]", line1, line2, pct);
}

static void r36_chkdsk_report(const struct r36_chkdsk_opts *o, const char *fmt, ...)
{
    char msg[256];
    va_list ap;
    int len;

    va_start(ap, fmt);
    len = vsnprintf(msg, sizeof(msg), fmt, ap);
    va_end(ap);
    if (len <= 0)
        return;

    fputs(msg, stdout);
    fflush(stdout);

    if (o && o->tty_path) {
        int tfd = open(o->tty_path, O_WRONLY | O_CLOEXEC);
        if (tfd >= 0) {
            ssize_t ignored = write(tfd, msg, (size_t)len);
            (void)ignored;
            close(tfd);
        }
    }
}

static int r36_chkdsk_kmsg_has_error(const char *kmsg_path)
{
    FILE *f;
    char line[512];
    int found = 0;

    if (!kmsg_path)
        return 0;
    f = fopen(kmsg_path, "r");
    if (!f)
        return 0;
    while (fgets(line, sizeof(line), f)) {
        if (r36_kmsg_line_indicates_fs_error(line)) {
            found = 1;
            break;
        }
    }
    fclose(f);
    return found;
}

#ifndef R36_CHKDSK_MOCK
static int r36_chkdsk_swap_active(const char *swaps_path, const char *swapfile)
{
    FILE *f;
    char line[512];
    int active = 0;

    if (!swaps_path || !swapfile)
        return 0;
    f = fopen(swaps_path, "r");
    if (!f)
        return 0;
    while (fgets(line, sizeof(line), f)) {
        if (strstr(line, swapfile) != NULL) {
            active = 1;
            break;
        }
    }
    fclose(f);
    return active;
}

static int r36_chkdsk_block_offline(const struct r36_chkdsk_opts *o)
{
    struct stat st;
    FILE *file;
    char line[1024];
    unsigned int maj, min;
    int fd;

    if (stat(o->device, &st) != 0 || !S_ISBLK(st.st_mode))
        return 0;

    file = fopen(o->mountinfo_path, "r");
    if (!file)
        return 0;
    while (fgets(line, sizeof(line), file)) {
        if (sscanf(line, "%*u %*u %u:%u", &maj, &min) != 2 ||
            (maj == major(st.st_rdev) && min == minor(st.st_rdev))) {
            fclose(file);
            return 0;
        }
    }
    fclose(file);

    if (r36_chkdsk_swap_active(o->swaps_path, o->swapfile))
        return 0;

    fd = open(o->device, O_RDONLY | O_EXCL | O_CLOEXEC);
    if (fd < 0)
        return 0;
    close(fd);
    return 1;
}

static int r36_chkdsk_pause_watchdog(void)
{
    int fd = open("/dev/mem", O_RDWR | O_SYNC | O_CLOEXEC);
    void *map;
    if (fd < 0)
        return -1;
    map = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0x18818000);
    close(fd);
    if (map == MAP_FAILED)
        return -1;
    r36_chk_wdt = (volatile uint32_t *)((unsigned char *)map + 0x500);
    r36_chk_old_ctrl = r36_chk_wdt[1];
    if (r36_chk_old_ctrl != 0x26)
        return -1;
    r36_chk_wdt[1] = 0;
    __sync_synchronize();
    return r36_chk_wdt[1] == 0 ? 0 : -1;
}

static void r36_chkdsk_resume_watchdog(void)
{
    if (!r36_chk_wdt)
        return;
    r36_chk_wdt[0] = (uint32_t)(0u - 187500u * 30u);
    r36_chk_wdt[1] = r36_chk_old_ctrl;
    __sync_synchronize();
}

static int r36_chkdsk_snapshot(const char *device, const char *snapshot_path)
{
    const size_t limit = 8u * 1024u * 1024u;
    unsigned char buf[16384];
    size_t done = 0;
    int in, out, res = -1;

    if (!snapshot_path)
        return 0;
    in = open(device, O_RDONLY | O_CLOEXEC);
    out = open(snapshot_path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (in < 0 || out < 0)
        goto out_close;
    while (done < limit) {
        ssize_t n = read(in, buf, sizeof(buf));
        ssize_t off = 0;
        if (n <= 0)
            goto out_close;
        while (off < n) {
            ssize_t w = write(out, buf + off, (size_t)(n - off));
            if (w <= 0)
                goto out_close;
            off += w;
        }
        done += (size_t)n;
    }
    res = fsync(out);
out_close:
    if (in >= 0) close(in);
    if (out >= 0) close(out);
    return res;
}

static int r36_chkdsk_exec_fsck(const char *tool, const char *device, int repair, int *signalled)
{
    int status, pfd[2], matches = 0, read_err;
    char line[512] = "", last[512] = "", expected[96];
    FILE *stream;
    pid_t child, got;

    *signalled = 0;
    if (pipe(pfd) != 0)
        return -1;
    child = fork();
    if (child < 0) {
        close(pfd[0]);
        close(pfd[1]);
        return -1;
    }
    if (!child) {
        close(pfd[0]);
        if (dup2(pfd[1], STDOUT_FILENO) < 0)
            _exit(127);
        close(pfd[1]);
        if (repair)
            execl(tool, tool, "-c", "437", "-a", "-f", device, (char *)NULL);
        else
            execl(tool, tool, "-c", "437", "-n", device, (char *)NULL);
        _exit(127);
    }
    close(pfd[1]);
    stream = fdopen(pfd[0], "r");
    if (!stream) {
        close(pfd[0]);
        do { got = waitpid(child, &status, 0); } while (got < 0 && errno == EINTR);
        return -1;
    }
    while (fgets(line, sizeof(line), stream)) {
        fputs(line, stdout);
        memcpy(last, line, sizeof(last));
        if (!strncmp(line, "R36_FSCK_COMPLETE_V1 ", 21))
            matches++;
    }
    read_err = ferror(stream);
    fclose(stream);
    do { got = waitpid(child, &status, 0); } while (got < 0 && errno == EINTR);
    if (got < 0)
        return -1;
    *signalled = !WIFEXITED(status);
    if (!WIFEXITED(status))
        return -1;
    status = WEXITSTATUS(status);
    snprintf(expected, sizeof(expected), "R36_FSCK_COMPLETE_V1 mode=%s status=%d\n",
             repair ? "repair" : "check", status);
    if (read_err || matches != 1 || strcmp(last, expected) != 0 || status > 1)
        return -1;
    return status;
}
#endif

static enum r36_chkdsk_result r36_chkdsk_run(const struct r36_chkdsk_opts *opts)
{
    int had_swap = 0, did_unmount = 0;
    int status, signalled = 0;
    enum r36_chkdsk_result res = R36_CHKDSK_CHECK_FAILED;

    if (!opts || !opts->device || !opts->fsck_tool)
        return R36_CHKDSK_CHECK_FAILED;

    if (opts->require_kmsg_error && !r36_chkdsk_kmsg_has_error(opts->kmsg_path)) {
        r36_chkdsk_report(opts, "[R36-CHKDSK] No kernel FS/memory error in log.\n");
        return R36_CHKDSK_NO_ERROR_DETECTED;
    }

    r36_chkdsk_report(opts, "[R36-CHKDSK] Preparing %s check...\n", opts->device);
    r36_chkdsk_ui(opts, R36_SCREEN_INFO, "PREPARING SD CARD CHECK...", opts->device, 10);

    if (!opts->image_mode) {
        had_swap = r36_chkdsk_swap_active(opts->swaps_path, opts->swapfile);
        sync();
        if (had_swap && swapoff(opts->swapfile) != 0) {
            r36_chkdsk_report(opts, "[R36-CHKDSK] REFUSED: swapoff failed (%d)\n", errno);
            r36_chkdsk_ui(opts, R36_SCREEN_ERR, "REFUSED: SWAPOFF FAILED", "CARD STILL BUSY", 100);
            return R36_CHKDSK_REFUSED_MOUNTED;
        }
        if (opts->mountpoint && umount2(opts->mountpoint, 0) == 0)
            did_unmount = 1;
        if (!r36_chkdsk_block_offline(opts)) {
            r36_chkdsk_report(opts, "[R36-CHKDSK] REFUSED: %s still mounted or busy\n", opts->device);
            r36_chkdsk_ui(opts, R36_SCREEN_ERR, "REFUSED: SD STILL MOUNTED", "CANNOT CHECK ONLINE", 100);
            return R36_CHKDSK_REFUSED_MOUNTED;
        }
    }

    r36_chkdsk_report(opts, "[R36-CHKDSK] Checking filesystem (read-only)...\n");
    r36_chkdsk_ui(opts, R36_SCREEN_INFO, "CHECKING FILESYSTEM...", "READ-ONLY PASS", 30);
    status = r36_chkdsk_exec_fsck(opts->fsck_tool, opts->device, 0, &signalled);
    switch (r36_fat_after_check(status, signalled)) {
    case R36_FAT_BOOT:
        r36_chkdsk_report(opts, "[R36-CHKDSK] Filesystem is clean.\n");
        r36_chkdsk_ui(opts, R36_SCREEN_OK, "FILESYSTEM IS CLEAN", "STARTING SYSTEM...", 100);
        res = R36_CHKDSK_CLEAN;
        break;
    case R36_FAT_STOP:
        r36_chkdsk_report(opts, "[R36-CHKDSK] Check aborted (status=%d sig=%d).\n", status, signalled);
        r36_chkdsk_ui(opts, R36_SCREEN_ERR, "CHECK ABORTED", "CHECK LOGS", 100);
        res = R36_CHKDSK_CHECK_FAILED;
        break;
    case R36_FAT_REPAIR:
        if (opts->check_only) {
            r36_chkdsk_report(opts, "[R36-CHKDSK] Errors found (check-only mode).\n");
            r36_chkdsk_ui(opts, R36_SCREEN_WARN, "ERRORS FOUND", "CHECK-ONLY MODE", 100);
            res = R36_CHKDSK_CHECK_FAILED;
            break;
        }
        if (!opts->image_mode && r36_chkdsk_snapshot(opts->device, opts->snapshot_path) != 0) {
            r36_chkdsk_report(opts, "[R36-CHKDSK] REFUSED: metadata backup failed.\n");
            r36_chkdsk_ui(opts, R36_SCREEN_ERR, "BACKUP FAILED", "NO WRITES PERFORMED", 100);
            res = R36_CHKDSK_REPAIR_FAILED;
            break;
        }
        if (!opts->image_mode && opts->use_watchdog && r36_chkdsk_pause_watchdog() != 0) {
            r36_chkdsk_report(opts, "[R36-CHKDSK] REFUSED: watchdog pause failed.\n");
            r36_chkdsk_ui(opts, R36_SCREEN_ERR, "WATCHDOG LOCK FAILED", "NO WRITES PERFORMED", 100);
            res = R36_CHKDSK_REPAIR_FAILED;
            break;
        }
        r36_chkdsk_report(opts, "[R36-CHKDSK] Repairing filesystem...\n");
        r36_chkdsk_ui(opts, R36_SCREEN_WARN, "REPAIRING FILESYSTEM...", "DO NOT POWER OFF!", 65);
        status = r36_chkdsk_exec_fsck(opts->fsck_tool, opts->device, 1, &signalled);
        sync();
        if (!r36_fat_repair_may_verify(status, signalled)) {
            r36_chkdsk_report(opts, "[R36-CHKDSK] Repair failed (status=%d sig=%d).\n", status, signalled);
            r36_chkdsk_ui(opts, R36_SCREEN_ERR, "REPAIR FAILED", "RECOVERY NEEDED", 100);
            if (!opts->image_mode && opts->use_watchdog)
                r36_chkdsk_resume_watchdog();
            res = R36_CHKDSK_REPAIR_FAILED;
            break;
        }
        r36_chkdsk_report(opts, "[R36-CHKDSK] Verifying repaired filesystem...\n");
        r36_chkdsk_ui(opts, R36_SCREEN_INFO, "VERIFYING REPAIR...", "FINAL PASS", 90);
        status = r36_chkdsk_exec_fsck(opts->fsck_tool, opts->device, 0, &signalled);
        if (!opts->image_mode && opts->use_watchdog)
            r36_chkdsk_resume_watchdog();
        if (r36_fat_verified(status, signalled)) {
            r36_chkdsk_report(opts, "[R36-CHKDSK] Repair verified OK.\n");
            r36_chkdsk_ui(opts, R36_SCREEN_OK, "REPAIR VERIFIED OK", "RESUMING SYSTEM...", 100);
            res = R36_CHKDSK_REPAIRED_VERIFIED;
        } else {
            r36_chkdsk_report(opts, "[R36-CHKDSK] Verification failed.\n");
            r36_chkdsk_ui(opts, R36_SCREEN_ERR, "VERIFY FAILED", "CHECK SD CARD", 100);
            res = R36_CHKDSK_VERIFY_FAILED;
        }
        break;
    }

    if (did_unmount) {
        if (mount(opts->device, opts->mountpoint, opts->fstype, 0, opts->mount_opts) != 0) {
            r36_chkdsk_report(opts, "[R36-CHKDSK] ERROR: remount failed (%d)\n", errno);
            return R36_CHKDSK_REMOUNT_FAILED;
        }
        if (had_swap)
            (void)swapon(opts->swapfile, 0);
    }
    return res;
}

#ifndef R36_CHKDSK_LIBRARY_ONLY
int main(int argc, char **argv)
{
    struct r36_chkdsk_opts opts;
    enum r36_chkdsk_result res;
    int i;

    r36_chkdsk_default_opts(&opts);
    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--check-only") == 0) {
            opts.check_only = 1;
        } else if (strcmp(argv[i], "--if-kernel-error") == 0) {
            opts.require_kmsg_error = 1;
        } else if (strcmp(argv[i], "--no-watchdog") == 0) {
            opts.use_watchdog = 0;
        } else if (strcmp(argv[i], "--image") == 0 && i + 1 < argc) {
            opts.image_mode = 1;
            opts.device = argv[++i];
        } else if (strcmp(argv[i], "--fsck") == 0 && i + 1 < argc) {
            opts.fsck_tool = argv[++i];
        } else {
            fprintf(stderr, "Usage: %s [--check-only] [--if-kernel-error] [--no-watchdog] [--image PATH] [--fsck PATH]\n", argv[0]);
            return 2;
        }
    }
    res = r36_chkdsk_run(&opts);
    return (res == R36_CHKDSK_CLEAN || res == R36_CHKDSK_REPAIRED_VERIFIED ||
            res == R36_CHKDSK_NO_ERROR_DETECTED) ? 0 : (int)res;
}
#endif
