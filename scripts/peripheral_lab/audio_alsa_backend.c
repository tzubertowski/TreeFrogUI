/* SPDX-License-Identifier: MIT */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <errno.h>
#include <stdint.h>
#include <string.h>

#ifndef R36_AUDIO_BACKEND_MOCK
#include <fcntl.h>
#include <poll.h>
#include <sound/asound.h>
#include <sys/ioctl.h>
#include <unistd.h>
#endif

#ifndef ESTRPIPE
#define ESTRPIPE 86
#endif

/* Linux 7.2 ALSA PCM backend for unchanged picoarch / TreeFrogUI audio loader
 * (picoarch 0x42c2a0..0x42cf88: PICOARCH_DRIVER -> sound_driver_init,
 * sound_driver_playframe, sound_driver_deinit, optional sound_driver_flush).
 *
 * Matches the verified 12-word r36_hc16xx_i2s UAPI (48000 Hz, stereo S16_LE,
 * period 512, buffer 4096) and supports picoarch's mandatory startup sequence:
 *   sound_driver_init(NULL, 48000, 2) -> sound_driver_deinit() ->
 *   usleep(100000) -> sound_driver_init(NULL, 48000, 2) -> playframe(480).
 */

#define R36_AUDIO_HW_RATE        48000u
#define R36_AUDIO_HW_CHANNELS    2u
#define R36_AUDIO_PERIOD_FRAMES  512u
#define R36_AUDIO_BUFFER_FRAMES  4096u
#define R36_AUDIO_MAX_IN_FRAMES  4096
#define R36_AUDIO_CHUNK_FRAMES   512u

static int      pcm_fd = -1;
static uint32_t in_rate = R36_AUDIO_HW_RATE;
static uint32_t in_channels = R36_AUDIO_HW_CHANNELS;

static void pcm_set_mask(struct snd_pcm_hw_params *p, unsigned int idx, unsigned int val)
{
    struct snd_mask *m = &p->masks[idx - SNDRV_PCM_HW_PARAM_FIRST_MASK];
    memset(m, 0, sizeof(*m));
    m->bits[val / 32u] = 1u << (val % 32u);
}

static void pcm_set_interval(struct snd_pcm_hw_params *p, unsigned int idx, unsigned int val)
{
    struct snd_interval *v = &p->intervals[idx - SNDRV_PCM_HW_PARAM_FIRST_INTERVAL];
    memset(v, 0, sizeof(*v));
    v->min = val;
    v->max = val;
    v->integer = 1;
}

static int configure_hw_and_sw(int fd)
{
    struct snd_pcm_info info;
    struct snd_pcm_hw_params hw;
    struct snd_pcm_sw_params sw;
    unsigned int i;

    memset(&info, 0, sizeof(info));
    if (ioctl(fd, SNDRV_PCM_IOCTL_INFO, &info) != 0 || strcmp((const char *)info.id, "I2S") != 0)
        return -1;

    memset(&hw, 0, sizeof(hw));
    for (i = 0; i <= SNDRV_PCM_HW_PARAM_LAST_MASK - SNDRV_PCM_HW_PARAM_FIRST_MASK; i++)
        memset(&hw.masks[i], 0xff, sizeof(hw.masks[i]));
    for (i = 0; i <= SNDRV_PCM_HW_PARAM_LAST_INTERVAL - SNDRV_PCM_HW_PARAM_FIRST_INTERVAL; i++)
        hw.intervals[i].max = ~0u;
    hw.rmask = ~0u;

    pcm_set_mask(&hw, SNDRV_PCM_HW_PARAM_ACCESS, SNDRV_PCM_ACCESS_RW_INTERLEAVED);
    pcm_set_mask(&hw, SNDRV_PCM_HW_PARAM_FORMAT, SNDRV_PCM_FORMAT_S16_LE);
    pcm_set_mask(&hw, SNDRV_PCM_HW_PARAM_SUBFORMAT, SNDRV_PCM_SUBFORMAT_STD);
    pcm_set_interval(&hw, SNDRV_PCM_HW_PARAM_CHANNELS, R36_AUDIO_HW_CHANNELS);
    pcm_set_interval(&hw, SNDRV_PCM_HW_PARAM_RATE, R36_AUDIO_HW_RATE);
    pcm_set_interval(&hw, SNDRV_PCM_HW_PARAM_PERIOD_SIZE, R36_AUDIO_PERIOD_FRAMES);
    pcm_set_interval(&hw, SNDRV_PCM_HW_PARAM_BUFFER_SIZE, R36_AUDIO_BUFFER_FRAMES);
    if (ioctl(fd, SNDRV_PCM_IOCTL_HW_PARAMS, &hw) != 0)
        return -1;

    memset(&sw, 0, sizeof(sw));
    sw.period_step = 1;
    sw.avail_min = R36_AUDIO_PERIOD_FRAMES;
    sw.xfer_align = 1;
    sw.start_threshold = R36_AUDIO_PERIOD_FRAMES * 2u;
    sw.stop_threshold = R36_AUDIO_BUFFER_FRAMES;
    sw.boundary = R36_AUDIO_BUFFER_FRAMES;
    while (sw.boundary * 2UL <= 0x7fffffffUL - R36_AUDIO_BUFFER_FRAMES)
        sw.boundary *= 2UL;

    if (ioctl(fd, SNDRV_PCM_IOCTL_SW_PARAMS, &sw) != 0)
        return -1;
    if (ioctl(fd, SNDRV_PCM_IOCTL_PREPARE, 0) != 0)
        return -1;
    return 0;
}

