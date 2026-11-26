#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <linux/input.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/utsname.h>
#include <unistd.h>

static void dump(const char *path, size_t limit)
{
    char data[4096];
    ssize_t n;
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    printf("\nFILE %s errno=%d\n", path, fd < 0 ? errno : 0);
    if (fd < 0) return;
    while (limit && (n = read(fd, data, limit < sizeof(data) ? limit : sizeof(data))) > 0) {
        fwrite(data, 1, (size_t)n, stdout);
        limit -= (size_t)n;
    }
    close(fd);
    puts("\nEND_FILE");
}

static void framebuffer(const char *path)
{
    struct fb_fix_screeninfo fix = {0};
    struct fb_var_screeninfo var = {0};
    int fd = open(path, O_RDONLY | O_CLOEXEC), rc;
    printf("\nFRAMEBUFFER %s open_errno=%d\n", path, fd < 0 ? errno : 0);
    if (fd < 0) return;
    rc = ioctl(fd, FBIOGET_FSCREENINFO, &fix);
    printf("fix_rc=%d errno=%d struct_bytes=%zu\n", rc, rc < 0 ? errno : 0, sizeof(fix));
    if (!rc) {
        printf("id=%.16s smem_start=0x%08lx smem_len=%u line_length=%u type=%u visual=%u\n",
               fix.id, fix.smem_start, fix.smem_len, fix.line_length, fix.type, fix.visual);
        printf("mmio_start=0x%08lx mmio_len=%u accel=%u\n", fix.mmio_start, fix.mmio_len, fix.accel);
    }
    rc = ioctl(fd, FBIOGET_VSCREENINFO, &var);
    printf("var_rc=%d errno=%d struct_bytes=%zu\n", rc, rc < 0 ? errno : 0, sizeof(var));
    if (!rc) {
        printf("size=%ux%u virtual=%ux%u offset=%u,%u bpp=%u nonstd=%u rotate=%u\n",
               var.xres, var.yres, var.xres_virtual, var.yres_virtual, var.xoffset, var.yoffset,
               var.bits_per_pixel, var.nonstd, var.rotate);
        printf("red=%u,%u green=%u,%u blue=%u,%u alpha=%u,%u\n",
               var.red.offset, var.red.length, var.green.offset, var.green.length,
               var.blue.offset, var.blue.length, var.transp.offset, var.transp.length);
        printf("pixclock=%u margins=%u,%u,%u,%u sync=%u,%u vmode=%u\n", var.pixclock,
               var.left_margin, var.right_margin, var.upper_margin, var.lower_margin,
               var.hsync_len, var.vsync_len, var.vmode);
    }
    close(fd);
}

static void input_devices(void)
{
    unsigned i;
    for (i = 0; i < 16; i++) {
        char path[64], name[256] = {0}, phys[256] = {0};
        struct input_id id = {0};
        unsigned char keys[128] = {0};
        int fd, rc;
        snprintf(path, sizeof(path), "/dev/input/event%u", i);
        fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0) continue;
        ioctl(fd, EVIOCGNAME(sizeof(name)), name);
        ioctl(fd, EVIOCGPHYS(sizeof(phys)), phys);
        ioctl(fd, EVIOCGID, &id);
        printf("\nINPUT %s name=%s phys=%s id=%04x:%04x:%04x:%04x\n", path, name, phys,
               id.bustype, id.vendor, id.product, id.version);
        rc = ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(keys)), keys);
        printf("key_capabilities_rc=%d bits=", rc);
        if (rc > 0) {
            int bit;
            for (bit = 0; bit < rc * 8; bit++)
                if (keys[bit / 8] & (1u << (bit % 8))) printf(" %d", bit);
        }
        putchar('\n');
        close(fd);
    }
}

static void ui_processes(void)
{
    struct dirent *entry;
    DIR *directory = opendir("/proc");
    if (!directory) return;
    while ((entry = readdir(directory)) != NULL) {
        char path[96], comm[80] = {0}, executable[1024] = {0};
        int fd;
        ssize_t n;
        if (entry->d_name[0] < '0' || entry->d_name[0] > '9') continue;
        if (strlen(entry->d_name) > 16) continue;
        snprintf(path, sizeof(path), "/proc/%.16s/comm", entry->d_name);
        fd = open(path, O_RDONLY | O_CLOEXEC);
        if (fd < 0) continue;
        n = read(fd, comm, sizeof(comm) - 1);
        close(fd);
        if (n <= 0) continue;
        comm[strcspn(comm, "\r\n")] = 0;
        if (!strstr(comm, "frog") && !strstr(comm, "pico") && !strstr(comm, "rkgame") &&
            !strstr(comm, "cubevol") && !strstr(comm, "tfmtp")) continue;
        snprintf(path, sizeof(path), "/proc/%.16s/exe", entry->d_name);
        n = readlink(path, executable, sizeof(executable) - 1);
        if (n >= 0) executable[n] = 0;
        printf("\nPROCESS pid=%s comm=%s executable=%s\n", entry->d_name, comm, executable);
        snprintf(path, sizeof(path), "/proc/%.16s/maps", entry->d_name);
        dump(path, 16384);
    }
    closedir(directory);
}

int main(void)
{
    struct utsname info;
    setvbuf(stdout, NULL, _IOLBF, 0);
    puts("R36 PERIPHERAL READ-ONLY INVENTORY V1");
    if (!uname(&info)) printf("kernel=%s %s machine=%s pointer_bytes=%zu\n", info.release,
                             info.version, info.machine, sizeof(void *));
    framebuffer("/dev/fb0");
    framebuffer("/dev/fb1");
    input_devices();
    dump("/proc/asound/cards", 8192);
    dump("/proc/asound/pcm", 8192);
    dump("/proc/bus/input/devices", 16384);
    ui_processes();
    puts("R36 PERIPHERAL INVENTORY END");
    return 0;
}
