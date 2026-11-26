/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <drm/drm.h>
#include <drm/drm_mode.h>
#include "rgb565_scale.h"

/* New backend, not a wrapper around the stock driver. Only observed video ABI
 * is exported; optional GE objects and unimplemented sound are deliberately
 * absent. Errors return -1. No dummy-success or MMIO access is used.
 *
 * Two dumb buffers: the scaler always writes the inactive one and a
 * DRM_MODE_PAGE_FLIP with a DRM_EVENT_FLIP_COMPLETE wait swaps it in, so the
 * buffer being scanned out is never rewritten. The first frame and any
 * resynchronisation after a failed flip use SETCRTC. */
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static int device = -1, active, needs_modeset;
static unsigned long submitted_frames;
static uint64_t flip_sequence;
static uint32_t connector_id, crtc_id, stride;
static uint32_t framebuffer[2], handle[2];
static uint64_t buffer_size;
static void *buffers[2] = {MAP_FAILED, MAP_FAILED};
static void *pixels;                 /* front: buffer expected on screen */
static void *render_pixels;          /* back: scaler target */
static int front, back;
static struct drm_mode_modeinfo native_mode;
static struct drm_mode_crtc previous;

#ifdef R36_SCANOUT_TRACE
#include "video_scanout_trace.h"
#endif

#define R36_FLIP_TIMEOUT_MS 250
#define R36_FLIP_EVENT_ATTEMPTS 8

static void swap_buffers(void)
{
    int old_front = front;

    front = back;
    back = old_front;
    pixels = buffers[front];
    render_pixels = buffers[back];
}

static void cleanup(void)
{
    int i;

    if (device < 0) return;
    if (active) {
        if (previous.mode_valid && previous.fb_id) {
            previous.set_connectors_ptr = (uintptr_t)&connector_id;
            previous.count_connectors = 1;
            if (ioctl(device, DRM_IOCTL_MODE_SETCRTC, &previous)) {
                fputs("r36-drm: restore failed; retaining scanout buffer until reset\n", stderr);
                return;
            }
        } else {
            struct drm_mode_crtc off = {.crtc_id = crtc_id};
            if (ioctl(device, DRM_IOCTL_MODE_SETCRTC, &off)) {
                fputs("r36-drm: disable failed; retaining scanout buffer until reset\n", stderr);
                return;
            }
        }
    }
    active = 0;
    needs_modeset = 0;
    for (i = 0; i < 2; i++) {
        if (buffers[i] != MAP_FAILED) munmap(buffers[i], buffer_size);
        buffers[i] = MAP_FAILED;
        if (framebuffer[i]) ioctl(device, DRM_IOCTL_MODE_RMFB, &framebuffer[i]);
        framebuffer[i] = 0;
        if (handle[i]) {
            struct drm_mode_destroy_dumb destroy = {.handle = handle[i]};
            ioctl(device, DRM_IOCTL_MODE_DESTROY_DUMB, &destroy);
        }
        handle[i] = 0;
    }
    close(device); device = -1;
    pixels = render_pixels = MAP_FAILED;
    front = 0; back = 1;
    buffer_size = 0; stride = 0;
}

static int r36_modeset(void)
{
    struct drm_mode_crtc crtc = {.set_connectors_ptr = (uintptr_t)&connector_id,
        .count_connectors = 1, .crtc_id = crtc_id, .fb_id = framebuffer[back],
        .mode_valid = 1, .mode = native_mode};
    union drm_wait_vblank wait = {0};

    if (ioctl(device, DRM_IOCTL_MODE_SETCRTC, &crtc)) return -1;
    active = 1;
    needs_modeset = 0;
    swap_buffers();
    wait.request.type = _DRM_VBLANK_RELATIVE;
    wait.request.sequence = 1;
    if (ioctl(device, DRM_IOCTL_WAIT_VBLANK, &wait)) return -1;
    return 0;
}

