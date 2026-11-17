#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>
#include "r36_display_contract.h"
#include "r36_display_abi.h"
#ifdef R36_INPUT_PROBE
#include "input_probe.h"
#endif
#ifdef R36_AUDIO_PROBE
#include "audio_probe.h"
#endif
#ifdef R36_CORE_CONSOLE_PROBE
#include "core_console_probe.h"
#endif

const uint32_t r36_display_abi[] __attribute__((used, section(".r36abi"))) = { R36_DISPLAY_ABI_VALUES };
static int held_drm = -1;
static void *held_pixels;
static const char *health_path = "/sys/bus/platform/devices/1883a000.display-controller/health";

static uint32_t hash_pixels(const volatile unsigned char *p, unsigned pitch)
{
    uint32_t hash = 2166136261u;
    unsigned x, y;
    for (y = 0; y < 480; y++)
        for (x = 0; x < 640 * 2; x++) hash = (hash ^ p[(size_t)y * pitch + x]) * 16777619u;
    return hash;
}

static void fill_pixels(void *p, unsigned pitch)
{
    static const uint16_t colors[8] = {0xffff, 0xffe0, 0x07ff, 0x07e0, 0xf81f, 0xf800, 0x001f, 0x0000};
    unsigned x, y;
    for (y = 0; y < 480; y++) {
        uint16_t *row = (uint16_t *)((unsigned char *)p + (size_t)y * pitch);
        for (x = 0; x < 640; x++) row[x] = colors[x / 80];
    }
}

static void *physical_read(int fd, uint32_t address, size_t bytes, void **mapping, size_t *length)
{
    size_t offset = address & 4095u;
    *length = (offset + bytes + 4095u) & ~4095u;
    *mapping = mmap(NULL, *length, PROT_READ, MAP_SHARED, fd, address & ~4095u);
    return *mapping == MAP_FAILED ? NULL : (unsigned char *)*mapping + offset;
}

static int inspect_display(void)
{
    int fd = open("/dev/mem", O_RDONLY | O_SYNC | O_CLOEXEC), match = 0, progress = 0;
    volatile uint32_t *regs, *descriptor;
    void *mapping;
    size_t length;
    uint32_t raw, physical, words[8], first;
    unsigned i;
    if (fd < 0) return -1;
    regs = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, 0x1883a000);
    if (regs == MAP_FAILED) { close(fd); return -1; }
    printf("DE control=%08x interrupt=%08x total=%08x hsync=%08x vsync=%08x line_compare=%08x\n",
           regs[0], regs[1], regs[3], regs[4], regs[6], regs[0x30 / 4]);
    printf("layer0 control=%08x descriptor=%08x active_control=%08x active_descriptor=%08x\n",
           regs[0x300 / 4], regs[0x304 / 4], regs[0xb00 / 4], regs[0xb04 / 4]);
    printf("layer1 control=%08x descriptor=%08x active_control=%08x active_descriptor=%08x\n",
           regs[0x380 / 4], regs[0x384 / 4], regs[0xb80 / 4], regs[0xb84 / 4]);
    first = regs[2] >> 16 & 0xfff;
    for (i = 0; i < 12; i++) {
        uint32_t line = regs[2] >> 16 & 0xfff;
        printf("line_sample=%u\n", line);
        if (line != first && line > 0 && line <= R36_DISPLAY_VTOTAL) progress = 1;
        usleep(5000);
    }
    raw = regs[0xb04 / 4];
    if (!r36_display_descriptor(raw, &physical)) {
        descriptor = physical_read(fd, physical, 0x280, &mapping, &length);
        if (descriptor) {
            for (i = 0; i < 8; i++) { words[i] = descriptor[i]; printf("boot_word%u=%08x\n", i, words[i]); }
            match = !r36_display_header(words) && regs[0xb04 / 4] == raw;
            munmap(mapping, length);
        }
    } else puts("boot_descriptor_outside_known_header=1");
    printf("timing_match=%d boot_header_match=%d raster_progress=%d\n", r36_display_timing(regs[3]), match, progress);
    match = match && progress && r36_display_timing(regs[3]) && (regs[0xb00 / 4] & 1) && !(regs[0xb80 / 4] & 1);
    munmap((void *)regs, 4096); close(fd);
    return match ? 0 : -1;
}

struct health {
    unsigned boot, active, programmed, line, failures, timing, on, pixel, format, width, height, pitch;
};

