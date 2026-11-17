#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>
#include <sys/klog.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <termios.h>
#include <unistd.h>
#include "user_trace.h"

static int serial = -1, sd_ready, gadget_result = -1;
static struct utsname identity;
static const char *phase = "userspace started";

static int put(const char *path, const char *value)
{
    int fd = open(path, O_WRONLY), ok;
    size_t size = strlen(value);
    if (fd < 0) return -1;
    ok = write(fd, value, size) == (ssize_t)size;
    close(fd);
    return ok ? 0 : -1;
}

static int usb_start(void)
{
    DIR *dir;
    struct dirent *entry;
    char udc[128] = "";
    mkdir("/sys/kernel/config", 0755);
    if (mount("configfs", "/sys/kernel/config", "configfs", 0, NULL) && errno != EBUSY) return -1;
    mkdir("/sys/kernel/config/usb_gadget/r36", 0755);
    if (chdir("/sys/kernel/config/usb_gadget/r36")) return -1;
    if (put("idVendor", "0x1d6b") || put("idProduct", "0x0104") ||
        put("bDeviceClass", "2") || put("bcdDevice", "0x0100")) return -1;
    mkdir("strings/0x409", 0755);
    if (put("strings/0x409/serialnumber", "R36LAB-PORTS1") ||
        put("strings/0x409/manufacturer", "R36Lab") ||
        put("strings/0x409/product", "HC16xx Linux diagnostic console")) return -1;
    mkdir("configs/c.1", 0755);
    mkdir("configs/c.1/strings/0x409", 0755);
    put("configs/c.1/strings/0x409/configuration", "CDC diagnostic console");
    mkdir("functions/acm.GS0", 0755);
    if (symlink("../../functions/acm.GS0", "configs/c.1/acm.GS0") && errno != EEXIST) return -1;
    dir = opendir("/sys/class/udc");
    if (!dir) return -1;
    while ((entry = readdir(dir))) {
        if (entry->d_name[0] != '.') {
            snprintf(udc, sizeof(udc), "%.127s", entry->d_name);
            break;
        }
    }
    closedir(dir);
    return udc[0] ? put("UDC", udc) : -1;
}

static void send_text(const char *text)
{
    size_t left = strlen(text);
    unsigned int retries = 0;
    while (serial >= 0 && left && retries++ < 20) {
        ssize_t n = write(serial, text, left);
        if (n > 0) { text += n; left -= n; }
        else if (errno == EAGAIN) {
            struct pollfd p = {serial, POLLOUT, 0};
            poll(&p, 1, 50);
        } else break;
    }
}

static void send_file(const char *path)
{
    char buffer[1024];
    int fd = open(path, O_RDONLY);
    ssize_t n;
    if (fd < 0) { send_text("cannot open file\n"); return; }
    while ((n = read(fd, buffer, sizeof(buffer) - 1)) > 0) {
        buffer[n] = 0;
        send_text(buffer);
    }
    close(fd);
}

static int test_driver(void)
{
    char log[512], marker[64] = "";
    int module = open("/sd/cubegm/r36hello.ko", O_RDONLY);
    int loaded = -1, reason = errno, fd, removed = -1;
    int parameter_ok = 0;
    if (module >= 0) {
        loaded = syscall(SYS_finit_module, module, "", 0);
        reason = loaded ? errno : 0;
        close(module);
    }
    if (!loaded) {
        fd = open("/sys/module/r36hello/parameters/marker", O_RDONLY);
        if (fd >= 0) {
            ssize_t n = read(fd, marker, sizeof(marker) - 1);
            if (n > 0) { marker[n] = 0; parameter_ok = !strcmp(marker, "5387062\n"); }
            close(fd);
        }
        removed = syscall(SYS_delete_module, "r36hello", O_NONBLOCK);
    }
    snprintf(log, sizeof(log), "load_rc=%d errno=%d\nparameter_ok=%d\nunload_rc=%d\nresult=%s\n",
             loaded, reason, parameter_ok, removed,
             !loaded && parameter_ok && !removed ? "PASS" : "FAIL");
    send_text(log);
    fd = open("/sd/cubegm/r36-driver-test.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd >= 0) {
        dprintf(fd, "R36 DRIVER TEST\nrelease=%s\nversion=%s\n%s", identity.release, identity.version, log);
        fsync(fd);
        close(fd);
    }
    sync();
    return !loaded && parameter_ok && !removed;
}

