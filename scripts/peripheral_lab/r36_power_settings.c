/* SPDX-License-Identifier: MIT
 * On-console framebuffer + evdev settings editor & CLI for R36S power/display timers:
 *  - Screen Off Timer (OFF / 30S / 1M / 2M / 5M / 10M / 15M; 5s smooth fade before off)
 *  - Auto Poweroff Timer (OFF / 5M / 10M / 15M / 30M / 60M)
 *  - Volume % (0..100) and Brightness % (5..100)
 * Persists to /mnt/sdcard/cubegm/r36_sysd.conf (hot-reloaded by r36_sysd).
 */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef R36_POWER_SETTINGS_MOCK
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <sys/mman.h>
#include <unistd.h>
#else
#define R36_SCREEN_STATUS_MOCK 1
#endif

#include "../kernel_lab/r36_screen_status.h"
#include "r36_sysd_conf.h"

#ifndef EV_KEY
#define EV_KEY 0x01
#endif

/* Standard Linux evdev keycodes used on R36S (D-pad + A/B/START/SELECT) */
#ifndef KEY_UP
#define KEY_UP     103
#endif
#ifndef KEY_DOWN
#define KEY_DOWN   108
#endif
#ifndef KEY_LEFT
#define KEY_LEFT   105
#endif
#ifndef KEY_RIGHT
#define KEY_RIGHT  106
#endif
#ifndef KEY_ENTER
#define KEY_ENTER  28
#endif
#ifndef KEY_ESC
#define KEY_ESC    1
#endif
#ifndef BTN_SOUTH
#define BTN_SOUTH  304
#endif
#ifndef BTN_EAST
#define BTN_EAST   305
#endif
#ifndef BTN_SELECT
#define BTN_SELECT 314
#endif
#ifndef BTN_START
#define BTN_START  315
#endif

enum r36_power_ui_row {
    R36_ROW_SCREEN_OFF = 0,
    R36_ROW_AUTO_POWEROFF = 1,
    R36_ROW_VOLUME = 2,
    R36_ROW_BRIGHTNESS = 3,
    R36_ROW_SAVE_EXIT = 4,
    R36_ROW_COUNT = 5
};

enum r36_power_ui_result {
    R36_UI_CONTINUE = 0,
    R36_UI_SAVED_EXIT = 1,
    R36_UI_CANCEL_EXIT = 2
};

struct r36_power_ui_state {
    struct r36_sysd_conf conf;
    int cursor;
    int dirty;
    const char *conf_path;
};

static const int k_screen_off_presets[] = { 0, 30, 60, 120, 300, 600, 900 };
static const int k_auto_poweroff_presets[] = { 0, 300, 600, 900, 1800, 3600 };

static int r36_step_preset(int current, const int *presets, int count, int dir)
{
    int i;
    if (dir > 0) {
        for (i = 0; i < count; i++) {
            if (presets[i] > current)
                return presets[i];
        }
        return presets[0];
    }
    for (i = count - 1; i >= 0; i--) {
        if (presets[i] < current)
            return presets[i];
    }
    return presets[count - 1];
}

static void r36_format_duration(int sec, char *out, size_t out_sz)
{
    if (sec <= 0)
        snprintf(out, out_sz, "OFF");
    else if (sec < 60 || (sec % 60) != 0)
        snprintf(out, out_sz, "%dS", sec);
    else
        snprintf(out, out_sz, "%dM", sec / 60);
}

static void r36_power_ui_init(struct r36_power_ui_state *ui, const char *conf_path)
{
    memset(ui, 0, sizeof(*ui));
    ui->conf_path = conf_path ? conf_path : R36_SYSD_CONF_DEFAULT_PATH;
    r36_sysd_conf_defaults(&ui->conf);
    (void)r36_sysd_conf_load(ui->conf_path, &ui->conf);
}

