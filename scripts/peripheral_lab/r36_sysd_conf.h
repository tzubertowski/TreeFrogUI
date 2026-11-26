/* SPDX-License-Identifier: MIT
 * Shared configuration schema & persistence for r36_sysd and r36_power_settings.
 */
#ifndef R36_SYSD_CONF_H
#define R36_SYSD_CONF_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef R36_SYSD_MOCK
#include <fcntl.h>
#include <unistd.h>
#endif

#ifndef O_RDONLY
#define O_RDONLY 0
#endif
#ifndef O_WRONLY
#define O_WRONLY 1
#endif
#ifndef O_CREAT
#define O_CREAT 0x40
#endif
#ifndef O_TRUNC
#define O_TRUNC 0x200
#endif
#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif

#define R36_SYSD_CONF_DEFAULT_PATH "/mnt/sdcard/cubegm/r36_sysd.conf"
#define R36_SYSD_MAX_TIMEOUT_SEC   86400

struct r36_sysd_conf {
    int volume_pct;
    int brightness_pct;
    int screen_off_sec;
    int auto_poweroff_sec;
};

static inline int r36_conf_clamp_int(int val, int lo, int hi)
{
    if (val < lo)
        return lo;
    if (val > hi)
        return hi;
    return val;
}

static inline void r36_sysd_conf_defaults(struct r36_sysd_conf *c)
{
    if (!c)
        return;
    c->volume_pct = 60;
    c->brightness_pct = 80;
    c->screen_off_sec = 120;
    c->auto_poweroff_sec = 600;
}

static inline void r36_sysd_conf_clamp(struct r36_sysd_conf *c)
{
    if (!c)
        return;
    c->volume_pct = r36_conf_clamp_int(c->volume_pct, 0, 100);
    c->brightness_pct = r36_conf_clamp_int(c->brightness_pct, 5, 100);
    c->screen_off_sec = r36_conf_clamp_int(c->screen_off_sec, 0, R36_SYSD_MAX_TIMEOUT_SEC);
    c->auto_poweroff_sec = r36_conf_clamp_int(c->auto_poweroff_sec, 0, R36_SYSD_MAX_TIMEOUT_SEC);
}

static inline void r36_sysd_conf_parse(const char *buf, struct r36_sysd_conf *c)
{
    const char *p;
    if (!buf || !c)
        return;
    p = strstr(buf, "volume_pct=");
    if (p)
        c->volume_pct = atoi(p + 11);
    p = strstr(buf, "brightness_pct=");
    if (p)
        c->brightness_pct = atoi(p + 15);
    p = strstr(buf, "screen_off_sec=");
    if (p)
        c->screen_off_sec = atoi(p + 15);
    p = strstr(buf, "auto_poweroff_sec=");
    if (p)
        c->auto_poweroff_sec = atoi(p + 18);
    r36_sysd_conf_clamp(c);
}

static inline int r36_sysd_conf_load(const char *path, struct r36_sysd_conf *c)
{
    char buf[256];
    int fd;
    ssize_t n;

    if (!path || !c)
        return -1;
    fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0)
        return -1;
    n = read(fd, buf, sizeof(buf) - 1u);
    close(fd);
    if (n <= 0)
        return -1;
    buf[n] = '\0';
    r36_sysd_conf_parse(buf, c);
    return 0;
}

static inline int r36_sysd_conf_save(const char *path, const struct r36_sysd_conf *in)
{
    struct r36_sysd_conf c;
    char buf[256];
    int fd, len;
    ssize_t n;

    if (!path || !in)
        return -1;
    c = *in;
    r36_sysd_conf_clamp(&c);
    fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    if (fd < 0)
        return -1;
    len = snprintf(buf, sizeof(buf),
                   "volume_pct=%d\n"
                   "brightness_pct=%d\n"
                   "screen_off_sec=%d\n"
                   "auto_poweroff_sec=%d\n",
                   c.volume_pct, c.brightness_pct,
                   c.screen_off_sec, c.auto_poweroff_sec);
    if (len <= 0 || (size_t)len >= sizeof(buf)) {
        close(fd);
        return -1;
    }
    n = write(fd, buf, (size_t)len);
    close(fd);
    return (n == (ssize_t)len) ? 0 : -1;
}

#endif /* R36_SYSD_CONF_H */
