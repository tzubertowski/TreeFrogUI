"""Verify picoarch ALSA audio backend lifecycle, warmup re-init, XRUN recovery, and resampling."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ZIG = Path(r"C:\Users\palpa\Tools\zig-x86_64-windows-0.17.0\zig.exe")


def test_audio_alsa_backend_picoarch_warmup_playframe_xrun_and_resampling(tmp_path):
    backend = ROOT / "scripts/peripheral_lab/audio_alsa_backend.c"
    harness = tmp_path / "audio_backend_test.c"
    harness.write_text(f'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define R36_AUDIO_BACKEND_MOCK 1
#define O_RDWR     2
#define O_NONBLOCK 4
#define O_CLOEXEC  8
#define POLLOUT    4

struct pollfd {{ int fd; short events; short revents; }};
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

static int mock_open_count, mock_close_count, mock_prepare_count, mock_drop_count;
static int inject_eagain_once, inject_epipe_once, inject_partial_write, bad_card_id;
static int16_t captured_samples[16384 * 2];
static unsigned int captured_frames;

static int mock_open(const char *path, int flags) {{
    assert(!strcmp(path, "/dev/snd/pcmC0D0p"));
    assert((flags & O_RDWR) && (flags & O_NONBLOCK));
    mock_open_count++;
    return 9;
}}
static int mock_close(int fd) {{
    assert(fd == 9);
    mock_close_count++;
    return 0;
}}
static int mock_poll(struct pollfd *pfd, unsigned long nfds, int timeout) {{
    assert(nfds == 1 && pfd->fd == 9 && (pfd->events & POLLOUT) && timeout == 20);
    pfd->revents = POLLOUT;
    return 1;
}}
static int mock_usleep(unsigned int us) {{ (void)us; return 0; }}
static int mock_ioctl(int fd, unsigned long req, void *arg) {{
    assert(fd == 9);
    if (req == SNDRV_PCM_IOCTL_INFO) {{
        struct snd_pcm_info *info = (struct snd_pcm_info *)arg;
        strcpy((char *)info->id, bad_card_id ? "WRONG" : "I2S");
        return 0;
    }}
    if (req == SNDRV_PCM_IOCTL_HW_PARAMS) {{
        struct snd_pcm_hw_params *hw = (struct snd_pcm_hw_params *)arg;
        assert(hw->intervals[0].min == 2 && hw->intervals[0].max == 2);
        assert(hw->intervals[1].min == 48000 && hw->intervals[1].max == 48000);
        assert(hw->intervals[2].min == 512 && hw->intervals[3].min == 4096);
        return 0;
    }}
    if (req == SNDRV_PCM_IOCTL_SW_PARAMS) {{
        struct snd_pcm_sw_params *sw = (struct snd_pcm_sw_params *)arg;
        assert(sw->avail_min == 512 && sw->start_threshold == 1024 && sw->stop_threshold == 4096);
        return 0;
    }}
    if (req == SNDRV_PCM_IOCTL_PREPARE) {{ mock_prepare_count++; return 0; }}
    if (req == SNDRV_PCM_IOCTL_DROP) {{ mock_drop_count++; return 0; }}
    if (req == SNDRV_PCM_IOCTL_WRITEI_FRAMES) {{
        struct snd_xferi *x = (struct snd_xferi *)arg;
        if (inject_eagain_once) {{ inject_eagain_once = 0; errno = EAGAIN; return -1; }}
        if (inject_epipe_once) {{ inject_epipe_once = 0; errno = EPIPE; return -1; }}
        unsigned int take = (unsigned int)x->frames;
        if (inject_partial_write && take > 200) {{ take = 200; inject_partial_write = 0; }}
        memcpy(captured_samples + (size_t)captured_frames * 2u, x->buf, (size_t)take * 4u);
        captured_frames += take;
        x->result = (snd_pcm_sframes_t)take;
        return 0;
    }}
    return -1;
}}

#define open   mock_open
#define close  mock_close
#define ioctl  mock_ioctl
#define poll   mock_poll
#define usleep mock_usleep

#include "{backend.as_posix()}"

int main(void) {{
    int16_t chunk480[480 * 2];
    for (int i = 0; i < 480 * 2; i++) chunk480[i] = (int16_t)(i - 400);

    /* Reject invalid parameters or wrong ALSA card ID */
    assert(sound_driver_init(NULL, 0, 2) == -1);
    assert(sound_driver_init(NULL, 48000, 3) == -1);
    bad_card_id = 1;
    assert(sound_driver_init(NULL, 48000, 2) == -1);
    bad_card_id = 0;

    /* Simulate picoarch's exact startup warm-up sequence (0x42ce80..0x42cfb8):
     * init(NULL, 48000, 2) -> deinit() -> init(NULL, 48000, 2) -> playframe(480) */
    mock_open_count = mock_close_count = mock_prepare_count = mock_drop_count = 0;
    captured_frames = 0;
    assert(sound_driver_init(NULL, 48000, 2) == 0);
    assert(sound_driver_deinit() == 0);
    assert(sound_driver_init(NULL, 48000, 2) == 0);
    assert(mock_open_count == 2 && mock_close_count == 1 && mock_prepare_count == 2);

    /* Fast path 48000 Hz stereo + partial write + EAGAIN + EPIPE recovery */
    inject_partial_write = 1;
    inject_eagain_once = 1;
    inject_epipe_once = 1;
    assert(sound_driver_playframe(chunk480, 480) == 0);
    assert(captured_frames == 480);
    assert(!memcmp(captured_samples, chunk480, sizeof(chunk480)));
    assert(mock_prepare_count == 3);

    /* Flush and mono 24000 Hz -> 48000 Hz stereo expansion */
    assert(sound_driver_flush() == 0);
    assert(sound_driver_init(NULL, 24000, 1) == 0);
    captured_frames = 0;
    int16_t mono240[240];
    for (int i = 0; i < 240; i++) mono240[i] = (int16_t)(i * 10);
    assert(sound_driver_playframe(mono240, 240) == 0);
    assert(captured_frames == 480);
    assert(captured_samples[0] == 0 && captured_samples[1] == 0);
    assert(captured_samples[479 * 2] == 2390 && captured_samples[479 * 2 + 1] == 2390);
    assert(sound_driver_deinit() == 0);
    return 0;
}}
''')
    exe = tmp_path / "audio_backend_test.exe"
    subprocess.run(["gcc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", str(harness), "-o", str(exe)],
                   check=True, capture_output=True, timeout=20)
    subprocess.run([str(exe)], check=True, timeout=5)

    if ZIG.exists():
        mips_obj = tmp_path / "audio_alsa_backend.o"
        subprocess.run([
            str(ZIG), "cc", "-target", "mipsel-linux.4.4-musleabi",
            "-march=mips32r2", "-msoft-float", "-Os", "-Wall", "-Wextra", "-Werror",
            "-c", str(backend), "-o", str(mips_obj),
        ], check=True, capture_output=True, timeout=30)
        assert mips_obj.stat().st_size > 0
