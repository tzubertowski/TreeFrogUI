#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <unistd.h>
#include "user_trace.h"

#ifndef R36_TEST_DRIVER
#define R36_TEST_DRIVER 0
#endif

#if R36_TEST_DRIVER
static const char init_mode[] __attribute__((used, section(".r36.init"))) = "R36_MINIMAL_INIT_V1:driver";
#else
static const char init_mode[] __attribute__((used, section(".r36.init"))) = "R36_MINIMAL_INIT_V1:boot";
#endif

static void note(const char *text)
{
    int fd = open("/dev/kmsg", O_WRONLY | O_NONBLOCK);
    if (fd >= 0) { dprintf(fd, "<6>r36lab: %s\n", text); close(fd); }
}

static void copy_report(const char *source, const char *destination, const char *id)
{
    char buffer[1024];
    int in = open(source, O_RDONLY);
    int out = open(destination, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    ssize_t n;
    if (in >= 0 && out >= 0) {
        dprintf(out, "run_id=%s\n", id);
        while ((n = read(in, buffer, sizeof(buffer))) > 0) {
            ssize_t done = 0;
            while (done < n) {
                ssize_t written = write(out, buffer + done, n - done);
                if (written <= 0) break;
                done += written;
            }
            if (done != n) break;
        }
        fsync(out);
    }
    if (in >= 0) close(in);
    if (out >= 0) close(out);
}

static void driver_test(const struct utsname *u, const char *id)
{
    int out = open("/sd/cubegm/r36-driver-test.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    int module, result, parameter = 0, unloaded = -1, disappeared = 0, fd;
    char marker[32] = {0};
    if (out < 0) { note("cannot create driver report"); return; }
    dprintf(out, "R36 DRIVER TEST\nrun_id=%s\nrelease=%s\nversion=%s\nphase=loading\n",
            id, u->release, u->version);
    fsync(out);
    module = open("/sd/cubegm/r36hello.ko", O_RDONLY);
    result = module < 0 ? -1 : syscall(SYS_finit_module, module, "", 0);
    dprintf(out, "load_rc=%d\nload_errno=%d\n", result, result ? errno : 0);
    if (module >= 0) close(module);
    fsync(out);
    if (!result) {
        fd = open("/sys/module/r36hello/parameters/marker", O_RDONLY);
        if (fd >= 0) {
            ssize_t n = read(fd, marker, sizeof(marker) - 1);
            if (n > 0) { marker[n] = 0; parameter = !strcmp(marker, "5387062\n"); }
            close(fd);
        }
        unloaded = syscall(SYS_delete_module, "r36hello", O_NONBLOCK);
        disappeared = access("/sys/module/r36hello", F_OK) != 0 && errno == ENOENT;
    }
    dprintf(out, "parameter_ok=%d\nunload_rc=%d\nsysfs_removed=%d\nresult=%s\n",
            parameter, unloaded, disappeared,
            !result && parameter && !unloaded && disappeared ? "PASS" : "FAIL");
    fsync(out);
    close(out);
    note("driver test report committed");
}

int main(void)
{
    struct utsname u;
    char id[80] = "missing";
    int attempt, fd;
    mkdir("/dev", 0755); mkdir("/proc", 0755); mkdir("/sys", 0755); mkdir("/sd", 0755);
    mount("devtmpfs", "/dev", "devtmpfs", 0, NULL);
    mount("proc", "/proc", "proc", 0, NULL);
    mount("sysfs", "/sys", "sysfs", 0, NULL);
    uname(&u);
    mark_userspace();
    note("minimal PID1 reached; watchdog remains armed");
    for (attempt = 0; attempt < 20; attempt++) {
        if (!mount("/dev/mmcblk0p1", "/sd", "vfat", MS_NOATIME, "iocharset=iso8859-1")) break;
        sleep(1);
    }
    if (attempt < 20) {
        fd = open("/sd/cubegm/r36-run-id.txt", O_RDONLY);
        if (fd >= 0) {
            ssize_t n = read(fd, id, sizeof(id) - 1);
            if (n > 0) { id[n] = 0; id[strcspn(id, "\r\n")] = 0; }
            close(fd);
        }
        fd = open("/sd/cubegm/r36-own-kernel-proof.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (fd >= 0) {
            dprintf(fd, "R36 OWN KERNEL USERSPACE REACHED\nrun_id=%s\nsysname=%s\n"
                    "release=%s\nversion=%s\nmachine=%s\npid=%ld\n",
                    id, u.sysname, u.release, u.version, u.machine, (long)getpid());
            fsync(fd);
            close(fd);
        }
        copy_report("/proc/meminfo", "/sd/cubegm/r36-minimal-meminfo.txt", id);
        copy_report("/proc/interrupts", "/sd/cubegm/r36-minimal-interrupts.txt", id);
        if (R36_TEST_DRIVER) driver_test(&u, id);
        sync();
        umount("/sd");
        note("reports committed; waiting for diagnostic watchdog reset");
    } else note("SD mount timeout; waiting for watchdog reset");
    for (;;) pause();
}
