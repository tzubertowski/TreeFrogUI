/* SPDX-License-Identifier: GPL-2.0 */
#ifndef R36_INPUT_PROBE_H
#define R36_INPUT_PROBE_H
#include <dirent.h>
#include <linux/input.h>
#include <poll.h>
#include <time.h>

#ifndef R36_INPUT_CAPTURE_MS
#define R36_INPUT_CAPTURE_MS 12000
#endif
#if R36_INPUT_CAPTURE_MS < 1000 || R36_INPUT_CAPTURE_MS > 60000
#error "Input capture must fit the diagnostic watchdog window"
#endif

static long input_time_ms(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1000L + t.tv_nsec / 1000000L;
}

static int input_probe(void)
{
    struct pollfd fds[16];
    char names[16][128];
    DIR *dir = opendir("/dev/input");
    struct dirent *entry;
    int count = 0, have_serial = 0, have_direct = 0, total = 0, result = -1;
    long end;
    unsigned int dropped = 0;
    puts("R36 INPUT INVENTORY V1");
    if (!dir) { printf("input_open_errno=%d\n", errno); return -1; }
    while ((entry = readdir(dir)) && count < 16) {
        char path[256], name[128] = {0};
        int fd;
        if (strncmp(entry->d_name, "event", 5)) continue;
        if (snprintf(path, sizeof(path), "/dev/input/%.200s", entry->d_name) >= (int)sizeof(path)) continue;
        fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0) continue;
        if (ioctl(fd, EVIOCGNAME(sizeof(name)), name) < 0) { close(fd); continue; }
        if (strcmp(name, "r36-serial-keys") && strcmp(name, "r36-direct-keys")) { close(fd); continue; }
        have_serial |= !strcmp(name, "r36-serial-keys");
        have_direct |= !strcmp(name, "r36-direct-keys");
        fds[count] = (struct pollfd){.fd = fd, .events = POLLIN};
        snprintf(names[count], sizeof(names[count]), "%s", name);
        printf("input_device=%s path=%s\n", name, path);
        count++;
    }
    closedir(dir);
    printf("input_devices=%d serial_present=%d direct_present=%d\n", count, have_serial, have_direct);
    if (!have_serial || !have_direct) goto finish;
    printf("input_capture_ms=%d\n", R36_INPUT_CAPTURE_MS);
    end = input_time_ms() + R36_INPUT_CAPTURE_MS;
    while (input_time_ms() < end) {
        int i, rc = poll(fds, count, 100);
        if (rc < 0 && errno == EINTR) continue;
        if (rc < 0) goto finish;
        for (i = 0; i < count; i++) {
            struct input_event events[32];
            ssize_t bytes;
            if (fds[i].revents & (POLLERR | POLLHUP | POLLNVAL)) goto finish;
            if (!(fds[i].revents & POLLIN)) continue;
            while ((bytes = read(fds[i].fd, events, sizeof(events))) > 0) {
                size_t n;
                if (bytes % sizeof(events[0])) goto finish;
                for (n = 0; n < (size_t)bytes / sizeof(events[0]); n++) {
                    if (events[n].type == EV_SYN && events[n].code == SYN_DROPPED) {
                        dropped++; puts("input_syn_dropped=1"); goto finish;
                    }
                    if (events[n].type != EV_KEY) continue;
                    if (total++ >= 1024) { puts("input_event_limit=1"); goto finish; }
                    printf("input_event device=%s code=%u value=%d\n", names[i], events[n].code, events[n].value);
                }
            }
            if (bytes < 0 && errno != EAGAIN && errno != EINTR) goto finish;
        }
    }
    puts("input_inventory=PASS\nphysical_key_mapping=NOT_VERIFIED");
    result = 0;
finish:
    for (int i = 0; i < count; i++) close(fds[i].fd);
    printf("input_events_recorded=%d dropped=%u\nR36 INPUT INVENTORY END\n", total, dropped);
    return result;
}
#endif
