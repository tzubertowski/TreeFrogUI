/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/klog.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>
#include "../kernel_lab/user_trace.h"

/* Diagnostic PID1. Does not feed/disable watchdog, export SD, or run a shell.
 * A host challenge/response proves communication, configfs bind alone does not.
 * Reports are committed to SD only after the bounded observation window.
 */
static const char base[] = "/sys/kernel/config/usb_gadget/r36diag";
static char last_phase[64] = "not_started", bound_udc[128];
static unsigned int pings, received, sent;

static long now_ms(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1000L + t.tv_nsec / 1000000L;
}
static int value(const char *path, const char *text)
{
    int fd = open(path, O_WRONLY | O_CLOEXEC);
    size_t size = strlen(text);
    ssize_t n;
    if (fd < 0) return -1;
    do { n = write(fd, text, size); } while (n < 0 && errno == EINTR);
    close(fd);
    return n == (ssize_t)size ? 0 : -1;
}
static int directory(const char *path)
{
    return mkdir(path, 0755) && errno != EEXIST ? -1 : 0;
}
static int setup_gadget(void)
{
    DIR *dir;
    struct dirent *entry;
    strcpy(last_phase, "configfs");
    if (directory("/sys/kernel/config") || mount("configfs", "/sys/kernel/config", "configfs", 0, NULL)) return -1;
    if (directory(base) || chdir(base)) return -1;
    strcpy(last_phase, "descriptors");
    if (value("idVendor", "0x1d6b") || value("idProduct", "0x0104") ||
        value("bcdUSB", "0x0200") || value("bcdDevice", "0x0101") ||
        value("bDeviceClass", "0x02") || value("bDeviceSubClass", "0") || value("bDeviceProtocol", "0")) return -1;
    if (directory("strings/0x409") || value("strings/0x409/serialnumber", "R36LAB-CDC-DIAG") ||
        value("strings/0x409/manufacturer", "R36Lab") ||
        value("strings/0x409/product", "HC16xx CDC diagnostic")) return -1;
    if (directory("configs/c.1") || directory("configs/c.1/strings/0x409") ||
        value("configs/c.1/strings/0x409/configuration", "Single CDC ACM") ||
        value("configs/c.1/MaxPower", "100") || value("configs/c.1/bmAttributes", "0x80")) return -1;
    strcpy(last_phase, "acm_function");
    if (directory("functions/acm.GS0")) return -1;
    strcpy(last_phase, "acm_link");
    /* configfs resolves targets using kern_path at syscall time (cwd), not
     * from the directory containing the symlink. Use the actual absolute path. */
    if (symlink("/sys/kernel/config/usb_gadget/r36diag/functions/acm.GS0", "configs/c.1/acm.GS0")) return -1;
    strcpy(last_phase, "wait_udc");
    for (unsigned int attempt = 0; attempt < 30; attempt++) {
        unsigned int count = 0;
        dir = opendir("/sys/class/udc");
        if (dir) {
            while ((entry = readdir(dir))) {
                if (entry->d_name[0] == '.') continue;
                count++;
                snprintf(bound_udc, sizeof(bound_udc), "%.127s", entry->d_name);
            }
            closedir(dir);
        }
        if (count > 1) return -1; /* Never select a different UDC by directory order. */
        if (count == 1) {
            strcpy(last_phase, "bind_udc");
            if (value("UDC", bound_udc)) return -1;
            strcpy(last_phase, "bound");
            return 0;
        }
        usleep(100000);
    }
    errno = ENODEV;
    return -1;
}
static int transmit(int fd, const char *text)
{
    size_t offset = 0, size = strlen(text);
    long deadline = now_ms() + 250;
    while (offset < size && now_ms() < deadline) {
        ssize_t n = write(fd, text + offset, size - offset);
        if (n > 0) { offset += n; sent += n; }
        else if (n < 0 && errno == EINTR) continue;
        else if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
            struct pollfd ready = {.fd = fd, .events = POLLOUT};
            poll(&ready, 1, 10);
        } else return -1;
    }
    return offset == size ? 0 : -1;
}
static void report_file(const char *source, const char *destination, const char *id)
{
    char data[1024];
    int in = open(source, O_RDONLY | O_CLOEXEC), out = open(destination, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    ssize_t n;
    if (in >= 0 && out >= 0) {
        dprintf(out, "run_id=%s\n", id);
        while ((n = read(in, data, sizeof(data))) > 0) {
            ssize_t offset = 0;
            while (offset < n) {
                ssize_t wrote = write(out, data + offset, n - offset);
                if (wrote <= 0) break;
                offset += wrote;
            }
            if (offset != n) break;
        }
        fsync(out);
    }
    if (in >= 0) close(in);
    if (out >= 0) close(out);
}
int main(void)
{
    struct utsname identity;
    char line[128], id[80] = "missing", state[64] = "unavailable";
    size_t used = 0;
    int gadget, saved_errno, serial = -1, sd = 0, fd, unbind = -1;
    long end;
    directory("/dev"); directory("/proc"); directory("/sys"); directory("/sd");
    if (mount("devtmpfs", "/dev", "devtmpfs", 0, NULL) || mount("proc", "/proc", "proc", 0, NULL) ||
        mount("sysfs", "/sys", "sysfs", 0, NULL) || uname(&identity)) for (;;) pause();
    mark_userspace();
    gadget = setup_gadget(); saved_errno = gadget ? errno : 0;
    if (chdir("/")) for (;;) pause();
    end = now_ms() + 12000;
    while (gadget == 0 && now_ms() < end) {
        if (serial < 0) {
            struct termios options;
            serial = open("/dev/ttyGS0", O_RDWR | O_NOCTTY | O_NONBLOCK | O_CLOEXEC);
            if (serial >= 0 && !tcgetattr(serial, &options)) {
                cfmakeraw(&options); tcsetattr(serial, TCSANOW, &options);
            }
        }
        if (serial >= 0) {
            char buffer[128]; ssize_t n = read(serial, buffer, sizeof(buffer));
            if (n > 0) for (ssize_t i = 0; i < n; i++) {
                char c = buffer[i]; received++;
                if (c == '\r' || c == '\n') {
                    if (used) {
                        char response[160];
                        line[used] = 0;
                        if (!strncmp(line, "PING ", 5) && used == 37 && strspn(line + 5, "0123456789abcdef") == 32) {
                            snprintf(response, sizeof(response), "PONG %s\n", line + 5);
                            if (!transmit(serial, response)) pings++;
                        } else transmit(serial, "ERROR expected PING plus 32 lowercase hex digits\n");
                    }
                    used = 0;
                } else if (used < sizeof(line) - 1) line[used++] = c;
                else { used = 0; close(serial); serial = -1; break; }
            }
            else if (n < 0 && errno != EAGAIN && errno != EINTR) { close(serial); serial = -1; used = 0; }
        }
        usleep(10000);
    }
    if (serial >= 0) close(serial);
    if (bound_udc[0]) {
        char path[256];
        snprintf(path, sizeof(path), "/sys/class/udc/%s/state", bound_udc);
        fd = open(path, O_RDONLY | O_CLOEXEC);
        if (fd >= 0) { ssize_t n = read(fd, state, sizeof(state) - 1); if (n > 0) state[n] = 0; close(fd); }
        unbind = value("/sys/kernel/config/usb_gadget/r36diag/UDC", "\n");
    }
    for (unsigned int attempt = 0; attempt < 5; attempt++) {
        if (!mount("/dev/mmcblk0p1", "/sd", "vfat", MS_NOATIME, "iocharset=iso8859-1")) { sd = 1; break; }
        usleep(200000);
    }
    if (sd) {
        fd = open("/sd/cubegm/r36-run-id.txt", O_RDONLY | O_CLOEXEC);
        if (fd >= 0) { ssize_t n = read(fd, id, sizeof(id) - 1); if (n > 0) { id[n] = 0; id[strcspn(id, "\r\n")] = 0; } close(fd); }
        fd = open("/sd/cubegm/r36-own-kernel-proof.txt", O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
        if (fd >= 0) {
            dprintf(fd, "R36 OWN KERNEL USERSPACE REACHED\nrun_id=%s\nsysname=Linux\nrelease=%s\nversion=%s\nmachine=%s\npid=1\n", id, identity.release, identity.version, identity.machine);
            fsync(fd); close(fd);
        }
        fd = open("/sd/cubegm/r36-usb-cdc-probe.txt", O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
        if (fd >= 0) {
            dprintf(fd, "R36 USB CDC PROBE V1\nrun_id=%s\nrelease=%s\nversion=%s\ngadget_rc=%d errno=%d\nphase=%s\nudc=%s\nudc_state=%s\nreceived=%u sent=%u pings=%u\nunbind_rc=%d\nWindows_enumeration=HOST_REPORT_REQUIRED\nR36 USB CDC PROBE END\n", id, identity.release, identity.version, gadget, saved_errno, last_phase, bound_udc, state, received, sent, pings, unbind);
            fsync(fd); close(fd);
        }
        report_file("/proc/interrupts", "/sd/cubegm/r36-usb-interrupts.txt", id);
        sync();
        if (umount("/sd")) { mount(NULL, "/sd", "vfat", MS_REMOUNT | MS_RDONLY, NULL); sync(); }
    }
    for (;;) pause();
}
