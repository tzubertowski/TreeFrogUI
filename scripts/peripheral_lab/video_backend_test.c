/* SPDX-License-Identifier: MIT
 * Native Linux test of the actual backend with a synthetic DRM ioctl device.
 * No display device is opened and no target hardware is contacted.
 *
 * The mock tracks which buffer the display scans out and hashes it at every
 * activation: if the scaler ever rewrites the active scanout buffer the test
 * aborts, which is the double-buffering contract this backend must keep. */
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <assert.h>
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
static int fail_open, fail_modeset, fail_flip_ioctl, fail_flip_wait;
static int closes, maps, munmaps, sets, waits, flips, rmfbs, destroys;
static int dumb_count, fb_count, screen_idx = -1;
static uint32_t screen_hash;
static uint64_t event_queue[16];
static int event_head, event_tail;
static unsigned char mock_buffers[2][1280 * 480];

static uint32_t hash_buffer(const unsigned char *bytes)
{
    uint32_t hash = 2166136261u;
    for (size_t i = 0; i < sizeof(mock_buffers[0]); i++) hash = (hash ^ bytes[i]) * 16777619u;
    return hash;
}
static int fb_index(uint32_t fb_id)
{
    if (fb_id == 13) return 0;
    if (fb_id == 15) return 1;
    return -1;
}
static void activate(int idx)
{
    if (screen_idx >= 0)
        assert(hash_buffer(mock_buffers[screen_idx]) == screen_hash &&
               "CPU rewrote the active scanout buffer");
    if (idx < 0) { screen_idx = -1; return; }
    screen_idx = idx;
    screen_hash = hash_buffer(mock_buffers[idx]);
}
static int fake_open(const char *path, int flags) { (void)path; (void)flags; if (fail_open) { errno=ENOENT; return -1; } return 42; }
static int fake_close(int fd) { assert(fd==42); closes++; return 0; }
static void *fake_mmap(void *p,size_t n,int prot,int flags,int fd,off_t offset) {
    (void)p;(void)prot;(void)flags; assert(fd==42 && n==sizeof(mock_buffers[0]));
    if (offset == (off_t)UINT64_C(0x100000000)) { maps++; return mock_buffers[0]; }
    if (offset == (off_t)UINT64_C(0x180000000)) { maps++; return mock_buffers[1]; }
    assert(!"unexpected mmap offset"); return NULL;
}
static int fake_munmap(void *p,size_t n) {
    assert(n==sizeof(mock_buffers[0]));
    assert(p==mock_buffers[0] || p==mock_buffers[1]); munmaps++; return 0;
}
static int fake_ioctl(int fd,unsigned long request,void *arg) {
    assert(fd==42);
    switch (request) {
    case DRM_IOCTL_VERSION: { struct drm_version *v=arg; strcpy(v->name,"r36-hc16xx"); break; }
    case DRM_IOCTL_MODE_GETRESOURCES: { struct drm_mode_card_res *r=arg; *(uint32_t *)(uintptr_t)r->crtc_id_ptr=10; *(uint32_t *)(uintptr_t)r->connector_id_ptr=11; r->count_crtcs=r->count_connectors=1; break; }
    case DRM_IOCTL_MODE_GETCONNECTOR: {
        struct drm_mode_get_connector *c=arg;
        struct drm_mode_modeinfo *m=(void *)(uintptr_t)c->modes_ptr;
        if (c->count_modes) {
            assert(c->props_ptr && c->prop_values_ptr && c->encoders_ptr && m);
            memset(m,0,sizeof(*m)); m->hdisplay=640;m->vdisplay=480;m->htotal=868;m->vtotal=518;
        }
        c->count_modes=c->count_encoders=c->count_props=c->connection=1; break;
    }
    case DRM_IOCTL_MODE_GETCRTC: { struct drm_mode_crtc *c=arg; c->mode_valid=0;c->fb_id=0;break; }
    case DRM_IOCTL_MODE_CREATE_DUMB: {
        struct drm_mode_create_dumb *d=arg;
        assert(d->width==640 && d->height==480 && d->bpp==16);
        d->handle = dumb_count ? 14 : 12; dumb_count++;
        d->pitch=1280; d->size=sizeof(mock_buffers[0]); break;
    }
    case DRM_IOCTL_MODE_MAP_DUMB: { struct drm_mode_map_dumb *m=arg;
        m->offset = m->handle==12 ? UINT64_C(0x100000000) : UINT64_C(0x180000000); break; }
    case DRM_IOCTL_MODE_ADDFB: { struct drm_mode_fb_cmd *f=arg;
        assert(f->width==640 && f->height==480 && f->pitch==1280 && f->bpp==16);
        f->fb_id = fb_count ? 15 : 13; fb_count++; break; }
    case DRM_IOCTL_MODE_SETCRTC: {
        struct drm_mode_crtc *c=arg;
        if (c->mode_valid) {
            int idx;
            if (fail_modeset) { errno=EIO; return -1; }
            idx = fb_index(c->fb_id); assert(idx>=0);
            activate(idx); sets++;
        } else if (screen_idx >= 0) {
            activate(-1);
        }
        break;
    }
    case DRM_IOCTL_MODE_PAGE_FLIP: {
        struct drm_mode_crtc_page_flip *f=arg;
        int idx;
        if (fail_flip_ioctl) { errno=EIO; return -1; }
        assert(f->flags==DRM_MODE_PAGE_FLIP_EVENT && f->crtc_id==10);
        idx = fb_index(f->fb_id); assert(idx>=0);
        assert(screen_idx>=0 && "page flip before the first modeset");
        activate(idx);
        assert(event_tail - event_head < (int)(sizeof(event_queue)/sizeof(event_queue[0])));
        event_queue[event_tail++ % (int)(sizeof(event_queue)/sizeof(event_queue[0]))] = f->user_data;
        flips++; break;
    }
    case DRM_IOCTL_WAIT_VBLANK: waits++;break;
    case DRM_IOCTL_MODE_RMFB: { struct drm_mode_fb_cmd *f=arg;
        assert(fb_index(f->fb_id)>=0 && screen_idx!=fb_index(f->fb_id));
        rmfbs++; break; }
    case DRM_IOCTL_MODE_DESTROY_DUMB: destroys++; break;
    default: assert(!"unexpected ioctl");
    }
    return 0;
}
static int fake_poll(struct pollfd *fds, nfds_t nfds, int timeout) {
    (void)timeout;
    assert(nfds==1 && fds[0].fd==42);
    if (fail_flip_wait) { fds[0].revents=0; return 0; }
    if (event_tail > event_head) { fds[0].revents=POLLIN; return 1; }
    fds[0].revents=0; return 0;
}
static ssize_t fake_read(int fd, void *buf, size_t count) {
    struct drm_event_vblank *event = buf;
    assert(fd==42 && count>=sizeof(*event) && event_tail>event_head);
    memset(event, 0, sizeof(*event));
    event->base.type = DRM_EVENT_FLIP_COMPLETE;
    event->base.length = sizeof(*event);
    event->crtc_id = 10;
    event->user_data = event_queue[event_head++ % (int)(sizeof(event_queue)/sizeof(event_queue[0]))];
    return sizeof(*event);
}
#define open fake_open
#define close fake_close
#define mmap fake_mmap
#define munmap fake_munmap
#define ioctl fake_ioctl
#define poll fake_poll
#define read fake_read
#include "video_drm_backend.c"
#undef open
#undef close
#undef mmap
#undef munmap
#undef ioctl
#undef poll
#undef read
unsigned int r36_test_backend_frames(void) { return (unsigned int)submitted_frames; }
unsigned int r36_test_backend_hash(void) {
    if (front < 0 || buffers[front] == MAP_FAILED) return 0;
    return hash_buffer(buffers[front]);
}
#ifndef R36_BACKEND_TEST_LIBRARY
int main(void) {
    uint16_t frame[320*240], other[320*240];
    unsigned i;
    for (i=0;i<320*240;i++) { frame[i]=0x1234; other[i]=0x5678; }
    fail_open=1;assert(video_drivers_init()==-1);assert(device==-1);
    fail_open=0;assert(video_drivers_init()>0);assert(video_drivers_init()>0);assert(maps==2);
    assert(pixels!=render_pixels && screen_idx==-1);
    assert(video_driver_disp_frame(NULL,320,240,640)==-1 && sets==0);
    fail_modeset=1;assert(video_driver_disp_frame(frame,320,240,640)==-1 && sets==0);
    fail_modeset=0;assert(video_driver_disp_frame(frame,320,240,640)==0);
    assert(sets==1 && waits==1 && flips==0 && screen_idx==front);
    assert(pixels!=render_pixels);
    assert(((uint16_t *)buffers[front])[0]==0x1234);
    assert(((uint16_t *)buffers[back])[0]==0);
    /* Second frame renders into the inactive buffer and flips it in; the mock
     * aborts if the active buffer is written during the render. */
    assert(video_driver_disp_frame(other,320,240,640)==0);
    assert(sets==1 && flips==1 && waits==1 && screen_idx==front);
    assert(((uint16_t *)buffers[front])[0]==0x5678);
    assert(((uint16_t *)buffers[back])[0]==0x1234);
    assert(video_driver_disp_frame(frame,320,240,640)==0 && flips==2);
    /* Flip ioctl failure: the next frame resynchronises with SETCRTC. */
    fail_flip_ioctl=1;assert(video_driver_disp_frame(other,320,240,640)==-1 && sets==1);
    fail_flip_ioctl=0;assert(video_driver_disp_frame(other,320,240,640)==0);
    assert(sets==2 && flips==3 && screen_idx==front);
    /* Flip event timeout: scanout target is unknown, so the next frame must
     * modeset before rendering and must drain the stale event by token. */
    fail_flip_wait=1;assert(video_driver_disp_frame(frame,320,240,640)==-1);
    fail_flip_wait=0;assert(video_driver_disp_frame(frame,320,240,640)==0);
    assert(sets==3 && screen_idx==front && ((uint16_t *)buffers[front])[0]==0x1234);
    video_driver_deinit();
    assert(device==-1 && closes==1 && munmaps==2 && rmfbs==2 && destroys==2);
    video_driver_deinit();assert(closes==1);
    assert(video_driver_disp_frame(frame,320,240,640)==-1);
    puts("REAL_BACKEND_MOCK_DRM=PASS (not hardware acceptance)");
    return 0;
}
#endif