static enum r36_power_ui_result r36_power_ui_step_key(struct r36_power_ui_state *ui,
                                                      uint16_t code, int32_t value)
{
    int dir = 0;
    if (value == 0)
        return R36_UI_CONTINUE;

    if (code == KEY_UP) {
        ui->cursor = (ui->cursor + R36_ROW_COUNT - 1) % R36_ROW_COUNT;
        return R36_UI_CONTINUE;
    }
    if (code == KEY_DOWN) {
        ui->cursor = (ui->cursor + 1) % R36_ROW_COUNT;
        return R36_UI_CONTINUE;
    }
    if (code == KEY_LEFT)
        dir = -1;
    else if (code == KEY_RIGHT)
        dir = 1;

    if (dir != 0) {
        switch (ui->cursor) {
        case R36_ROW_SCREEN_OFF:
            ui->conf.screen_off_sec = r36_step_preset(
                ui->conf.screen_off_sec, k_screen_off_presets,
                (int)(sizeof(k_screen_off_presets) / sizeof(k_screen_off_presets[0])), dir);
            ui->dirty = 1;
            break;
        case R36_ROW_AUTO_POWEROFF:
            ui->conf.auto_poweroff_sec = r36_step_preset(
                ui->conf.auto_poweroff_sec, k_auto_poweroff_presets,
                (int)(sizeof(k_auto_poweroff_presets) / sizeof(k_auto_poweroff_presets[0])), dir);
            ui->dirty = 1;
            break;
        case R36_ROW_VOLUME:
            ui->conf.volume_pct = r36_conf_clamp_int(ui->conf.volume_pct + dir * 5, 0, 100);
            ui->dirty = 1;
            break;
        case R36_ROW_BRIGHTNESS:
            ui->conf.brightness_pct = r36_conf_clamp_int(ui->conf.brightness_pct + dir * 5, 5, 100);
            ui->dirty = 1;
            break;
        default:
            break;
        }
        return R36_UI_CONTINUE;
    }

    if (code == BTN_SOUTH || code == BTN_START || code == KEY_ENTER) {
        (void)r36_sysd_conf_save(ui->conf_path, &ui->conf);
        ui->dirty = 0;
        return R36_UI_SAVED_EXIT;
    }
    if (code == BTN_EAST || code == BTN_SELECT || code == KEY_ESC)
        return R36_UI_CANCEL_EXIT;

    return R36_UI_CONTINUE;
}

static void r36_power_ui_render(uint16_t *fb, const struct r36_power_ui_state *ui)
{
    static const char *const labels[R36_ROW_COUNT] = {
        "SCREEN OFF TIMER",
        "AUTO POWEROFF",
        "VOLUME",
        "BRIGHTNESS",
        "SAVE AND EXIT"
    };
    char val_buf[32];
    int i;

    if (!fb || !ui)
        return;

    r36_fb_fill_rect(fb, 0, 0, R36_FB_WIDTH, R36_FB_HEIGHT, 0x0842u);
    r36_fb_fill_rect(fb, 28, 36, R36_FB_WIDTH - 56, 4, 0xBDF7u);
    r36_fb_fill_rect(fb, 28, R36_FB_HEIGHT - 44, R36_FB_WIDTH - 56, 4, 0xBDF7u);
    r36_fb_draw_text(fb, 40, 56, "R36S POWER SETTINGS", 0xFFFFu, 3);

    for (i = 0; i < R36_ROW_COUNT; i++) {
        int y = 128 + i * 52;
        uint16_t row_bg = (i == ui->cursor) ? 0x1A50u : 0x1084u;
        uint16_t fg = (i == ui->cursor) ? 0xFFE0u : 0xFFFFu;

        r36_fb_fill_rect(fb, 40, y - 8, R36_FB_WIDTH - 80, 40, row_bg);
        r36_fb_draw_text(fb, 56, y + 4, labels[i], fg, 2);

        val_buf[0] = '\0';
        if (i == R36_ROW_SCREEN_OFF)
            r36_format_duration(ui->conf.screen_off_sec, val_buf, sizeof(val_buf));
        else if (i == R36_ROW_AUTO_POWEROFF)
            r36_format_duration(ui->conf.auto_poweroff_sec, val_buf, sizeof(val_buf));
        else if (i == R36_ROW_VOLUME)
            snprintf(val_buf, sizeof(val_buf), "%d%%", ui->conf.volume_pct);
        else if (i == R36_ROW_BRIGHTNESS)
            snprintf(val_buf, sizeof(val_buf), "%d%%", ui->conf.brightness_pct);

        if (val_buf[0] != '\0')
            r36_fb_draw_text(fb, 440, y + 4, val_buf, fg, 2);
    }

    r36_fb_draw_text(fb, 40, 404, "A/START: SAVE   B/SELECT: CANCEL", 0xDEFBu, 2);
}

#ifndef R36_POWER_SETTINGS_MOCK
static int r36_open_evdev_opt(const char *path)
{
    return path ? open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC) : -1;
}