static int r36_flip(uint32_t fb_id, uint64_t token)
{
    struct drm_mode_crtc_page_flip flip = {0};
    int attempts = 0;

    flip.crtc_id = crtc_id;
    flip.fb_id = fb_id;
    flip.flags = DRM_MODE_PAGE_FLIP_EVENT;
    flip.user_data = token;
    if (ioctl(device, DRM_IOCTL_MODE_PAGE_FLIP, &flip)) return -1;
    for (;;) {
        struct pollfd polled = {.fd = device, .events = POLLIN};
        struct drm_event_vblank event;
        ssize_t bytes;
        int ready = poll(&polled, 1, R36_FLIP_TIMEOUT_MS);

        if (ready < 0 && errno == EINTR) continue;
        if (ready <= 0 || !(polled.revents & POLLIN)) return -1;
        bytes = read(device, &event, sizeof(event));
        if (bytes < 0 && errno == EINTR) continue;
        if (bytes != (ssize_t)sizeof(event)) return -1;
        if (event.base.type != DRM_EVENT_FLIP_COMPLETE || event.base.length != sizeof(event))
            return -1;
        if (event.user_data == token) return 0;
        if (++attempts >= R36_FLIP_EVENT_ATTEMPTS) return -1;
    }
}

int video_drivers_init(void)
{
    struct drm_version version = {0};
    char name[64] = {0};
    struct drm_mode_card_res resources = {0};
    struct drm_mode_get_connector connector = {0};
    struct drm_mode_modeinfo modes[64];
    struct drm_mode_create_dumb dumb = {.width = 640, .height = 480, .bpp = 16};
    struct drm_mode_map_dumb map = {0};
    struct drm_mode_fb_cmd fb = {0};
    uint32_t crtcs[64], connectors[64], encoders[64], props[64];
    uint64_t values[64];
    const char *path = getenv("R36_DRM_DEVICE");
    int found = 0, result = -1, i;
    const char *phase = "open";
    unsigned int j;
    pthread_mutex_lock(&lock);
    if (device >= 0) { result = 1; goto finish; }
    device = open(path ? path : "/dev/dri/card0", O_RDWR | O_CLOEXEC);
    if (device < 0) goto fail;
    phase = "version";
    version.name = name; version.name_len = sizeof(name) - 1;
    if (ioctl(device, DRM_IOCTL_VERSION, &version) || strcmp(name, "r36-hc16xx")) goto fail;
    phase = "resources";
    resources.crtc_id_ptr = (uintptr_t)crtcs; resources.count_crtcs = 64;
    resources.connector_id_ptr = (uintptr_t)connectors; resources.count_connectors = 64;
    if (ioctl(device, DRM_IOCTL_MODE_GETRESOURCES, &resources) || resources.count_crtcs != 1 || resources.count_connectors != 1) goto fail;
    phase = "connector";
    connector_id = connectors[0]; crtc_id = crtcs[0];
    connector.connector_id = connector_id;
    /* A zero-mode count query asks DRM to populate/probe connector modes.
     * Passing a full buffer immediately can return an unprobed empty list. */
    if (ioctl(device, DRM_IOCTL_MODE_GETCONNECTOR, &connector)) goto fail;
    if (connector.count_modes > 64 || connector.count_encoders > 64 || connector.count_props > 64) {
        errno = EOVERFLOW; goto fail;
    }
    connector.modes_ptr = (uintptr_t)modes; connector.count_modes = 64;
    connector.encoders_ptr = (uintptr_t)encoders; connector.count_encoders = 64;
    connector.props_ptr = (uintptr_t)props; connector.prop_values_ptr = (uintptr_t)values; connector.count_props = 64;
    if (ioctl(device, DRM_IOCTL_MODE_GETCONNECTOR, &connector)) goto fail;
    if (connector.connection != 1 || connector.count_modes > 64 || connector.count_encoders > 64 || connector.count_props > 64) {
        errno = connector.connection != 1 ? ENODEV : EOVERFLOW; goto fail;
    }
    for (j = 0; j < connector.count_modes; j++) {
        if (modes[j].hdisplay == 640 && modes[j].vdisplay == 480 &&
            modes[j].htotal == 868 && modes[j].vtotal == 518) {
            native_mode = modes[j]; found = 1; break;
        }
    }
    if (!found) { errno = ENOENT; goto fail; }
    phase = "getcrtc";
    memset(&previous, 0, sizeof(previous)); previous.crtc_id = crtc_id;
    if (ioctl(device, DRM_IOCTL_MODE_GETCRTC, &previous)) goto fail;
    for (i = 0; i < 2; i++) {
        phase = "create_dumb";
        if (ioctl(device, DRM_IOCTL_MODE_CREATE_DUMB, &dumb)) goto fail;
        handle[i] = dumb.handle;
        if (!i) {
            stride = dumb.pitch; buffer_size = dumb.size;
            if (stride < 1280 || stride > 65536 || buffer_size < (uint64_t)stride * 480 || buffer_size > 16 * 1024 * 1024) goto fail;
        } else if (dumb.pitch != stride || dumb.size != buffer_size) {
            errno = EINVAL; goto fail;
        }
        phase = "map_dumb";
        memset(&map, 0, sizeof(map)); map.handle = handle[i];
        if (ioctl(device, DRM_IOCTL_MODE_MAP_DUMB, &map)) goto fail;
        if (!i) fprintf(stderr, "r36-drm: pitch=%u bytes=%llu offset=%llu off_t_bytes=%u\n", stride,
                (unsigned long long)buffer_size, (unsigned long long)map.offset, (unsigned int)sizeof(off_t));
        phase = "mmap";
        buffers[i] = mmap(NULL, buffer_size, PROT_READ | PROT_WRITE, MAP_SHARED, device, (off_t)map.offset);
        if (buffers[i] == MAP_FAILED) goto fail;
        memset(buffers[i], 0, buffer_size);
        memset(&fb, 0, sizeof(fb));
        fb.width = 640; fb.height = 480; fb.pitch = stride; fb.bpp = fb.depth = 16; fb.handle = handle[i];
        phase = "addfb";
        if (ioctl(device, DRM_IOCTL_MODE_ADDFB, &fb)) goto fail;
        framebuffer[i] = fb.fb_id;
    }
    front = 0; back = 1;
    pixels = buffers[front];
    render_pixels = buffers[back];
    needs_modeset = 0;
    result = 1;
    goto finish;
fail:
    fprintf(stderr, "r36-drm: init failed phase=%s errno=%d\n", phase, errno);
    cleanup();
finish:
    pthread_mutex_unlock(&lock);
    return result;
}

