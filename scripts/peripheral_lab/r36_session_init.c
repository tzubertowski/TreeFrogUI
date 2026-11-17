/* SPDX-License-Identifier: MIT
 * Full Linux 7.2 session supervisor / PID1 orchestrator for R36S:
 *  1. Reserves stdio fds 0..2 on /dev/null and mounts /dev, /proc, /sys, /tmp
 *  2. Runs pre-mount r36-chkdsk before touching /mnt/sdcard (aborts if unsafe)
 *  3. Mounts /mnt/sdcard, writes /tmp/tfdevice.env, exports PICOARCH_DRIVER
 *  4. Supervises r36-sysd, r36-legacy-keys, r36-usb-mtp-adb, and picoarch UI
 *  5. Handles frogui_launch.txt game handoff and clean swapoff/umount shutdown
 */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

#ifndef R36_SESSION_MOCK
#include <fcntl.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/stat.h>
#include <sys/swap.h>
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
#ifndef O_TRUNC
#define O_TRUNC 0x200
#endif
#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif
#ifndef F_OK
#define F_OK 0
#endif
#ifndef RB_POWER_OFF
#define RB_POWER_OFF 0x4321fedcu
#endif
#ifndef SIGTERM
#define SIGTERM 15
#endif
#ifndef SIGKILL
#define SIGKILL 9
#endif
#ifndef WNOHANG
#define WNOHANG 1
#endif
#ifndef WIFEXITED
#define WIFEXITED(s) (((s) & 0x7f) == 0)
#define WEXITSTATUS(s) (((s) >> 8) & 0xff)
#endif
#endif

struct r36_session_cfg {
    const char *sd_dev;
    const char *sd_mount;
    const char *chkdsk_bin;
    const char *sysd_bin;
    const char *keys_bin;
    const char *keys_map;
    const char *usb_bin;
    const char *picoarch_bin;
    const char *frogui_core;
    const char *driver_so;
    const char *tfdevice_env_path;
    const char *launch_file;
    const char *poweroff_flag;
    const char *swapfile;
};

struct r36_session_ctx {
    struct r36_session_cfg cfg;
    pid_t sysd_pid;
    pid_t keys_pid;
    pid_t usb_pid;
    pid_t ui_pid;
    int sd_mounted;
    int shutdown_requested;
};

static void r36_session_default_cfg(struct r36_session_cfg *c)
{
    memset(c, 0, sizeof(*c));
    c->sd_dev = "/dev/mmcblk0p1";
    c->sd_mount = "/mnt/sdcard";
    c->chkdsk_bin = "/sbin/r36-chkdsk";
    c->sysd_bin = "/sbin/r36-sysd";
    c->keys_bin = "/mnt/sdcard/cubegm/r36-legacy-keys";
    c->keys_map = "/mnt/sdcard/cubegm/evdev-to-legacy.map";
    c->usb_bin = "/sbin/r36-usb-mtp-adb";
    c->picoarch_bin = "/mnt/sdcard/cubegm/picoarch";
    c->frogui_core = "/mnt/sdcard/cubegm/cores/frogui_libretro.so";
    c->driver_so = "/mnt/sdcard/cubegm/driver_r36_combined.so";
    c->tfdevice_env_path = "/tmp/tfdevice.env";
    c->launch_file = "/mnt/sdcard/cubegm/frogui_launch.txt";
    c->poweroff_flag = "/tmp/r36-poweroff.req";
    c->swapfile = "/mnt/sdcard/cubegm/pagefile.sys";
}

