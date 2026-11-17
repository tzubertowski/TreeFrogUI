"""Verify combined PICOARCH_DRIVER DRM video + ALSA audio backend without altering video_drm_backend.c."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ZIG = Path(r"C:\Users\palpa\Tools\zig-x86_64-windows-0.17.0\zig.exe")


def _write_synthetic_headers(inc_dir: Path) -> None:
    (inc_dir / "drm").mkdir(parents=True, exist_ok=True)
    (inc_dir / "sys").mkdir(parents=True, exist_ok=True)

    (inc_dir / "poll.h").write_text(
        """#ifndef R36_MOCK_POLL_H
#define R36_MOCK_POLL_H
typedef unsigned long nfds_t;
struct pollfd {
    int fd;
    short events;
    short revents;
};
#ifndef POLLIN
#define POLLIN 1
#endif
#ifndef POLLOUT
#define POLLOUT 4
#endif
int poll(struct pollfd *fds, nfds_t nfds, int timeout);
#endif
"""
    )

    (inc_dir / "sys" / "ioctl.h").write_text(
        """#ifndef R36_MOCK_SYS_IOCTL_H
#define R36_MOCK_SYS_IOCTL_H
int ioctl(int fd, unsigned long request, ...);
#endif
"""
    )

    (inc_dir / "sys" / "mman.h").write_text(
        """#ifndef R36_MOCK_SYS_MMAN_H
#define R36_MOCK_SYS_MMAN_H
#include <stddef.h>
#include <sys/types.h>
#define PROT_READ  1
#define PROT_WRITE 2
#define MAP_SHARED 1
#define MAP_FAILED ((void *)(-1))
void *mmap(void *addr, size_t len, int prot, int flags, int fd, off_t offset);
int munmap(void *addr, size_t len);
#endif
"""
    )

    (inc_dir / "drm" / "drm.h").write_text(
        """#ifndef R36_MOCK_DRM_H
#define R36_MOCK_DRM_H
#include <stdint.h>
#include <stddef.h>

struct drm_version {
    int version_major;
    int version_minor;
    int version_patchlevel;
    size_t name_len;
    char *name;
};

struct drm_event {
    uint32_t type;
    uint32_t length;
};

struct drm_event_vblank {
    struct drm_event base;
    uint64_t user_data;
    uint32_t tv_sec;
    uint32_t tv_usec;
    uint32_t sequence;
    uint32_t crtc_id;
};

#define DRM_EVENT_FLIP_COMPLETE 0x02u
#define _DRM_VBLANK_RELATIVE    0x1u

union drm_wait_vblank {
    struct {
        uint32_t type;
        uint32_t sequence;
    } request;
    struct {
        uint32_t type;
        uint32_t sequence;
    } reply;
};

#define DRM_IOCTL_VERSION     0xD001u
#define DRM_IOCTL_WAIT_VBLANK 0xD002u
#endif
"""
    )

    (inc_dir / "drm" / "drm_mode.h").write_text(
        """#ifndef R36_MOCK_DRM_MODE_H
#define R36_MOCK_DRM_MODE_H
#include <stdint.h>

struct drm_mode_modeinfo {
    uint32_t clock;
    uint16_t hdisplay, hsync_start, hsync_end, htotal, hskew;
    uint16_t vdisplay, vsync_start, vsync_end, vtotal, vscan;
    uint32_t vrefresh;
    uint32_t flags;
    uint32_t type;
    char name[32];
};

struct drm_mode_card_res {
    uint64_t fb_id_ptr;
    uint64_t crtc_id_ptr;
    uint64_t connector_id_ptr;
    uint64_t encoder_id_ptr;
    uint32_t count_fbs;
    uint32_t count_crtcs;
    uint32_t count_connectors;
    uint32_t count_encoders;
    uint32_t min_width, max_width;
    uint32_t min_height, max_height;
};

struct drm_mode_get_connector {
    uint64_t encoders_ptr;
    uint64_t modes_ptr;
    uint64_t props_ptr;
    uint64_t prop_values_ptr;
    uint32_t count_modes;
    uint32_t count_props;
    uint32_t count_encoders;
    uint32_t encoder_id;
    uint32_t connector_id;
    uint32_t connector_type;
    uint32_t connector_type_id;
    uint32_t connection;
    uint32_t mm_width, mm_height;
    uint32_t subpixel;
};

