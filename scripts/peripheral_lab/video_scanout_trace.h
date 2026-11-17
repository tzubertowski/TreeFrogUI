/* SPDX-License-Identifier: MIT */
#ifndef R36_VIDEO_SCANOUT_TRACE_H
#define R36_VIDEO_SCANOUT_TRACE_H

struct r36_scanout_health {
    unsigned boot, active, programmed, line, failures, timing, on, pixel, format, width, height, pitch;
};
static uint32_t scanout_hash(const volatile unsigned char *bytes, unsigned pitch)
{
    uint32_t hash = 2166136261u;
    for (unsigned y = 0; y < 480; y++)
        for (unsigned x = 0; x < 1280; x++) hash = (hash ^ bytes[(size_t)y * pitch + x]) * 16777619u;
    return hash;
}
static int scanout_parse(const char *text, struct r36_scanout_health *h)
{
    int end = 0;
    int count = sscanf(text, "boot_descriptor=%x active_descriptor=%x programmed_descriptor=%x line=%u flip_timeouts=%u timing_stable=%u active_on=%u pixel=%x format=%u width=%u height=%u pitch=%u%n",
                       &h->boot, &h->active, &h->programmed, &h->line, &h->failures,
                       &h->timing, &h->on, &h->pixel, &h->format, &h->width, &h->height, &h->pitch, &end);
    return count == 12 && (text[end] == '\0' || (text[end] == '\n' && text[end + 1] == '\0')) ? 0 : -1;
}
static int scanout_valid(const struct r36_scanout_health *h, unsigned pitch)
{
    uint32_t physical = h->pixel & 0x07ffffffu;
    return h->active == h->programmed && h->active != h->boot &&
           h->active >= 0x02f90400u && h->active <= 0x02f90d80u && !(h->active & 31u) &&
           !h->failures && h->timing == 1 && h->on == 1 && h->format == 6 &&
           h->width == 640 && h->height == 480 && h->pitch == pitch &&
           pitch >= 1280 && pitch <= 65536 && h->pixel < 0x10000000u &&
           physical >= 0x1000 && (uint64_t)physical + (uint64_t)pitch * 480 <= 0x02f91000u;
}
static int scanout_health(struct r36_scanout_health *h)
{
    char text[512] = {0};
    int fd = open("/sys/bus/platform/devices/1883a000.display-controller/health", O_RDONLY | O_CLOEXEC);
    ssize_t n;
    if (fd < 0) return -1;
    n = read(fd, text, sizeof(text) - 1); close(fd);
    return n > 0 && n < (ssize_t)sizeof(text) - 1 ? scanout_parse(text, h) : -1;
}
static uint32_t scanout_expected_hash;
static int scanout_expected_ready;

/* Observation only: no register/descriptor writes or extra DRM state changes.
 * The backend lock holds pixels stable; health checks bracket uncached DMA read.
 * Hash agreement does not prove panel visibility. */
static void scanout_trace(const char *phase, uint32_t expected, int have_expected)
{
    struct r36_scanout_health before, after, sample;
    uint32_t mapped_hash, dma_hash;
    void *mapping = MAP_FAILED;
    size_t offset, length;
    int memory = -1, progress = 0;
    if (!active || pixels == MAP_FAILED || !have_expected) goto fail;
    mapped_hash = scanout_hash(pixels, stride);
    if (scanout_health(&before) || !scanout_valid(&before, stride)) goto fail;
    fprintf(stderr, "r36-scanout: phase=%s active=%08x programmed=%08x boot=%08x pixel=%08x format=%u size=%ux%u pitch=%u on=%u timing=%u timeouts=%u\n",
            phase, before.active, before.programmed, before.boot, before.pixel, before.format,
            before.width, before.height, before.pitch, before.on, before.timing, before.failures);
    memory = open("/dev/mem", O_RDONLY | O_SYNC | O_CLOEXEC);
    if (memory < 0) goto fail;
    offset = before.pixel & 4095u;
    length = (offset + (size_t)stride * 480 + 4095u) & ~(size_t)4095u;
    mapping = mmap(NULL, length, PROT_READ, MAP_SHARED, memory, (off_t)((before.pixel & 0x07ffffffu) & ~4095u));
    if (mapping == MAP_FAILED) goto fail;
    dma_hash = scanout_hash((volatile unsigned char *)mapping + offset, stride);
    munmap(mapping, length); mapping = MAP_FAILED;
    close(memory); memory = -1;
    if (scanout_health(&after) || !scanout_valid(&after, stride) ||
        after.active != before.active || after.pixel != before.pixel) goto fail;
    for (unsigned i = 0; i < 12; i++) {
        usleep(5000);
        if (scanout_health(&sample) || !scanout_valid(&sample, stride) ||
            sample.active != before.active || sample.pixel != before.pixel) goto fail;
        if (sample.line != before.line && sample.line > 0 && sample.line <= 518) progress = 1;
    }
    fprintf(stderr, "r36-scanout: phase=%s expected=%08x mapped=%08x dma=%08x raster_progress=%d digital_match=%u physical_visual=NOT_TESTED\n",
            phase, expected, mapped_hash, dma_hash, progress,
            expected == mapped_hash && mapped_hash == dma_hash && progress);
    return;
fail:
    if (mapping != MAP_FAILED) munmap(mapping, length);
    if (memory >= 0) close(memory);
    fprintf(stderr, "r36-scanout: phase=%s observation_failed=1 physical_visual=NOT_TESTED\n", phase);
}
#endif
