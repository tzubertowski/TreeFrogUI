#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/ipc.h>
#include <sys/ioctl.h>
#include <sys/shm.h>
#include <sys/stat.h>
#include <unistd.h>
#include "legacy_keys.h"

/* Standalone new-kernel service. Explicit calibrated mapping is mandatory;
 * serial bit order is never inferred from a different board's DTS. */
static volatile sig_atomic_t stopped, requested_stop;
static struct r36_key_bridge state;
static void stop(int number) { (void)number; requested_stop = stopped = 1; }

static int load_mapping(const char *path)
{
    FILE *file = fopen(path, "r");
    char line[128], extra;
    unsigned int code, bit, count = 0;
    unsigned char seen[R36_KEY_LIMIT] = {0};
    if (!file) return -1;
    while (fgets(line, sizeof(line), file)) {
        if (line[0] == '#' || line[0] == '\n') continue;
        if (sscanf(line, "%u %u %c", &code, &bit, &extra) != 2 || code >= R36_KEY_LIMIT ||
            bit >= 32 || seen[code]) { fclose(file); return -1; }
#ifdef R36_KEYS_NAVIGATION_ONLY
        if (bit < 4 || bit > 7) { fclose(file); return -1; }
        for (unsigned int c=0;c<R36_KEY_LIMIT;c++)
            if (state.mapping[c] == (UINT32_C(1) << bit)) { fclose(file); return -1; }
#endif
        seen[code] = 1;
        state.mapping[code] = UINT32_C(1) << bit;
        count++;
    }
    if (ferror(file)) { fclose(file); return -1; }
    fclose(file);
#ifdef R36_KEYS_NAVIGATION_ONLY
    return count == 4 ? 0 : -1;
#else
    return count ? 0 : -1;
#endif
}

int main(int argc, char **argv)
{
    struct pollfd fds[R36_KEY_SOURCES];
    volatile uint32_t *shared;
    int lock, token, id, count, i, result = 1;
    key_t key;
    if (argc < 3 || argc > (int)R36_KEY_SOURCES + 2 || load_mapping(argv[1])) {
        fputs("usage: legacy_keys CALIBRATED_MAP /dev/input/eventN [...]\n", stderr); return 2;
    }
    lock = open("/tmp/r36-legacy-keys.lock", O_RDWR | O_CREAT | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (lock < 0 || flock(lock, LOCK_EX | LOCK_NB)) return 2;
    count = argc - 2;
    for (i = 0; i < count; i++) fds[i] = (struct pollfd){.fd = -1, .events = POLLIN};
    for (i = 0; i < count; i++) {
        struct input_id identity;
        if (strncmp(argv[i + 2], "/dev/input/event", 16)) goto close_inputs;
        fds[i].fd = open(argv[i + 2], O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (fds[i].fd < 0 || ioctl(fds[i].fd, EVIOCGID, &identity)) goto close_inputs;
    }
    token = open("/tmp/joy_key", O_WRONLY | O_CREAT | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (token < 0) goto close_inputs;
    close(token);
    key = ftok("/tmp/joy_key", 'a');
    if (key == (key_t)-1) goto close_inputs;
    /* Never steal or overwrite an existing cubevol/other publisher segment. */
    id = shmget(key, sizeof(uint32_t), IPC_CREAT | IPC_EXCL | 0600);
    if (id < 0) goto close_inputs;
    shared = shmat(id, NULL, 0);
    if (shared == (void *)-1) { shmctl(id, IPC_RMID, NULL); goto close_inputs; }
    *shared = 0;
    /* A key may already be held when the service starts. Restore each source
     * from EVIOCGKEY instead of waiting for a new press event that never comes. */
    for (i = 0; i < count; i++) {
        unsigned char keys[(R36_KEY_LIMIT + 7) / 8] = {0};
        unsigned int code;
        if (ioctl(fds[i].fd, EVIOCGKEY(sizeof(keys)), keys) < 0) { stopped = 1; break; }
        for (code = 0; code < R36_KEY_LIMIT; code++)
            if (keys[code / 8] & (1u << (code % 8))) r36_key_event(&state, i, code, 1);
    }
    if (!stopped) *shared = r36_key_word(&state);
    __sync_synchronize();
    signal(SIGINT, stop); signal(SIGTERM, stop);
#ifdef R36_KEYS_DIAGNOSTIC
    dprintf(1, "keys_diagnostic_ready=%d\n", !stopped);
    unsigned int diagnostic_records = 0;
#endif
    while (!stopped) {
        int rc = poll(fds, count, 100);
        if (rc < 0 && errno == EINTR) continue;
        if (rc < 0) break;
        for (i = 0; i < count; i++) {
            struct input_event events[32];
            ssize_t bytes;
            if (fds[i].revents & (POLLERR | POLLHUP | POLLNVAL)) { stopped = 1; break; }
            if (!(fds[i].revents & POLLIN)) continue;
            while ((bytes = read(fds[i].fd, events, sizeof(events))) > 0) {
                unsigned int n;
                if (bytes % sizeof(events[0])) { stopped = 1; break; }
                for (n = 0; n < (unsigned int)bytes / sizeof(events[0]); n++) {
                    if (events[n].type == EV_SYN && events[n].code == SYN_DROPPED) {
                        /* A lost event may leave a stuck button. Fail closed;
                         * a supervisor can restart after querying EVIOCGKEY. */
                        stopped = 1; break;
                    }
                    if (events[n].type == EV_KEY && r36_key_event(&state, i, events[n].code, events[n].value)) {
                        stopped = 1; break;
                    }
                }
                if (stopped) break;
            }
            if (bytes == 0 || (bytes < 0 && errno != EAGAIN && errno != EINTR)) stopped = 1;
        }
#ifdef R36_KEYS_DIAGNOSTIC
        uint32_t before = *shared;
#endif
        *shared = stopped ? 0 : r36_key_word(&state);
        __sync_synchronize();
#ifdef R36_KEYS_DIAGNOSTIC
        if (*shared != before && diagnostic_records++ < 128)
            dprintf(1, "keys_word=%08x\n", (unsigned)*shared);
#endif
    }
    *shared = 0;
    __sync_synchronize();
#ifdef R36_KEYS_DIAGNOSTIC
    dprintf(1, "keys_diagnostic_end requested_stop=%d final_word=%08x\n", (int)requested_stop, (unsigned)*shared);
#endif
    shmdt((const void *)shared);
    shmctl(id, IPC_RMID, NULL);
    result = requested_stop ? 0 : 1;
close_inputs:
    for (i = 0; i < count; i++) if (fds[i].fd >= 0) close(fds[i].fd);
    close(lock);
    return result;
}
