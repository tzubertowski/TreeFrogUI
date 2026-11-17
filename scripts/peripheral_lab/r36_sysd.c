/* SPDX-License-Identifier: MIT
 * Unified peripheral system daemon for R36S on Linux 7.2:
 *  - Direct keys (FN, VOL+, VOL-, POWER, L2, R2) via direct_keys_policy.h
 *  - Speaker PA (GPIO19) conditioned on HP-detect (GPIO15), mute, volume, sleep
 *  - PWM backlight (/sys/class/backlight) brightness scaling 5..100%
 *  - Persistent /dev/check_adc1 + /dev/check_adc5 battery/charge polling
 *  - Clean poweroff (mute PA, backlight off, sync, swapoff, umount, RB_POWER_OFF)
 */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef R36_SYSD_MOCK
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <sys/reboot.h>
#include <sys/swap.h>
#include <sys/mount.h>
#include <time.h>
#include <unistd.h>
#else
#ifndef O_RDONLY
#define O_RDONLY 0
#endif
#ifndef O_WRONLY
#define O_WRONLY 1
#endif
#ifndef O_RDWR
#define O_RDWR 2
#endif
#ifndef O_NONBLOCK
#define O_NONBLOCK 0x800
#endif
#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif
#ifndef O_CREAT
#define O_CREAT 0x40
#endif
#ifndef O_TRUNC
#define O_TRUNC 0x200
#endif
#ifndef RB_POWER_OFF
#define RB_POWER_OFF 0x4321fedcu
#endif
#ifndef EV_KEY
#define EV_KEY 0x01
#endif
struct r36_input_event_compat {
    long tv_sec;
    long tv_usec;
    uint16_t type;
    uint16_t code;
    int32_t value;
};
#define input_event r36_input_event_compat
#endif

#include "adc_battery_osd.h"
#include "direct_keys_policy.h"
#include "r36_sysd_conf.h"

struct r36_sysd_paths {
    const char *evdev_path;
    const char *evdev_game_path;
    const char *backlight_max_path;
    const char *backlight_cur_path;
    const char *gpio15_hp_path;
    const char *gpio19_amp_path;
    const char *battery_status_path;
    const char *config_path;
    const char *sd_mountpoint;
    const char *sd_swapfile;
};

struct r36_sysd_state {
    struct r36_sysd_paths paths;
    struct r36_direct_keys_policy keys;
    struct r36_battery_monitor bat;
    struct r36_battery_status bat_status;
    struct r36_sysd_conf conf;
    int evdev_fd;
    int evdev_game_fd;
    int sleeping;
    int idle_screen_off;
    int dim_active;
    int dim_pct;
    int muted;
    int hp_active_low;
    int max_brightness;
    int last_amp_enable;
    int last_bl_raw;
    int shutdown_requested;
    uint64_t last_bat_poll_ms;
    uint64_t last_activity_ms;
    uint64_t last_conf_poll_ms;
};

static int r36_read_sysfs_int(const char *path, int fallback)
{
    char buf[32];
    int fd;
    ssize_t n;

    if (!path)
        return fallback;
    fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0)
        return fallback;
    n = read(fd, buf, sizeof(buf) - 1u);
    close(fd);
    if (n <= 0)
        return fallback;
    buf[n] = '\0';
    return atoi(buf);
}

static int r36_write_sysfs_int(const char *path, int val)
{
    char buf[32];
    int fd, len;
    ssize_t n;

    if (!path)
        return -1;
    fd = open(path, O_WRONLY | O_TRUNC | O_CLOEXEC);
    if (fd < 0)
        return -1;
    len = snprintf(buf, sizeof(buf), "%d\n", val);
    if (len <= 0 || (size_t)len >= sizeof(buf)) {
        close(fd);
        return -1;
    }
    n = write(fd, buf, (size_t)len);
    close(fd);
    return (n == (ssize_t)len) ? 0 : -1;
}