static int write_hw_frames(const int16_t *stereo_frames, unsigned int total_frames)
{
    unsigned int offset = 0;
    unsigned int retries = 0;

    while (offset < total_frames) {
        unsigned int chunk = total_frames - offset;
        if (chunk > R36_AUDIO_CHUNK_FRAMES)
            chunk = R36_AUDIO_CHUNK_FRAMES;
        struct snd_xferi xfer = {
            .result = 0,
            .buf = (void *)(stereo_frames + (size_t)offset * 2u),
            .frames = chunk,
        };
        if (ioctl(pcm_fd, SNDRV_PCM_IOCTL_WRITEI_FRAMES, &xfer) != 0) {
            if (errno == EINTR)
                continue;
            if (errno == EPIPE || errno == ESTRPIPE) {
                if (ioctl(pcm_fd, SNDRV_PCM_IOCTL_PREPARE, 0) != 0)
                    return -1;
                if (++retries > 16u)
                    return -1;
                continue;
            }
            if (errno == EAGAIN) {
                struct pollfd pfd = { .fd = pcm_fd, .events = POLLOUT, .revents = 0 };
                if (++retries > 32u || poll(&pfd, 1, 20) < 0)
                    return -1;
                usleep(1000);
                continue;
            }
            return -1;
        }
        if (xfer.result <= 0 || (unsigned long)xfer.result > chunk)
            return -1;
        offset += (unsigned int)xfer.result;
        retries = 0;
    }
    return 0;
}

int sound_driver_deinit(void)
{
    if (pcm_fd >= 0) {
        ioctl(pcm_fd, SNDRV_PCM_IOCTL_DROP, 0);
        close(pcm_fd);
        pcm_fd = -1;
    }
    return 0;
}

int sound_driver_flush(void)
{
    if (pcm_fd < 0)
        return 0;
    if (ioctl(pcm_fd, SNDRV_PCM_IOCTL_DROP, 0) != 0)
        return -1;
    if (ioctl(pcm_fd, SNDRV_PCM_IOCTL_PREPARE, 0) != 0)
        return -1;
    return 0;
}

int sound_driver_init(void *device_name, int sample_rate, int channels)
{
    const char *path = "/dev/snd/pcmC0D0p";
    int fd;
    (void)device_name;

    if (sample_rate < 8000 || sample_rate > 192000 || (channels != 1 && channels != 2))
        return -1;

    if (pcm_fd >= 0)
        sound_driver_deinit();

    fd = open(path, O_RDWR | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0)
        return -1;
    if (configure_hw_and_sw(fd) != 0) {
        close(fd);
        return -1;
    }
    pcm_fd = fd;
    in_rate = (uint32_t)sample_rate;
    in_channels = (uint32_t)channels;
    return 0;
}

int sound_driver_playframe(const void *buf, int frames)
{
    const int16_t *src = (const int16_t *)buf;
    int16_t converted[R36_AUDIO_CHUNK_FRAMES * 2u];

    if (pcm_fd < 0 || !buf || frames <= 0 || frames > R36_AUDIO_MAX_IN_FRAMES)
        return -1;

    /* Fast path: picoarch already resamples to 48000 Hz stereo (480 frames/call) */
    if (in_rate == R36_AUDIO_HW_RATE && in_channels == 2u)
        return write_hw_frames(src, (unsigned int)frames);

    /* Nearest/linear rate and mono-to-stereo conversion into 48000 Hz stereo chunks */
    uint64_t out_total64 = ((uint64_t)(unsigned int)frames * R36_AUDIO_HW_RATE + in_rate / 2u) / in_rate;
    unsigned int out_total = out_total64 > 0 ? (unsigned int)out_total64 : 1u;
    unsigned int out_pos = 0;

    while (out_pos < out_total) {
        unsigned int n = out_total - out_pos;
        if (n > R36_AUDIO_CHUNK_FRAMES)
            n = R36_AUDIO_CHUNK_FRAMES;
        for (unsigned int i = 0; i < n; i++) {
            unsigned int src_idx = (unsigned int)(((uint64_t)(out_pos + i) * (unsigned int)frames) / out_total);
            if (src_idx >= (unsigned int)frames)
                src_idx = (unsigned int)frames - 1u;
            if (in_channels == 2u) {
                converted[i * 2u + 0u] = src[src_idx * 2u + 0u];
                converted[i * 2u + 1u] = src[src_idx * 2u + 1u];
            } else {
                int16_t s = src[src_idx];
                converted[i * 2u + 0u] = s;
                converted[i * 2u + 1u] = s;
            }
        }
        if (write_hw_frames(converted, n) != 0)
            return -1;
        out_pos += n;
    }
    return 0;
}