static int health(struct health *value)
{
    char text[512] = {0};
    int fd = open(health_path, O_RDONLY | O_CLOEXEC);
    ssize_t n;
    if (fd < 0) return -1;
    n = read(fd, text, sizeof(text) - 1); close(fd);
    if (n <= 0) return -1;
    text[n] = 0;
    printf("health=%s", text);
    return sscanf(text, "boot_descriptor=%x active_descriptor=%x programmed_descriptor=%x line=%u flip_timeouts=%u timing_stable=%u active_on=%u pixel=%x format=%u width=%u height=%u pitch=%u",
                  &value->boot, &value->active, &value->programmed, &value->line, &value->failures,
                  &value->timing, &value->on, &value->pixel, &value->format, &value->width, &value->height, &value->pitch) == 12 ? 0 : -1;
}

static unsigned long display_irqs(void)
{
    FILE *file = fopen("/proc/interrupts", "r");
    char line[512];
    unsigned long result = 0;
    if (!file) return 0;
    while (fgets(line, sizeof(line), file)) {
        char *colon;
        if (strstr(line, "1883a000.display-controller") && (colon = strchr(line, ':')) != NULL)
            result = strtoul(colon + 1, NULL, 10);
    }
    fclose(file);
    return result;
}

static int checked_ioctl(unsigned long request, void *argument, const char *phase)
{
    int result = ioctl(held_drm, request, argument);
    int reason = result ? errno : 0;
    printf("kms_ioctl=%s rc=%d errno=%d\n", phase, result, reason);
    errno = reason;
    return result;
}