static void r36_sysd_default_paths(struct r36_sysd_paths *p)
{
    p->evdev_path = "/dev/input/event1";
    p->evdev_game_path = "/dev/input/event0";
    p->backlight_max_path = "/sys/class/backlight/backlight/max_brightness";
    p->backlight_cur_path = "/sys/class/backlight/backlight/brightness";
    p->gpio15_hp_path = "/sys/class/gpio/gpio15/value";
    p->gpio19_amp_path = "/sys/class/gpio/gpio19/value";
    p->battery_status_path = "/tmp/r36-battery.status";
    p->config_path = R36_SYSD_CONF_DEFAULT_PATH;
    p->sd_mountpoint = "/mnt/sdcard";
    p->sd_swapfile = "/mnt/sdcard/cubegm/pagefile.sys";
}

static void r36_sysd_save_config(struct r36_sysd_state *st)
{
    if (!st || !st->paths.config_path)
        return;
    st->conf.volume_pct = st->keys.volume_pct;
    st->conf.brightness_pct = st->keys.brightness_pct;
    (void)r36_sysd_conf_save(st->paths.config_path, &st->conf);
}

static int r36_sysd_apply_backlight(struct r36_sysd_state *st)
{
    int pct = st->sleeping ? 0 : (st->dim_active ? st->dim_pct : st->keys.brightness_pct);
    int raw = (pct * st->max_brightness) / 100;

    if (raw == st->last_bl_raw)
        return 0;
    if (r36_write_sysfs_int(st->paths.backlight_cur_path, raw) == 0) {
        st->last_bl_raw = raw;
        return 0;
    }
    return -1;
}

static int r36_sysd_apply_speaker_amp(struct r36_sysd_state *st)
{
    int hp_lvl = r36_read_sysfs_int(st->paths.gpio15_hp_path, st->hp_active_low ? 1 : 0);
    int en = r36_speaker_amp_should_enable(hp_lvl, st->hp_active_low, st->muted,
                                           st->keys.volume_pct, st->sleeping);
    if (en == st->last_amp_enable)
        return 0;
    if (r36_write_sysfs_int(st->paths.gpio19_amp_path, en) == 0) {
        st->last_amp_enable = en;
        return 0;
    }
    return -1;
}