struct drm_mode_crtc {
    uint64_t set_connectors_ptr;
    uint32_t count_connectors;
    uint32_t crtc_id;
    uint32_t fb_id;
    uint32_t x, y;
    uint32_t gamma_size;
    uint32_t mode_valid;
    struct drm_mode_modeinfo mode;
};

struct drm_mode_create_dumb {
    uint32_t height;
    uint32_t width;
    uint32_t bpp;
    uint32_t flags;
    uint32_t handle;
    uint32_t pitch;
    uint64_t size;
};

struct drm_mode_map_dumb {
    uint32_t handle;
    uint32_t pad;
    uint64_t offset;
};

struct drm_mode_fb_cmd {
    uint32_t fb_id;
    uint32_t width;
    uint32_t height;
    uint32_t pitch;
    uint32_t bpp;
    uint32_t depth;
    uint32_t handle;
};

struct drm_mode_destroy_dumb {
    uint32_t handle;
};

struct drm_mode_crtc_page_flip {
    uint32_t crtc_id;
    uint32_t fb_id;
    uint32_t flags;
    uint32_t reserved;
    uint64_t user_data;
};

#define DRM_MODE_PAGE_FLIP_EVENT   0x01u
#define DRM_IOCTL_MODE_GETRESOURCES 0xD101u
#define DRM_IOCTL_MODE_GETCONNECTOR 0xD102u
#define DRM_IOCTL_MODE_GETCRTC      0xD103u
#define DRM_IOCTL_MODE_SETCRTC      0xD104u
#define DRM_IOCTL_MODE_CREATE_DUMB  0xD105u
#define DRM_IOCTL_MODE_MAP_DUMB     0xD106u
#define DRM_IOCTL_MODE_ADDFB        0xD107u
#define DRM_IOCTL_MODE_RMFB         0xD108u
#define DRM_IOCTL_MODE_DESTROY_DUMB 0xD109u
#define DRM_IOCTL_MODE_PAGE_FLIP    0xD10Au
#endif
"""
    )


def test_combined_video_drm_and_audio_alsa_backend_interleaved(tmp_path):
    inc_dir = tmp_path / "include"
    _write_synthetic_headers(inc_dir)

    combined = ROOT / "scripts/peripheral_lab/driver_r36_combined_backend.c"
    harness = tmp_path / "combined_backend_test.c"
    harness.write_text(
        f'''
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <drm/drm.h>
#include <drm/drm_mode.h>

#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif
#ifndef O_NONBLOCK
#define O_NONBLOCK 0x800
#endif
#ifndef EOVERFLOW
#define EOVERFLOW 75
#endif

/* ALSA mock definitions for R36_AUDIO_BACKEND_MOCK */
#define R36_AUDIO_BACKEND_MOCK 1
typedef unsigned long snd_pcm_uframes_t;
typedef long snd_pcm_sframes_t;

#define SNDRV_PCM_HW_PARAM_ACCESS      0
#define SNDRV_PCM_HW_PARAM_FORMAT      1
#define SNDRV_PCM_HW_PARAM_SUBFORMAT   2
#define SNDRV_PCM_HW_PARAM_FIRST_MASK  0
#define SNDRV_PCM_HW_PARAM_LAST_MASK   2

#define SNDRV_PCM_HW_PARAM_CHANNELS       8
#define SNDRV_PCM_HW_PARAM_RATE           9
#define SNDRV_PCM_HW_PARAM_PERIOD_SIZE   10
#define SNDRV_PCM_HW_PARAM_BUFFER_SIZE   11
#define SNDRV_PCM_HW_PARAM_FIRST_INTERVAL 8
#define SNDRV_PCM_HW_PARAM_LAST_INTERVAL  11

#define SNDRV_PCM_ACCESS_RW_INTERLEAVED 3
#define SNDRV_PCM_FORMAT_S16_LE         2
#define SNDRV_PCM_SUBFORMAT_STD         0

#define SNDRV_PCM_IOCTL_INFO          0x81204101u
#define SNDRV_PCM_IOCTL_HW_PARAMS     0xc2604111u
#define SNDRV_PCM_IOCTL_SW_PARAMS     0xc0684113u
#define SNDRV_PCM_IOCTL_PREPARE       0x00004140u
#define SNDRV_PCM_IOCTL_DROP          0x00004143u
#define SNDRV_PCM_IOCTL_WRITEI_FRAMES 0x400c4150u

struct snd_mask {{ uint32_t bits[8]; }};
struct snd_interval {{ unsigned int min, max, openmin:1, openmax:1, integer:1, empty:1; }};
struct snd_pcm_info {{ unsigned char id[64]; }};
struct snd_pcm_hw_params {{
    unsigned int rmask;
    struct snd_mask masks[3];
    struct snd_interval intervals[4];
}};
struct snd_pcm_sw_params {{
    int tstamp_mode;
    unsigned int period_step;
    unsigned int sleep_min;
    snd_pcm_uframes_t avail_min;
    snd_pcm_uframes_t xfer_align;
    snd_pcm_uframes_t start_threshold;
    snd_pcm_uframes_t stop_threshold;
    snd_pcm_uframes_t silence_threshold;
    snd_pcm_uframes_t silence_size;
    snd_pcm_uframes_t boundary;
}};
struct snd_xferi {{
    snd_pcm_sframes_t result;
    void *buf;
    snd_pcm_uframes_t frames;
}};

/* Unified DRM (fd 42) + ALSA (fd 9) state */
static int drm_opens, drm_closes, alsa_opens, alsa_closes;
static int maps, munmaps, sets, waits, flips, rmfbs, destroys;
static int dumb_count, fb_count, screen_idx = -1;
static uint32_t screen_hash;
static uint64_t event_queue[16];
static int event_head, event_tail;
static unsigned char mock_buffers[2][1280 * 480];

static int alsa_prepares, alsa_drops;
static int16_t captured_pcm[4096 * 2];
static unsigned int captured_pcm_frames;

static uint32_t hash_buffer(const unsigned char *bytes) {{
    uint32_t h = 2166136261u;
    for (size_t i = 0; i < sizeof(mock_buffers[0]); i++) h = (h ^ bytes[i]) * 16777619u;
    return h;
}}

static int fb_index(uint32_t fb_id) {{
    if (fb_id == 13u) return 0;
    if (fb_id == 15u) return 1;
    return -1;
}}

static void activate(int idx) {{
    if (screen_idx >= 0)
        assert(hash_buffer(mock_buffers[screen_idx]) == screen_hash &&
               "CPU overwrote active scanout buffer");
    if (idx < 0) {{ screen_idx = -1; return; }}
    screen_idx = idx;
    screen_hash = hash_buffer(mock_buffers[idx]);
}}

static int mock_open(const char *path, int flags) {{
    (void)flags;
    if (!strcmp(path, "/dev/dri/card0")) {{ drm_opens++; return 42; }}
    if (!strcmp(path, "/dev/snd/pcmC0D0p")) {{ alsa_opens++; return 9; }}
    assert(!"unexpected device path");
    return -1;
}}

static int mock_close(int fd) {{
    if (fd == 42) {{ drm_closes++; return 0; }}
    if (fd == 9) {{ alsa_closes++; return 0; }}
    assert(!"unexpected close fd");
    return -1;
}}

static void *mock_mmap(void *p, size_t n, int prot, int flags, int fd, off_t offset) {{
    (void)p; (void)prot; (void)flags;
    assert(fd == 42 && n == sizeof(mock_buffers[0]));
    if (offset == (off_t)0x10000000L) {{ maps++; return mock_buffers[0]; }}
    if (offset == (off_t)0x18000000L) {{ maps++; return mock_buffers[1]; }}
    assert(!"unexpected mmap offset");
    return MAP_FAILED;
}}

static int mock_munmap(void *p, size_t n) {{
    assert(n == sizeof(mock_buffers[0]));
    assert(p == mock_buffers[0] || p == mock_buffers[1]);
    munmaps++;
    return 0;
}}

static int drm_ioctl(unsigned long req, void *arg) {{
    switch (req) {{
    case DRM_IOCTL_VERSION: {{
        struct drm_version *v = arg;
        strcpy(v->name, "r36-hc16xx");
        break;
    }}
    case DRM_IOCTL_MODE_GETRESOURCES: {{
        struct drm_mode_card_res *r = arg;
        *(uint32_t *)(uintptr_t)r->crtc_id_ptr = 10u;
        *(uint32_t *)(uintptr_t)r->connector_id_ptr = 11u;
        r->count_crtcs = r->count_connectors = 1u;
        break;
    }}
    case DRM_IOCTL_MODE_GETCONNECTOR: {{
        struct drm_mode_get_connector *c = arg;
        if (c->count_modes) {{
            struct drm_mode_modeinfo *m = (void *)(uintptr_t)c->modes_ptr;
            assert(c->props_ptr && c->prop_values_ptr && c->encoders_ptr && m);
            memset(m, 0, sizeof(*m));
            m->hdisplay = 640u; m->vdisplay = 480u;
            m->htotal = 868u; m->vtotal = 518u;
        }}
        c->count_modes = c->count_encoders = c->count_props = c->connection = 1u;
        break;
    }}
    case DRM_IOCTL_MODE_GETCRTC: {{
        struct drm_mode_crtc *c = arg;
        c->mode_valid = 0u;
        c->fb_id = 0u;
        break;
    }}
    case DRM_IOCTL_MODE_CREATE_DUMB: {{
        struct drm_mode_create_dumb *d = arg;
        assert(d->width == 640u && d->height == 480u && d->bpp == 16u);
        d->handle = dumb_count ? 14u : 12u;
        dumb_count++;
        d->pitch = 1280u;
        d->size = sizeof(mock_buffers[0]);
        break;
    }}
    case DRM_IOCTL_MODE_MAP_DUMB: {{
        struct drm_mode_map_dumb *m = arg;
        m->offset = (m->handle == 12u) ? UINT64_C(0x10000000) : UINT64_C(0x18000000);
        break;
    }}
    case DRM_IOCTL_MODE_ADDFB: {{
        struct drm_mode_fb_cmd *f = arg;
        assert(f->width == 640u && f->height == 480u && f->pitch == 1280u && f->bpp == 16u);
        f->fb_id = fb_count ? 15u : 13u;
        fb_count++;
        break;
    }}
    case DRM_IOCTL_MODE_SETCRTC: {{
        struct drm_mode_crtc *c = arg;
        if (c->mode_valid) {{
            int idx = fb_index(c->fb_id);
            assert(idx >= 0);
            activate(idx);
            sets++;
        }} else if (screen_idx >= 0) {{
            activate(-1);
        }}
        break;
    }}
    case DRM_IOCTL_MODE_PAGE_FLIP: {{
        struct drm_mode_crtc_page_flip *f = arg;
        int idx = fb_index(f->fb_id);
        assert(f->flags == DRM_MODE_PAGE_FLIP_EVENT && f->crtc_id == 10u && idx >= 0);
        assert(screen_idx >= 0);
        activate(idx);
        event_queue[event_tail++ % 16] = f->user_data;
        flips++;
        break;
    }}
    case DRM_IOCTL_WAIT_VBLANK:
        waits++;
        break;
    case DRM_IOCTL_MODE_RMFB: {{
        struct drm_mode_fb_cmd *f = arg;
        assert(fb_index(f->fb_id) >= 0 && screen_idx != fb_index(f->fb_id));
        rmfbs++;
        break;
    }}
    case DRM_IOCTL_MODE_DESTROY_DUMB:
        destroys++;
        break;
    default:
        assert(!"unexpected drm ioctl");
    }}
    return 0;
}}

static int alsa_ioctl(unsigned long req, void *arg) {{
    if (req == SNDRV_PCM_IOCTL_INFO) {{
        struct snd_pcm_info *info = arg;
        strcpy((char *)info->id, "I2S");
        return 0;
    }}
    if (req == SNDRV_PCM_IOCTL_HW_PARAMS) {{
        struct snd_pcm_hw_params *hw = arg;
        assert(hw->intervals[0].min == 2u && hw->intervals[1].min == 48000u);
        return 0;
    }}
    if (req == SNDRV_PCM_IOCTL_SW_PARAMS) {{
        struct snd_pcm_sw_params *sw = arg;
        assert(sw->avail_min == 512u && sw->start_threshold == 1024u);
        return 0;
    }}
    if (req == SNDRV_PCM_IOCTL_PREPARE) {{ alsa_prepares++; return 0; }}
    if (req == SNDRV_PCM_IOCTL_DROP) {{ alsa_drops++; return 0; }}
    if (req == SNDRV_PCM_IOCTL_WRITEI_FRAMES) {{
        struct snd_xferi *x = arg;
        memcpy(captured_pcm + (size_t)captured_pcm_frames * 2u, x->buf, (size_t)x->frames * 4u);
        captured_pcm_frames += (unsigned int)x->frames;
        x->result = (snd_pcm_sframes_t)x->frames;
        return 0;
    }}
    assert(!"unexpected alsa ioctl");
    return -1;
}}

static int mock_ioctl(int fd, unsigned long req, ...) {{
    void *arg = NULL;
    if (req != SNDRV_PCM_IOCTL_PREPARE && req != SNDRV_PCM_IOCTL_DROP) {{
        va_list ap;
        va_start(ap, req);
        arg = va_arg(ap, void *);
        va_end(ap);
    }}
    if (fd == 42) return drm_ioctl(req, arg);
    if (fd == 9) return alsa_ioctl(req, arg);
    assert(!"unexpected ioctl fd");
    return -1;
}}

static int mock_poll(struct pollfd *fds, nfds_t nfds, int timeout) {{
    (void)timeout;
    assert(nfds == 1);
    if (fds[0].fd == 42) {{
        if (event_tail > event_head) {{ fds[0].revents = POLLIN; return 1; }}
        fds[0].revents = 0; return 0;
    }}
    if (fds[0].fd == 9) {{
        fds[0].revents = POLLOUT; return 1;
    }}
    assert(!"unexpected poll fd");
    return -1;
}}

static ssize_t mock_read(int fd, void *buf, size_t count) {{
    struct drm_event_vblank *ev = buf;
    assert(fd == 42 && count >= sizeof(*ev) && event_tail > event_head);
    memset(ev, 0, sizeof(*ev));
    ev->base.type = DRM_EVENT_FLIP_COMPLETE;
    ev->base.length = sizeof(*ev);
    ev->crtc_id = 10u;
    ev->user_data = event_queue[event_head++ % 16];
    return (ssize_t)sizeof(*ev);
}}

static int mock_usleep(unsigned int usec) {{ (void)usec; return 0; }}

#define open   mock_open
#define close  mock_close
#define mmap   mock_mmap
#define munmap mock_munmap
#define ioctl  mock_ioctl
#define poll   mock_poll
#define read   mock_read
#define usleep mock_usleep

#include "{combined.as_posix()}"

int main(void) {{
    uint16_t frame_a[320 * 240], frame_b[320 * 240], frame_c[320 * 240];
    int16_t pcm[480 * 2];
    for (unsigned i = 0; i < 320u * 240u; i++) {{
        frame_a[i] = 0x1111u;
        frame_b[i] = 0x2222u;
        frame_c[i] = 0x3333u;
    }}
    for (unsigned i = 0; i < 480u * 2u; i++) pcm[i] = (int16_t)(i - 300);

    /* Video + picoarch audio warmup init->deinit->init */
    assert(video_drivers_init() > 0);
    assert(sound_driver_init(NULL, 48000, 2) == 0);
    assert(sound_driver_deinit() == 0);
    assert(sound_driver_init(NULL, 48000, 2) == 0);
    assert(drm_opens == 1 && alsa_opens == 2 && alsa_closes == 1);

    /* Interleaved 3-frame render + audio loop */
    uint16_t *frames[3] = {{ frame_a, frame_b, frame_c }};
    for (int f = 0; f < 3; f++) {{
        assert(video_driver_disp_frame(frames[f], 320, 240, 640) == 0);
        assert(sound_driver_playframe(pcm, 480) == 0);
    }}
    assert(sets == 1 && waits == 1 && flips == 2);
    assert(submitted_frames == 3);
    assert(captured_pcm_frames == 480u * 3u);
    assert(!memcmp(captured_pcm, pcm, sizeof(pcm)));
    assert(!memcmp(captured_pcm + 480u * 2u, pcm, sizeof(pcm)));

    assert(sound_driver_flush() == 0);
    assert(sound_driver_deinit() == 0);
    video_driver_deinit();
    assert(drm_closes == 1 && alsa_closes == 2 && alsa_drops >= 2);
    assert(munmaps == 2 && rmfbs == 2 && destroys == 2);
    puts("COMBINED_BACKEND_MOCK=PASS");
    return 0;
}}
'''
    )

    exe = tmp_path / "combined_backend_test.exe"
    subprocess.run(
        [
            "gcc",
            "-std=gnu11",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{inc_dir}",
            f"-I{(ROOT / 'scripts/peripheral_lab')}",
            str(harness),
            "-lpthread",
            "-o",
            str(exe),
        ],
        check=True,
        capture_output=True,
        timeout=20,
    )
    res = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=5)
    assert "COMBINED_BACKEND_MOCK=PASS" in res.stdout

    if ZIG.exists():
        mips_obj = tmp_path / "driver_r36_combined_backend.o"
        subprocess.run(
            [
                str(ZIG),
                "cc",
                "-target",
                "mipsel-linux.4.4-musleabi",
                "-march=mips32r2",
                "-msoft-float",
                "-Os",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-c",
                str(combined),
                "-o",
                str(mips_obj),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        assert mips_obj.stat().st_size > 0