static int r36_run_cli(int argc, char **argv, const char *conf_path)
{
    struct r36_sysd_conf c;
    int i, get_only = 0, modified = 0;

    r36_sysd_conf_defaults(&c);
    (void)r36_sysd_conf_load(conf_path, &c);

    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--config") && i + 1 < argc) {
            i++;
        } else if (!strcmp(argv[i], "--get")) {
            get_only = 1;
        } else if (!strcmp(argv[i], "--screen-off") && i + 1 < argc) {
            c.screen_off_sec = atoi(argv[++i]);
            modified = 1;
        } else if (!strcmp(argv[i], "--auto-poweroff") && i + 1 < argc) {
            c.auto_poweroff_sec = atoi(argv[++i]);
            modified = 1;
        } else if (!strcmp(argv[i], "--volume") && i + 1 < argc) {
            c.volume_pct = atoi(argv[++i]);
            modified = 1;
        } else if (!strcmp(argv[i], "--brightness") && i + 1 < argc) {
            c.brightness_pct = atoi(argv[++i]);
            modified = 1;
        } else {
            fprintf(stderr, "Usage: %s [--config PATH] [--get] [--screen-off SEC] [--auto-poweroff SEC] [--volume PCT] [--brightness PCT]\n", argv[0]);
            return 2;
        }
    }

    r36_sysd_conf_clamp(&c);
    if (modified) {
        if (r36_sysd_conf_save(conf_path, &c) != 0) {
            perror("save config");
            return 1;
        }
    }
    if (get_only || modified) {
        printf("volume_pct=%d\nbrightness_pct=%d\nscreen_off_sec=%d\nauto_poweroff_sec=%d\n",
               c.volume_pct, c.brightness_pct, c.screen_off_sec, c.auto_poweroff_sec);
        return 0;
    }
    return -1;
}

int main(int argc, char **argv)
{
    const char *conf_path = R36_SYSD_CONF_DEFAULT_PATH;
    int i, cli_rc;
    int fb_fd, fd0, fd1;
    size_t fb_bytes = (size_t)R36_FB_WIDTH * (size_t)R36_FB_HEIGHT * sizeof(uint16_t);
    uint16_t *fb;
    struct r36_power_ui_state ui;
    enum r36_power_ui_result res = R36_UI_CONTINUE;

    for (i = 1; i + 1 < argc; i++) {
        if (!strcmp(argv[i], "--config"))
            conf_path = argv[i + 1];
    }
    if (argc > 1) {
        cli_rc = r36_run_cli(argc, argv, conf_path);
        if (cli_rc >= 0)
            return cli_rc;
    }

    fb_fd = open("/dev/fb0", O_RDWR | O_CLOEXEC);
    if (fb_fd < 0)
        return 1;
    fb = (uint16_t *)mmap(NULL, fb_bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fb_fd, 0);
    if (fb == MAP_FAILED) {
        close(fb_fd);
        return 1;
    }

    fd0 = r36_open_evdev_opt("/dev/input/event0");
    fd1 = r36_open_evdev_opt("/dev/input/event1");
    r36_power_ui_init(&ui, conf_path);
    r36_power_ui_render(fb, &ui);

    while (res == R36_UI_CONTINUE) {
        struct pollfd pfds[2];
        nfds_t nfds = 0;
        int fds[2];
        int k;

        if (fd0 >= 0) {
            fds[nfds] = fd0;
            pfds[nfds].fd = fd0;
            pfds[nfds].events = POLLIN;
            pfds[nfds].revents = 0;
            nfds++;
        }
        if (fd1 >= 0) {
            fds[nfds] = fd1;
            pfds[nfds].fd = fd1;
            pfds[nfds].events = POLLIN;
            pfds[nfds].revents = 0;
            nfds++;
        }
        if (nfds == 0)
            break;
        (void)poll(pfds, nfds, 250);
        for (k = 0; k < (int)nfds && res == R36_UI_CONTINUE; k++) {
            struct input_event ev;
            while (read(fds[k], &ev, sizeof(ev)) == (ssize_t)sizeof(ev)) {
                if (ev.type == EV_KEY) {
                    res = r36_power_ui_step_key(&ui, ev.code, ev.value);
                    r36_power_ui_render(fb, &ui);
                    if (res != R36_UI_CONTINUE)
                        break;
                }
            }
        }
    }

    if (fd0 >= 0) close(fd0);
    if (fd1 >= 0) close(fd1);
    munmap(fb, fb_bytes);
    close(fb_fd);
    return 0;
}
#endif
