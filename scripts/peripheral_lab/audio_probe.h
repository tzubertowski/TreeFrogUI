/* SPDX-License-Identifier: GPL-2.0 */
#ifndef R36_AUDIO_PROBE_H
#define R36_AUDIO_PROBE_H
#include <sound/asound.h>
#include <poll.h>

const uint32_t r36_audio_abi[] __attribute__((used, section(".r36audio"))) = {
    0x52334142, 1, sizeof(struct snd_pcm_hw_params), sizeof(struct snd_pcm_sw_params),
    sizeof(struct snd_xferi), sizeof(struct snd_pcm_info),
    SNDRV_PCM_IOCTL_HW_PARAMS, SNDRV_PCM_IOCTL_SW_PARAMS,
    SNDRV_PCM_IOCTL_WRITEI_FRAMES, SNDRV_PCM_IOCTL_INFO,
    SNDRV_PCM_IOCTL_PREPARE, SNDRV_PCM_IOCTL_DROP
};

static void pcm_mask(struct snd_pcm_hw_params *p, unsigned int index, unsigned int value)
{
    struct snd_mask *mask = &p->masks[index - SNDRV_PCM_HW_PARAM_FIRST_MASK];
    memset(mask, 0, sizeof(*mask));
    mask->bits[value / 32] = 1u << (value % 32);
}
static void pcm_interval(struct snd_pcm_hw_params *p, unsigned int index, unsigned int value)
{
    struct snd_interval *v = &p->intervals[index - SNDRV_PCM_HW_PARAM_FIRST_INTERVAL];
    memset(v, 0, sizeof(*v)); v->min = v->max = value; v->integer = 1;
}
static unsigned long audio_irqs(void)
{
    FILE *file = fopen("/proc/interrupts", "r");
    char line[512]; unsigned long count = 0;
    if (!file) return 0;
    while (fgets(line, sizeof(line), file)) {
        char *colon = strchr(line, ':');
        if (colon && strstr(line, "1880a000.sound")) count = strtoul(colon + 1, NULL, 10);
    }
    fclose(file); return count;
}
static int audio_state(unsigned int *control, unsigned int *rd, unsigned int *gain, unsigned int *mute)
{
    char text[256] = {0}; unsigned int dma, config, wr;
    int fd = open("/sys/bus/platform/devices/1880a000.sound/health", O_RDONLY | O_CLOEXEC);
    ssize_t n;
    if (fd < 0) return -1;
    n = read(fd, text, sizeof(text) - 1); close(fd);
    if (n <= 0) return -1;
    printf("audio_health=%s", text);
    return sscanf(text, "control=%x dma=%x config=%x rd=%u wr=%u gain=%u mute=%u",
                  control, &dma, &config, rd, &wr, gain, mute) == 7 ? 0 : -1;
}
static int audio_silent_probe(void)
{
    struct snd_pcm_hw_params hw;
    struct snd_pcm_sw_params sw = {0};
    struct snd_pcm_info info = {0};
    static short silence[512 * 2];
    unsigned int i, control, first = 0, rd, gain, mute, moved = 0;
    unsigned long before, after;
    int module, pcm = -1, rc, result = -1, reason = 0, drop_rc = -1;
    long frames = 0;
    struct timespec started, current;
    puts("R36 AUDIO SILENT PROBE V1");
    module = open("/sd/cubegm/r36_hc16xx_i2s.ko", O_RDONLY | O_CLOEXEC);
    if (module < 0) goto finish;
    rc = syscall(SYS_finit_module, module, "allow_takeover=1", 0); reason = rc ? errno : 0; close(module);
    printf("audio_module_load_rc=%d errno=%d\n", rc, reason);
    if (rc) goto finish;
    pcm = open("/dev/snd/pcmC0D0p", O_RDWR | O_NONBLOCK | O_CLOEXEC);
    if (pcm < 0) goto finish;
    if (ioctl(pcm, SNDRV_PCM_IOCTL_INFO, &info) || strcmp((char *)info.id, "I2S")) goto finish;
    memset(&hw, 0, sizeof(hw));
    for (i = 0; i <= SNDRV_PCM_HW_PARAM_LAST_MASK - SNDRV_PCM_HW_PARAM_FIRST_MASK; i++)
        memset(&hw.masks[i], 0xff, sizeof(hw.masks[i]));
    for (i = 0; i <= SNDRV_PCM_HW_PARAM_LAST_INTERVAL - SNDRV_PCM_HW_PARAM_FIRST_INTERVAL; i++)
        hw.intervals[i].max = ~0u;
    hw.rmask = ~0u;
    pcm_mask(&hw, SNDRV_PCM_HW_PARAM_ACCESS, SNDRV_PCM_ACCESS_RW_INTERLEAVED);
    pcm_mask(&hw, SNDRV_PCM_HW_PARAM_FORMAT, SNDRV_PCM_FORMAT_S16_LE);
    pcm_mask(&hw, SNDRV_PCM_HW_PARAM_SUBFORMAT, SNDRV_PCM_SUBFORMAT_STD);
    pcm_interval(&hw, SNDRV_PCM_HW_PARAM_CHANNELS, 2);
    pcm_interval(&hw, SNDRV_PCM_HW_PARAM_RATE, 48000);
    pcm_interval(&hw, SNDRV_PCM_HW_PARAM_PERIOD_SIZE, 512);
    pcm_interval(&hw, SNDRV_PCM_HW_PARAM_BUFFER_SIZE, 4096);
    if (ioctl(pcm, SNDRV_PCM_IOCTL_HW_PARAMS, &hw)) goto finish;
    sw.period_step = 1; sw.avail_min = 512; sw.xfer_align = 1;
    sw.start_threshold = 1024; sw.stop_threshold = 4096;
    sw.boundary = 4096;
    while (sw.boundary * 2 <= 0x7fffffffUL - 4096) sw.boundary *= 2;
    if (ioctl(pcm, SNDRV_PCM_IOCTL_SW_PARAMS, &sw) || ioctl(pcm, SNDRV_PCM_IOCTL_PREPARE)) goto finish;
    if (audio_state(&control, &first, &gain, &mute) || gain || !mute) goto finish;
    before = audio_irqs();
    if (clock_gettime(CLOCK_MONOTONIC, &started)) goto finish;
    for (i = 0; frames < 24576; i++) {
        snd_pcm_uframes_t remaining = (snd_pcm_uframes_t)(24576 - frames);
        struct snd_xferi transfer = {.buf = silence, .frames = remaining < 512 ? remaining : 512};
        if (clock_gettime(CLOCK_MONOTONIC, &current)) goto finish;
        if (current.tv_sec - started.tv_sec >= 5) { errno = ETIMEDOUT; goto finish; }
        if (ioctl(pcm, SNDRV_PCM_IOCTL_WRITEI_FRAMES, &transfer)) {
            struct pollfd event = {.fd = pcm, .events = POLLOUT};
            if (errno == EINTR) continue;
            if (errno != EAGAIN || poll(&event, 1, 20) < 0) goto finish;
            /* Some PCM poll implementations report ready while a small write
             * still returns EAGAIN. Back off rather than consume an iteration
             * budget or hammer sysfs before hardware has advanced. */
            usleep(1000);
            continue;
        }
        if (transfer.result <= 0 || (snd_pcm_uframes_t)transfer.result > transfer.frames) goto finish;
        frames += transfer.result;
        if (i % 8 == 0 || frames == 24576) {
            if (audio_state(&control, &rd, &gain, &mute) || gain || !mute) goto finish;
            moved |= rd != first;
        }
    }
    after = audio_irqs();
    drop_rc = ioctl(pcm, SNDRV_PCM_IOCTL_DROP);
    if (audio_state(&control, &rd, &gain, &mute)) goto finish;
    printf("audio_frames=%ld dma_moved=%u irq_before=%lu irq_after=%lu drop_rc=%d stopped=%u\n",
           frames, moved, before, after, drop_rc, !(control & (1u << 16)));
    if (frames != 24576 || !moved || after <= before || drop_rc || (control & (1u << 16)) || gain || !mute) goto finish;
    puts("audio_silent_dma=PASS\naudible_output=NOT_TESTED"); result = 0;
finish:
    reason = result ? errno : 0;
    if (pcm >= 0) {
        if (result) ioctl(pcm, SNDRV_PCM_IOCTL_DROP);
        close(pcm);
    }
    printf("audio_probe_rc=%d errno=%d\nR36 AUDIO SILENT PROBE END\n", result, reason);
    return result;
}
#endif