static void record_boot(void)
{
    int fd = open("/sd/cubegm/r36-own-kernel-proof.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd >= 0) {
        dprintf(fd, "R36 OWN KERNEL USERSPACE REACHED\nsysname=%s\nrelease=%s\nversion=%s\nmachine=%s\npid=%ld\n",
                identity.sysname, identity.release, identity.version, identity.machine, (long)getpid());
        fsync(fd);
        close(fd);
    }
    phase = "SD mounted; starting module test";
    test_driver();
    phase = "ready";
}

static void command(const char *line)
{
    char text[512];
    if (!strcmp(line, "status") || !strcmp(line, "uname")) {
        snprintf(text, sizeof(text), "R36LAB\nrelease=%.80s\nversion=%.100s\nphase=%s\nsd_ready=%d\ngadget_rc=%d\n",
                 identity.release, identity.version, phase, sd_ready, gadget_result);
        send_text(text);
    } else if (!strcmp(line, "meminfo")) send_file("/proc/meminfo");
    else if (!strcmp(line, "interrupts")) send_file("/proc/interrupts");
    else if (!strcmp(line, "modules")) send_file("/proc/modules");
    else if (!strcmp(line, "driver")) {
        if (sd_ready) test_driver(); else send_text("SD not mounted\n");
    } else if (!strcmp(line, "adc")) {
        send_file("/sys/bus/iio/devices/iio:device0/in_voltage1_raw");
        send_file("/sys/bus/iio/devices/iio:device0/in_voltage5_raw");
    } else if (!strcmp(line, "dmesg")) {
        char log[32768];
        int n = klogctl(3, log, sizeof(log) - 1);
        if (n > 0) { log[n] = 0; send_text(log); }
    } else if (!strcmp(line, "reboot")) {
        send_text("syncing and restarting\n");
        sync();
        if (sd_ready) umount("/sd");
        reboot(RB_AUTOBOOT);
        send_text("restart returned unexpectedly\n");
    } else send_text("commands: status meminfo interrupts modules driver adc dmesg reboot\n");
    send_text("R36LAB> ");
}

int main(void)
{
    char input[128];
    size_t used = 0;
    unsigned int ticks = 0, attempts = 0;
    mkdir("/dev", 0755); mkdir("/proc", 0755); mkdir("/sys", 0755); mkdir("/sd", 0755);
    mount("devtmpfs", "/dev", "devtmpfs", 0, NULL);
    mount("proc", "/proc", "proc", 0, NULL);
    mount("sysfs", "/sys", "sysfs", 0, NULL);
    uname(&identity);
    mark_userspace();
    gadget_result = usb_start();
    if (chdir("/")) return 1;
    phase = "waiting for SD";
    for (;;) {
        if (serial < 0) {
            serial = open("/dev/ttyGS0", O_RDWR | O_NOCTTY | O_NONBLOCK);
            if (serial >= 0) {
                struct termios options;
                if (!tcgetattr(serial, &options)) {
                    cfmakeraw(&options);
                    tcsetattr(serial, TCSANOW, &options);
                }
            }
        }
        if (!sd_ready && attempts < 60 && ticks++ % 20 == 0) {
            attempts++;
            if (!mount("/dev/mmcblk0p1", "/sd", "vfat", MS_NOATIME, "iocharset=iso8859-1")) {
                sd_ready = 1;
                record_boot();
            }
        }
        if (serial >= 0) {
            char c;
            ssize_t n;
            while ((n = read(serial, &c, 1)) > 0) {
                if (c == '\n' || c == '\r') {
                    if (used) { input[used] = 0; command(input); used = 0; }
                } else if (used < sizeof(input) - 1) input[used++] = c;
            }
            if (n < 0 && errno != EAGAIN && errno != EINTR) { close(serial); serial = -1; }
        }
        usleep(50000);
    }
}