static void r36_sysd_publish_battery(struct r36_sysd_state *st)
{
    char buf[96];
    int fd, len;

    if (!st->paths.battery_status_path)
        return;
    fd = open(st->paths.battery_status_path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    if (fd < 0)
        return;
    len = snprintf(buf, sizeof(buf), "percent=%u charging=%d raw_bat=%u raw_chg=%u\n",
                   (unsigned int)st->bat_status.percent,
                   st->bat_status.charging,
                   (unsigned int)st->bat_status.raw_battery,
                   (unsigned int)st->bat_status.raw_charge);
    if (len > 0 && (size_t)len < sizeof(buf)) {
        ssize_t ignored = write(fd, buf, (size_t)len);
        (void)ignored;
    }
    close(fd);
}

static int r36_sysd_clean_shutdown(struct r36_sysd_state *st)
{
    r36_sysd_save_config(st);
    st->sleeping = 1;
    st->last_amp_enable = -1;
    st->last_bl_raw = -1;
    r36_sysd_apply_speaker_amp(st);
    r36_sysd_apply_backlight(st);
    r36_battery_close(&st->bat);
    if (st->evdev_fd >= 0) {
        close(st->evdev_fd);
        st->evdev_fd = -1;
    }
    if (st->evdev_game_fd >= 0) {
        close(st->evdev_game_fd);
        st->evdev_game_fd = -1;
    }
    sync();
    if (st->paths.sd_swapfile)
        (void)swapoff(st->paths.sd_swapfile);
    if (st->paths.sd_mountpoint)
        (void)umount(st->paths.sd_mountpoint);
    sync();
    return reboot(RB_POWER_OFF);
}

static int r36_sysd_init(struct r36_sysd_state *st, const struct r36_sysd_paths *custom_paths)
{
    if (!st)
        return -1;
    memset(st, 0, sizeof(*st));
    st->evdev_fd = -1;
    st->evdev_game_fd = -1;
    if (custom_paths)
        st->paths = *custom_paths;
    else
        r36_sysd_default_paths(&st->paths);

    r36_sysd_conf_defaults(&st->conf);
    if (st->paths.config_path)
        (void)r36_sysd_conf_load(st->paths.config_path, &st->conf);
    r36_direct_keys_policy_init(&st->keys, st->conf.volume_pct, st->conf.brightness_pct);
    r36_battery_monitor_init(&st->bat);
    st->hp_active_low = 1;
    st->last_amp_enable = -1;
    st->last_bl_raw = -1;
    st->max_brightness = r36_read_sysfs_int(st->paths.backlight_max_path, 255);
    if (st->max_brightness <= 0)
        st->max_brightness = 255;

    st->evdev_fd = open(st->paths.evdev_path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    if (st->evdev_fd < 0)
        return -1;
    if (st->paths.evdev_game_path)
        st->evdev_game_fd = open(st->paths.evdev_game_path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    (void)r36_battery_open(&st->bat);
    (void)r36_sysd_apply_backlight(st);
    (void)r36_sysd_apply_speaker_amp(st);
    return 0;
}

static void r36_sysd_process_action(struct r36_sysd_state *st, enum r36_direct_action act)
{
    switch (act) {
    case R36_DIRECT_ACTION_VOLUME_CHANGED:
        (void)r36_sysd_apply_speaker_amp(st);
        r36_sysd_save_config(st);
        break;
    case R36_DIRECT_ACTION_BRIGHTNESS_CHANGED:
        (void)r36_sysd_apply_backlight(st);
        r36_sysd_save_config(st);
        break;
    case R36_DIRECT_ACTION_SLEEP_TOGGLE:
        st->sleeping = !st->sleeping;
        st->idle_screen_off = 0;
        (void)r36_sysd_apply_speaker_amp(st);
        (void)r36_sysd_apply_backlight(st);
        break;
    case R36_DIRECT_ACTION_POWEROFF:
        st->shutdown_requested = 1;
        break;
    default:
        break;
    }
}

static int r36_sysd_drain_evdev(struct r36_sysd_state *st, int fd, int process_direct, uint64_t now_ms)
{
    struct input_event ev;

    if (fd < 0)
        return 0;
    for (;;) {
        ssize_t n = read(fd, &ev, sizeof(ev));
        if (n < 0) {
            if (errno == EINTR)
                continue;
            if (errno == EAGAIN || errno == EWOULDBLOCK)
                break;
            return -1;
        }
        if (n != (ssize_t)sizeof(ev))
            break;
        if (ev.type == EV_KEY) {
            int need_restore = 0;
            st->last_activity_ms = now_ms;
            if (st->dim_active) {
                st->dim_active = 0;
                st->dim_pct = 0;
                need_restore = 1;
            }
            if (st->sleeping && st->idle_screen_off && ev.value == 1) {
                st->sleeping = 0;
                st->idle_screen_off = 0;
                need_restore = 1;
            }
            if (need_restore) {
                (void)r36_sysd_apply_speaker_amp(st);
                (void)r36_sysd_apply_backlight(st);
            }
            if (process_direct) {
                enum r36_direct_action act = r36_direct_keys_handle_event(
                    &st->keys, ev.code, ev.value, now_ms);
                r36_sysd_process_action(st, act);
            }
        }
    }
    return 0;
}

static void r36_sysd_poll_config(struct r36_sysd_state *st, uint64_t now_ms)
{
    struct r36_sysd_conf fresh;

    if (!st->paths.config_path)
        return;
    if (st->last_conf_poll_ms != 0 && now_ms - st->last_conf_poll_ms < 2000ULL)
        return;
    st->last_conf_poll_ms = now_ms;
    fresh = st->conf;
    if (r36_sysd_conf_load(st->paths.config_path, &fresh) != 0)
        return;
    if (fresh.volume_pct != st->conf.volume_pct ||
        fresh.brightness_pct != st->conf.brightness_pct ||
        fresh.screen_off_sec != st->conf.screen_off_sec ||
        fresh.auto_poweroff_sec != st->conf.auto_poweroff_sec) {
        st->conf = fresh;
        st->keys.volume_pct = fresh.volume_pct;
        st->keys.brightness_pct = fresh.brightness_pct;
        (void)r36_sysd_apply_speaker_amp(st);
        (void)r36_sysd_apply_backlight(st);
    }
}

static int r36_sysd_step(struct r36_sysd_state *st, uint64_t now_ms)
{
    uint64_t idle_ms;

    if (!st || st->evdev_fd < 0)
        return -1;
    if (st->last_activity_ms == 0)
        st->last_activity_ms = now_ms;

    if (r36_sysd_drain_evdev(st, st->evdev_fd, 1, now_ms) != 0)
        return -1;
    if (st->evdev_game_fd >= 0 && r36_sysd_drain_evdev(st, st->evdev_game_fd, 0, now_ms) != 0) {
        close(st->evdev_game_fd);
        st->evdev_game_fd = -1;
    }

    r36_sysd_process_action(st, r36_direct_keys_tick(&st->keys, now_ms));
    r36_sysd_poll_config(st, now_ms);
    (void)r36_sysd_apply_speaker_amp(st);

    idle_ms = (now_ms >= st->last_activity_ms) ? (now_ms - st->last_activity_ms) : 0ULL;
    if (st->conf.screen_off_sec > 0 && !st->sleeping) {
        uint64_t off_ms = (uint64_t)st->conf.screen_off_sec * 1000ULL;
        uint64_t fade_ms = (off_ms > 5000ULL) ? 5000ULL : off_ms;
        if (idle_ms >= off_ms) {
            st->dim_active = 0;
            st->dim_pct = 0;
            st->sleeping = 1;
            st->idle_screen_off = 1;
            (void)r36_sysd_apply_speaker_amp(st);
            (void)r36_sysd_apply_backlight(st);
        } else if (fade_ms > 0 && idle_ms >= off_ms - fade_ms) {
            uint64_t rem_ms = off_ms - idle_ms;
            int pct = (int)(((uint64_t)st->keys.brightness_pct * rem_ms) / fade_ms);
            if (pct < 1)
                pct = 1;
            st->dim_active = 1;
            st->dim_pct = pct;
            (void)r36_sysd_apply_backlight(st);
        } else if (st->dim_active) {
            st->dim_active = 0;
            st->dim_pct = 0;
            (void)r36_sysd_apply_backlight(st);
        }
    }
    if (st->conf.auto_poweroff_sec > 0 &&
        idle_ms >= (uint64_t)st->conf.auto_poweroff_sec * 1000ULL) {
        st->shutdown_requested = 1;
    }

    if (st->bat.bat_fd >= 0 && st->bat.chg_fd >= 0 &&
        (st->last_bat_poll_ms == 0 || now_ms - st->last_bat_poll_ms >= 5000ULL)) {
        if (r36_battery_poll(&st->bat, &st->bat_status) == 0) {
            st->last_bat_poll_ms = now_ms;
            r36_sysd_publish_battery(st);
        }
    }

    if (st->shutdown_requested) {
        (void)r36_sysd_clean_shutdown(st);
        return 1;
    }
    return 0;
}

#ifndef R36_SYSD_LIBRARY_ONLY
static uint64_t r36_monotonic_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000ULL + (uint64_t)(ts.tv_nsec / 1000000L);
}

int main(void)
{
    struct r36_sysd_state st;
    if (r36_sysd_init(&st, NULL) != 0)
        return 1;
    for (;;) {
        struct pollfd pfds[2];
        nfds_t nfds = 1;
        int timeout_ms = st.dim_active ? 100 : 250;

        pfds[0].fd = st.evdev_fd;
        pfds[0].events = POLLIN;
        pfds[0].revents = 0;
        if (st.evdev_game_fd >= 0) {
            pfds[1].fd = st.evdev_game_fd;
            pfds[1].events = POLLIN;
            pfds[1].revents = 0;
            nfds = 2;
        }
        (void)poll(pfds, nfds, timeout_ms);
        if (r36_sysd_step(&st, r36_monotonic_ms()) != 0)
            break;
    }
    r36_battery_close(&st.bat);
    if (st.evdev_fd >= 0)
        close(st.evdev_fd);
    if (st.evdev_game_fd >= 0)
        close(st.evdev_game_fd);
    return 0;
}
#endif