static int kms_test(void)
{
    struct drm_mode_card_res resources = {0};
    struct drm_mode_get_connector connector = {0};
    struct drm_mode_modeinfo modes[64], mode = {0};
    struct drm_mode_create_dumb dumb = {.width = 640, .height = 480, .bpp = 16};
    struct drm_mode_map_dumb map = {0};
    struct drm_mode_fb_cmd fb = {0};
    struct drm_mode_crtc crtc = {0};
    struct drm_version version = {0};
    struct health current = {0};
    uint32_t crtcs[64], connectors[64], encoders[64], properties[64], expected, actual, physical;
    uint64_t property_values[64];
    unsigned long before, after;
    int fd, rc, i, found = 0, progress = 0, memory;
    char name[64] = {0};
    void *uncached, *mapping;
    size_t length;
    if (inspect_display()) { puts("activation_refused=passive_contract_failed"); return -1; }
    fd = open("/sd/cubegm/r36_hc16xx_drm.ko", O_RDONLY | O_CLOEXEC);
    if (fd < 0) return -1;
    rc = syscall(SYS_finit_module, fd, "", 0); close(fd);
    printf("display_module_load_rc=%d errno=%d\n", rc, rc ? errno : 0);
    if (rc) return -1;
    held_drm = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
    if (held_drm < 0) return -1;
    version.name = name; version.name_len = sizeof(name) - 1;
    if (checked_ioctl(DRM_IOCTL_VERSION, &version, "version") || strcmp(name, "r36-hc16xx")) return -1;
    resources.crtc_id_ptr = (uintptr_t)crtcs; resources.count_crtcs = 64;
    resources.connector_id_ptr = (uintptr_t)connectors; resources.count_connectors = 64;
    if (checked_ioctl(DRM_IOCTL_MODE_GETRESOURCES, &resources, "resources") || resources.count_crtcs != 1 || resources.count_connectors != 1) return -1;
    connector.connector_id = connectors[0];
    if (checked_ioctl(DRM_IOCTL_MODE_GETCONNECTOR, &connector, "connector_count") ||
        connector.count_modes > 64 || connector.count_encoders > 64 || connector.count_props > 64) return -1;
    connector.modes_ptr = (uintptr_t)modes; connector.count_modes = 64;
    connector.encoders_ptr = (uintptr_t)encoders; connector.count_encoders = 64;
    /* Count-query fills count_props too. A second query must provide matching
     * arrays: retaining a nonzero count with null pointers produces EFAULT. */
    connector.props_ptr = (uintptr_t)properties;
    connector.prop_values_ptr = (uintptr_t)property_values; connector.count_props = 64;
    if (checked_ioctl(DRM_IOCTL_MODE_GETCONNECTOR, &connector, "connector_data") || connector.connection != 1 ||
        connector.count_modes > 64 || connector.count_encoders > 64 || connector.count_props > 64) return -1;
    for (i = 0; i < (int)connector.count_modes; i++) {
        if (modes[i].hdisplay == 640 && modes[i].vdisplay == 480 &&
            modes[i].htotal == R36_DISPLAY_HTOTAL && modes[i].vtotal == R36_DISPLAY_VTOTAL) {
            mode = modes[i]; found = 1; break;
        }
    }
    if (!found) return -1;
    if (checked_ioctl(DRM_IOCTL_MODE_CREATE_DUMB, &dumb, "create_dumb")) return -1;
    if (dumb.pitch < 1280 || dumb.pitch > 16383 || dumb.size > 16 * 1024 * 1024 || dumb.size < (uint64_t)dumb.pitch * 480) return -1;
    map.handle = dumb.handle;
    if (checked_ioctl(DRM_IOCTL_MODE_MAP_DUMB, &map, "map_dumb")) return -1;
    printf("kms_mmap_offset=%llu bytes=%llu\n", (unsigned long long)map.offset, (unsigned long long)dumb.size);
    held_pixels = mmap(NULL, dumb.size, PROT_READ | PROT_WRITE, MAP_SHARED, held_drm, (off_t)map.offset);
    if (held_pixels == MAP_FAILED) return -1;
    memset(held_pixels, 0, dumb.size); fill_pixels(held_pixels, dumb.pitch);
    expected = hash_pixels(held_pixels, dumb.pitch);
    fb.width = 640; fb.height = 480; fb.pitch = dumb.pitch; fb.bpp = 16; fb.depth = 16; fb.handle = dumb.handle;
    if (checked_ioctl(DRM_IOCTL_MODE_ADDFB, &fb, "addfb")) return -1;
    crtc.set_connectors_ptr = (uintptr_t)connectors; crtc.count_connectors = 1;
    crtc.crtc_id = crtcs[0]; crtc.fb_id = fb.fb_id; crtc.mode_valid = 1; crtc.mode = mode;
    puts("modeset_requested=1");
    if (checked_ioctl(DRM_IOCTL_MODE_SETCRTC, &crtc, "setcrtc")) return -1;
    for (i = 0; i < 100; i++) {
        if (!health(&current) && current.active == current.programmed && current.active != current.boot && current.on) break;
        usleep(10000);
    }
    if (i == 100 || current.failures || !current.timing || current.format != 6 ||
        current.width != 640 || current.height != 480 || current.pitch != dumb.pitch) return -1;
    before = display_irqs();
    {
        union drm_wait_vblank wait = {0};
        wait.request.type = _DRM_VBLANK_RELATIVE;
        wait.request.sequence = 2;
        if (checked_ioctl(DRM_IOCTL_WAIT_VBLANK, &wait, "wait_vblank")) return -1;
    }
    for (i = 0; i < 20; i++) {
        struct health next;
        usleep(10000);
        if (health(&next)) return -1;
        if (next.line != current.line && next.line > 0 && next.line <= R36_DISPLAY_VTOTAL) progress = 1;
        if (next.failures || !next.timing || next.active != current.programmed || !next.on) return -1;
    }
    /* WAIT_VBLANK drops its IRQ reference when it returns; force another
     * observed vblank rather than assuming IRQs stay enabled while sampling. */
    {
        union drm_wait_vblank wait = {0};
        wait.request.type = _DRM_VBLANK_RELATIVE; wait.request.sequence = 2;
        if (checked_ioctl(DRM_IOCTL_WAIT_VBLANK, &wait, "wait_vblank_after")) return -1;
    }
    after = display_irqs();
    printf("kms_irq_before=%lu kms_irq_after=%lu raster_progress=%d\n", before, after, progress);
    {
        FILE *interrupts = fopen("/proc/interrupts", "r");
        char line[512];
        if (interrupts) {
            while (fgets(line, sizeof(line), interrupts)) printf("irq_snapshot=%s", line);
            fclose(interrupts);
        }
    }
    if (!progress || after <= before) return -1;
    if (r36_display_ddr(current.pixel, &physical) || physical < 0x1000 ||
        (uint64_t)physical + (uint64_t)dumb.pitch * 480 > 0x02f91000) return -1;
    memory = open("/dev/mem", O_RDONLY | O_SYNC | O_CLOEXEC);
    if (memory < 0) return -1;
    uncached = physical_read(memory, physical, (size_t)dumb.pitch * 480, &mapping, &length);
    if (!uncached) { close(memory); return -1; }
    actual = hash_pixels(uncached, dumb.pitch);
    munmap(mapping, length); close(memory);
    printf("pixel_hash_cpu=%08x pixel_hash_dma=%08x irq_before=%lu irq_after=%lu raster_progress=%d\n", expected, actual, before, after, progress);
    if (expected != actual) return -1;
    puts("display_scanout=PASS\nphysical_panel_visual_confirmation=NOT_TESTED");
    return 0;
}