static int r36_write_tfdevice_env(const struct r36_session_cfg *c)
{
    static const char body[] =
        "TF_DEVICE=GB350\n"
        "TF_PANEL_W=640\n"
        "TF_PANEL_H=480\n"
        "TF_UI_SCALE=150\n"
        "TF_ASPECT_NUM=4\n"
        "TF_ASPECT_DEN=3\n"
        "TF_ROTATE=0\n"
        "TF_PRESENT=dispframe\n";
    int fd;
    size_t len = sizeof(body) - 1u;
    ssize_t n;

    if (!c || !c->tfdevice_env_path)
        return -1;
    fd = open(c->tfdevice_env_path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    if (fd < 0)
        return -1;
    n = write(fd, body, len);
    close(fd);
    if (n != (ssize_t)len)
        return -1;

    if (c->driver_so && access(c->driver_so, F_OK) == 0)
        setenv("PICOARCH_DRIVER", c->driver_so, 1);
    setenv("LD_LIBRARY_PATH", "/mnt/sdcard/cubegm/lib:/mnt/sdcard/cubegm/usr/lib", 1);
    return 0;
}

static pid_t r36_spawn_prog(const char *const argv[])
{
    pid_t pid = fork();
    if (pid < 0)
        return -1;
    if (pid == 0) {
        if (chdir("/") != 0)
            _exit(127);
        execv(argv[0], (char *const *)argv);
        _exit(127);
    }
    return pid;
}

static int r36_run_sync_cmd(const char *const argv[])
{
    int status = 0;
    pid_t pid = r36_spawn_prog(argv);
    pid_t got;
    if (pid < 0)
        return -1;
    do {
        got = waitpid(pid, &status, 0);
    } while (got < 0 && errno == EINTR);
    if (got != pid || !WIFEXITED(status))
        return -1;
    return WEXITSTATUS(status);
}

static void r36_stop_child(pid_t *pid)
{
    int status = 0;
    pid_t got;
    if (!pid || *pid <= 0)
        return;
    (void)kill(*pid, SIGTERM);
    do {
        got = waitpid(*pid, &status, 0);
    } while (got < 0 && errno == EINTR);
    *pid = 0;
}

static int r36_session_bootstrap(struct r36_session_ctx *ctx, const struct r36_session_cfg *custom)
{
    int attempt;

    if (!ctx)
        return -1;
    memset(ctx, 0, sizeof(*ctx));
    if (custom)
        ctx->cfg = *custom;
    else
        r36_session_default_cfg(&ctx->cfg);

    for (attempt = 0; attempt < 20; attempt++) {
        if (access(ctx->cfg.sd_dev, F_OK) == 0)
            break;
        usleep(100000);
    }
    if (attempt == 20)
        return -1;

    if (ctx->cfg.chkdsk_bin && access(ctx->cfg.chkdsk_bin, F_OK) == 0) {
        const char *const chk_argv[] = { ctx->cfg.chkdsk_bin, "--if-kernel-error", NULL };
        if (r36_run_sync_cmd(chk_argv) != 0)
            return -2; /* Never mount a dirty/damaged SD card on chkdsk refusal */
    }

    if (mount(ctx->cfg.sd_dev, ctx->cfg.sd_mount, "vfat", 0, "utf8") != 0)
        return -3;
    ctx->sd_mounted = 1;

    if (r36_write_tfdevice_env(&ctx->cfg) != 0)
        return -4;

    if (ctx->cfg.sysd_bin && access(ctx->cfg.sysd_bin, F_OK) == 0) {
        const char *const argv[] = { ctx->cfg.sysd_bin, NULL };
        ctx->sysd_pid = r36_spawn_prog(argv);
    }
    if (ctx->cfg.keys_bin && access(ctx->cfg.keys_bin, F_OK) == 0) {
        const char *const argv[] = { ctx->cfg.keys_bin, ctx->cfg.keys_map, NULL };
        ctx->keys_pid = r36_spawn_prog(argv);
    }
    if (ctx->cfg.usb_bin && access(ctx->cfg.usb_bin, F_OK) == 0) {
        const char *const argv[] = { ctx->cfg.usb_bin, NULL };
        ctx->usb_pid = r36_spawn_prog(argv);
    }
    return 0;
}

static int r36_read_launch_request(const char *path, char kind[32], char bin[256], char arg[256])
{
    FILE *f;
    size_t n;

    if (!path || !kind || !bin || !arg)
        return 0;
    f = fopen(path, "r");
    if (!f)
        return 0;
    kind[0] = bin[0] = arg[0] = '\0';
    if (!fgets(kind, 32, f) || !fgets(bin, 256, f)) {
        fclose(f);
        return 0;
    }
    (void)fgets(arg, 256, f);
    fclose(f);

    for (char *s = kind; *s; s++) if (*s == '\n' || *s == '\r') *s = '\0';
    for (char *s = bin; *s; s++) if (*s == '\n' || *s == '\r') *s = '\0';
    for (char *s = arg; *s; s++) if (*s == '\n' || *s == '\r') *s = '\0';
    n = strlen(bin);
    return n > 0u ? 1 : 0;
}

static int r36_session_launch_ui(struct r36_session_ctx *ctx)
{
    if (!ctx || !ctx->cfg.picoarch_bin || !ctx->cfg.frogui_core)
        return -1;
    const char *const argv[] = {
        ctx->cfg.picoarch_bin, ctx->cfg.frogui_core, ctx->cfg.frogui_core, NULL
    };
    ctx->ui_pid = r36_spawn_prog(argv);
    return ctx->ui_pid > 0 ? 0 : -1;
}

static int r36_session_step(struct r36_session_ctx *ctx)
{
    char kind[32], bin[256], arg[256];

    if (!ctx)
        return -1;

    if (ctx->cfg.poweroff_flag && access(ctx->cfg.poweroff_flag, F_OK) == 0) {
        ctx->shutdown_requested = 1;
        return 1;
    }

    if (ctx->ui_pid <= 0) {
        if (r36_session_launch_ui(ctx) != 0)
            return -1;
    }

    if (ctx->cfg.launch_file && r36_read_launch_request(ctx->cfg.launch_file, kind, bin, arg)) {
        (void)unlink(ctx->cfg.launch_file);
        r36_stop_child(&ctx->ui_pid);
        if (strcmp(kind, "standalone") == 0) {
            const char *const argv[] = { bin, arg[0] ? arg : NULL, NULL };
            (void)r36_run_sync_cmd(argv);
        } else {
            const char *const argv[] = { ctx->cfg.picoarch_bin, bin, arg[0] ? arg : NULL, NULL };
            (void)r36_run_sync_cmd(argv);
        }
        (void)r36_session_launch_ui(ctx);
    } else if (ctx->ui_pid > 0) {
        int status = 0;
        pid_t got = waitpid(ctx->ui_pid, &status, WNOHANG);
        if (got == ctx->ui_pid)
            ctx->ui_pid = 0;
    }

    return 0;
}

static int r36_session_shutdown(struct r36_session_ctx *ctx)
{
    if (!ctx)
        return -1;
    r36_stop_child(&ctx->ui_pid);
    r36_stop_child(&ctx->keys_pid);
    r36_stop_child(&ctx->usb_pid);
    r36_stop_child(&ctx->sysd_pid);

    sync();
    if (ctx->sd_mounted) {
        if (ctx->cfg.swapfile)
            (void)swapoff(ctx->cfg.swapfile);
        (void)umount(ctx->cfg.sd_mount);
        ctx->sd_mounted = 0;
    }
    sync();
    return reboot(RB_POWER_OFF);
}

#ifndef R36_SESSION_LIBRARY_ONLY
static void r36_reserve_stdio(void)
{
    int null_fd = open("/dev/null", O_RDWR);
    if (null_fd >= 0) {
        while (null_fd <= 2) {
            int dup_fd = dup(null_fd);
            if (dup_fd < 0)
                break;
            null_fd = dup_fd;
        }
        if (null_fd > 2)
            close(null_fd);
    }
}

int main(void)
{
    struct r36_session_ctx ctx;
    if (getpid() == 1) {
        mkdir("/dev", 0755);
        mkdir("/proc", 0755);
        mkdir("/sys", 0755);
        mkdir("/tmp", 01777);
        mkdir("/mnt", 0755);
        mkdir("/mnt/sdcard", 0755);
        (void)mount("devtmpfs", "/dev", "devtmpfs", 0, NULL);
        r36_reserve_stdio();
        (void)mount("proc", "/proc", "proc", 0, NULL);
        (void)mount("sysfs", "/sys", "sysfs", 0, NULL);
        (void)mount("tmpfs", "/tmp", "tmpfs", 0, NULL);
    }
    if (r36_session_bootstrap(&ctx, NULL) != 0)
        return 1;
    while (!ctx.shutdown_requested) {
        if (r36_session_step(&ctx) != 0)
            break;
        usleep(100000);
    }
    (void)r36_session_shutdown(&ctx);
    return 0;
}
#endif