int video_driver_disp_frame(void *source, int width, int height, int pitch_bytes)
{
    int result = -1;
    pthread_mutex_lock(&lock);
    if (device < 0) goto finish;
    /* A failed flip leaves the scanout target unknown; re-establish it with a
     * synchronous modeset before touching either buffer again. */
    if (needs_modeset && r36_modeset()) goto finish;
    if (r36_scale565(render_pixels, stride, source, width, height, pitch_bytes)) goto finish;
    __sync_synchronize();
#ifdef R36_SCANOUT_TRACE
    if (!submitted_frames) {
        scanout_expected_hash = scanout_hash(render_pixels, stride);
        scanout_expected_ready = 1;
        if (source && width == 640 && height == 480 && pitch_bytes == 1280)
            fprintf(stderr, "r36-scanout: callback_source=%08x scaled_target=%08x identity_geometry=1\n",
                    scanout_hash(source, pitch_bytes), scanout_expected_hash);
    }
#endif
    if (!active) {
        if (r36_modeset()) goto finish;
    } else if (r36_flip(framebuffer[back], ++flip_sequence)) {
        needs_modeset = 1;
        goto finish;
    } else {
        swap_buffers();
    }
    submitted_frames++;
#ifdef R36_SCANOUT_TRACE
    if (submitted_frames == 1) scanout_trace("first", scanout_expected_hash, scanout_expected_ready);
#endif
    if (submitted_frames == 1 || submitted_frames % 60 == 0)
        fprintf(stderr, "r36-drm: submitted_frames=%lu source=%dx%d pitch=%d\n", submitted_frames, width, height, pitch_bytes);
    result = 0;
finish:
    pthread_mutex_unlock(&lock);
    return result;
}

#ifdef R36_SCANOUT_TRACE
void r36_scanout_live_checkpoint(void)
{
    pthread_mutex_lock(&lock);
    fprintf(stderr, "r36-scanout: live_submitted_frames=%lu\n", submitted_frames);
    if (submitted_frames == 1)
        scanout_trace("late_live", scanout_expected_hash, scanout_expected_ready);
    else
        fputs("r36-scanout: phase=late_live observation_failed=1\n", stderr);
    pthread_mutex_unlock(&lock);
}
#endif

void video_driver_deinit(void)
{
    pthread_mutex_lock(&lock);
#ifdef R36_SCANOUT_TRACE
    if (submitted_frames == 1) scanout_trace("before_cleanup", scanout_expected_hash, scanout_expected_ready);
#endif
    cleanup();
    pthread_mutex_unlock(&lock);
}