static int prepare_pid1(const struct utsname *info)
{
    char id[80] = {0};
    FILE *file;
    int fd, attempt;
    volatile uint32_t *trace;
    mkdir("/dev", 0755); mkdir("/proc", 0755); mkdir("/sys", 0755); mkdir("/sd", 0755);
    mount("devtmpfs", "/dev", "devtmpfs", 0, NULL); mount("proc", "/proc", "proc", 0, NULL); mount("sysfs", "/sys", "sysfs", 0, NULL);
    fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd >= 0) {
        trace = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0x02f91000);
        if (trace != MAP_FAILED) { trace[4] = 6; __sync_synchronize(); munmap((void *)trace, 4096); }
        close(fd);
    }
    for (attempt = 0; attempt < 20; attempt++) {
        if (!mount("/dev/mmcblk0p1", "/sd", "vfat", MS_NOATIME, "iocharset=iso8859-1")) break;
        sleep(1);
    }
    if (attempt == 20) return -1;
    file = fopen("/sd/cubegm/r36-run-id.txt", "r");
    if (file) { if (!fgets(id, sizeof(id), file)) id[0] = 0; fclose(file); }
    id[strcspn(id, "\r\n")] = 0;
    file = fopen("/sd/cubegm/r36-own-kernel-proof.txt", "w");
    if (file) {
        fprintf(file, "R36 OWN KERNEL USERSPACE REACHED\nrun_id=%s\nsysname=Linux\nrelease=%s\nversion=%s\nmachine=%s\npid=1\n", id, info->release, info->version, info->machine);
        fflush(file); fsync(fileno(file)); fclose(file);
    }
    fd = open("/sd/cubegm/r36-display-probe.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return -1;
    dup2(fd, 1); dup2(fd, 2); close(fd);
    printf("run_id=%s\n", id);
    return 0;
}

int main(int argc, char **argv)
{
    struct utsname info;
    int pid1 = getpid() == 1, result;
    setvbuf(stdout, NULL, _IOLBF, 0);
    if (argc == 2 && !strcmp(argv[1], "--selftest")) {
        unsigned char *p = malloc(1344u * 480);
        uint32_t a, b;
        if (!p) return 2;
        memset(p, 0x6d, 1344u * 480); fill_pixels(p, 1344);
        a = hash_pixels(p, 1344); p[0] ^= 1; b = hash_pixels(p, 1344);
        result = a != b && p[1280] == 0x6d;
        printf("pattern_hash=%08x corrupted_hash=%08x padding_preserved=%d selftest=%s\n", a, b, p[1280] == 0x6d, result ? "PASS" : "FAIL");
        free(p); return result ? 0 : 2;
    }
    if (uname(&info)) return 1;
    if (pid1 && prepare_pid1(&info)) for (;;) pause();
    puts("R36 DISPLAY PROBE V1");
    printf("kernel=%s %s\n", info.release, info.version);
    if (pid1 && argc == 2 && !strcmp(argv[1], "--display-kms-probe") &&
        !strncmp(info.release, "7.2.0-rc5-r36", sizeof("7.2.0-rc5-r36") - 1)) result = kms_test();
    else if (pid1 || (argc == 2 && !strcmp(argv[1], "--inspect"))) {
        result = inspect_display();
        puts(result ? "display_inspection=FAIL" : "display_inspection=PASS");
    } else return 2;
#ifdef R36_INPUT_PROBE
    if (pid1 && result == 0) {
        int input_result = input_probe();
        printf("input_probe_rc=%d\n", input_result);
        if (input_result) result = input_result;
    }
#endif
#ifdef R36_AUDIO_PROBE
    if (pid1 && result == 0 && !strncmp(info.release, "7.2.0-rc5-r36", sizeof("7.2.0-rc5-r36") - 1)) {
        int audio_result = audio_silent_probe();
        if (audio_result) result = audio_result;
    }
#endif
#ifdef R36_CORE_CONSOLE_PROBE
    if (pid1 && result == 0 && !strncmp(info.release, "7.2.0-rc5-r36", sizeof("7.2.0-rc5-r36") - 1)) {
        int core_result = console_core_probe();
        printf("core_probe_rc=%d\n", core_result);
        if (core_result) result = core_result;
    }
#endif
    printf("probe_rc=%d errno=%d\nR36 DISPLAY PROBE END\n", result, result ? errno : 0);
    fflush(stdout);
    if (pid1) {
        fsync(1); close(1); close(2); sync();
        if (umount("/sd")) { mount(NULL, "/sd", "vfat", MS_REMOUNT | MS_RDONLY, NULL); sync(); }
        /* GEM buffers and DRM fd remain owned until the watchdog resets the SoC. */
        for (;;) pause();
    }
    return result ? 1 : 0;
}
