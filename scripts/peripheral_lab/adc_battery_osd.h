/* SPDX-License-Identifier: MIT
 * Userspace battery percentage curve and charging helper for /dev/check_adc1
 * and /dev/check_adc5 (matching RE notes in osd-battery-volume.md).
 *
 * Stock/TreeFrogUI keep both fds open with O_RDWR across polls and read 1 raw
 * calibrated byte (0..255) per sample without closing or seeking.
 */
#ifndef R36_ADC_BATTERY_OSD_H
#define R36_ADC_BATTERY_OSD_H

#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <unistd.h>

#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif

#define R36_CHECK_ADC1_PATH      "/dev/check_adc1"
#define R36_CHECK_ADC5_PATH      "/dev/check_adc5"
#define R36_BAT_ADC_MIN          64u
#define R36_BAT_ADC_MID          153u
#define R36_BAT_ADC_MAX          180u
#define R36_CHARGE_ADC_THRESHOLD 64u

struct r36_battery_monitor {
    int bat_fd;
    int chg_fd;
};

struct r36_battery_status {
    uint8_t raw_battery;
    uint8_t raw_charge;
    uint8_t percent;
    int charging;
};

static inline uint8_t r36_battery_percent_from_adc(uint8_t raw)
{
    if (raw <= R36_BAT_ADC_MIN)
        return 0u;
    if (raw >= R36_BAT_ADC_MAX)
        return 100u;
    if (raw <= R36_BAT_ADC_MID) {
        return (uint8_t)(((unsigned int)(raw - R36_BAT_ADC_MIN) * 50u) /
                         (R36_BAT_ADC_MID - R36_BAT_ADC_MIN));
    }
    return (uint8_t)(50u + (((unsigned int)(raw - R36_BAT_ADC_MID) * 50u) /
                            (R36_BAT_ADC_MAX - R36_BAT_ADC_MID)));
}

static inline int r36_is_charging_from_adc(uint8_t raw)
{
    return raw >= R36_CHARGE_ADC_THRESHOLD ? 1 : 0;
}

static inline void r36_battery_monitor_init(struct r36_battery_monitor *mon)
{
    if (!mon)
        return;
    mon->bat_fd = -1;
    mon->chg_fd = -1;
}

static inline void r36_battery_close(struct r36_battery_monitor *mon)
{
    if (!mon)
        return;
    if (mon->bat_fd >= 0) {
        close(mon->bat_fd);
        mon->bat_fd = -1;
    }
    if (mon->chg_fd >= 0) {
        close(mon->chg_fd);
        mon->chg_fd = -1;
    }
}

static inline int r36_battery_open(struct r36_battery_monitor *mon)
{
    if (!mon) {
        errno = EINVAL;
        return -1;
    }
    r36_battery_close(mon);
    mon->bat_fd = open(R36_CHECK_ADC1_PATH, O_RDWR | O_CLOEXEC);
    if (mon->bat_fd < 0)
        return -1;
    mon->chg_fd = open(R36_CHECK_ADC5_PATH, O_RDWR | O_CLOEXEC);
    if (mon->chg_fd < 0) {
        int saved = errno;
        r36_battery_close(mon);
        errno = saved;
        return -1;
    }
    return 0;
}

static inline int r36_battery_read_byte(int fd, uint8_t *out)
{
    if (fd < 0 || !out) {
        errno = EINVAL;
        return -1;
    }
    for (;;) {
        ssize_t n = read(fd, out, 1);
        if (n == 1)
            return 0;
        if (n < 0 && errno == EINTR)
            continue;
        if (n == 0)
            errno = EIO;
        return -1;
    }
}

static inline int r36_battery_poll(const struct r36_battery_monitor *mon,
                                   struct r36_battery_status *out)
{
    uint8_t bat = 0, chg = 0;

    if (!mon || !out) {
        errno = EINVAL;
        return -1;
    }
    if (r36_battery_read_byte(mon->bat_fd, &bat) != 0)
        return -1;
    if (r36_battery_read_byte(mon->chg_fd, &chg) != 0)
        return -1;

    out->raw_battery = bat;
    out->raw_charge = chg;
    out->percent = r36_battery_percent_from_adc(bat);
    out->charging = r36_is_charging_from_adc(chg);
    return 0;
}

#endif
