/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Pavel Kotek
 *
 * tfrec - capture recorder for tfshim.so. Creates the tfcap shared memory
 * segment (tmpfs, never the SD card), enables capture and streams video
 * frames + audio chunks to stdout in the tfrec packet format (tfcap.h)
 * until killed (SIGTERM/SIGINT/SIGHUP/SIGPIPE) or --seconds elapse.
 *
 *   tfrec [--fps N] [--scale 1|2] [--no-audio] [--no-video] [--seconds N]
 *         [--keyint S] [--nice N] [--path FILE] [--info S]
 *
 * stdout carries only the binary stream (diagnostics travel in-band as
 * TFS_INFO packets), because tfmtp merges stderr into the same pipe.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#include "tfcap.h"
#include "tfrec_core.h"

#define POLL_MS 5

static volatile sig_atomic_t g_stop;
static void on_signal(int sig) { (void)sig; g_stop = 1; }

static uint64_t mono_us(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000u + (uint64_t)t.tv_nsec / 1000u;
}

static void usage(void)
{
    static const char u[] =
        "usage: tfrec [--fps N] [--scale 1|2] [--no-audio] [--no-video] [--seconds N]\n"
        "             [--keyint S] [--nice N] [--path FILE] [--info S]\n"
        "Streams tfshim captures to stdout (binary). Defaults: --fps 30 --scale 1\n"
        "--keyint 10 --nice 10 --path " TFCAP_PATH " --info 2\n";
    if (write(2, u, sizeof u - 1) < 0) { /* nothing to do */ }
}

/* A recorder that is still running would keep the shim attached to its
 * segment: ask it to stop (SIGTERM) and wait up to 2 s. */
static void stop_previous(const char *path)
{
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return;
    struct tfcap_hdr old;
    ssize_t n = read(fd, &old, sizeof old);
    close(fd);
    if (n != (ssize_t)sizeof old || old.magic != TFCAP_MAGIC || old.state != TFCAP_STATE_RUNNING) return;
    pid_t pid = (pid_t)old.rec_pid;
    if (pid <= 1 || pid == getpid() || kill(pid, 0) != 0) return;
    kill(pid, SIGTERM);
    for (int i = 0; i < 40 && kill(pid, 0) == 0; i++) {
        struct timespec ts = { 0, 50000000 };
        nanosleep(&ts, NULL);
    }
}

/* write as much as possible; returns -1 on a fatal error (EPIPE...) */
static int flush_out(struct tfrec *r)
{
    while (tfrec_pending(r)) {
        ssize_t n = write(1, tfrec_out(r), tfrec_pending(r));
        if (n > 0) { tfrec_consumed(r, (size_t)n); continue; }
        if (n < 0 && errno == EINTR) continue;
        if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) return 0;
        return -1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    struct tfrec_opts o = { .fps = 30, .scale = 1, .video = 1, .audio = 1, .keyint_s = 10 };
    int seconds = 0, nice_v = 10, info_s = 2;
    const char *path = TFCAP_PATH;

    for (int i = 1; i < argc; i++) {
        const char *a = argv[i], *v = i + 1 < argc ? argv[i + 1] : NULL;
        if (!strcmp(a, "--no-audio")) o.audio = 0;
        else if (!strcmp(a, "--no-video")) o.video = 0;
        else if (!strcmp(a, "--fps") && v) { o.fps = atoi(v); i++; }
        else if (!strcmp(a, "--scale") && v) { o.scale = atoi(v); i++; }
        else if (!strcmp(a, "--seconds") && v) { seconds = atoi(v); i++; }
        else if (!strcmp(a, "--keyint") && v) { o.keyint_s = atoi(v); i++; }
        else if (!strcmp(a, "--nice") && v) { nice_v = atoi(v); i++; }
        else if (!strcmp(a, "--info") && v) { info_s = atoi(v); i++; }
        else if (!strcmp(a, "--path") && v) { path = v; i++; }
        else { usage(); return 2; }
    }
    if (o.fps < 0 || o.fps > 120 || (o.scale != 1 && o.scale != 2)) { usage(); return 2; }

    if (nice_v) setpriority(PRIO_PROCESS, 0, nice_v);

    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = on_signal;               /* no SA_RESTART: poll() returns EINTR */
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGHUP, &sa, NULL);
    sigaction(SIGPIPE, &sa, NULL);

    uint32_t size = tfcap_layout_size();
    stop_previous(path);
    unlink(path);                            /* stale segment of a killed recorder */
    int fd = open(path, O_RDWR | O_CREAT | O_EXCL | O_CLOEXEC, 0666);
    if (fd < 0) { fprintf(stderr, "tfrec: create %s: %s\n", path, strerror(errno)); return 1; }
    fchmod(fd, 0666);
    if (ftruncate(fd, size) != 0) {
        fprintf(stderr, "tfrec: ftruncate: %s\n", strerror(errno));
        close(fd); unlink(path); return 1;
    }
    void *m = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);
    if (m == MAP_FAILED) { fprintf(stderr, "tfrec: mmap: %s\n", strerror(errno)); unlink(path); return 1; }
    struct tfcap_hdr *h = m;
    tfcap_layout_init(h);
    h->rec_pid = (uint32_t)getpid();

    static struct tfrec r;
    if (tfrec_init(&r, h, &o) != 0) {
        fprintf(stderr, "tfrec: out of memory\n");
        munmap(m, size); unlink(path); return 1;
    }
    fcntl(1, F_SETFL, fcntl(1, F_GETFL) | O_NONBLOCK);

    uint64_t t0 = mono_us(), next_info = t0 + (uint64_t)info_s * 1000000u;
    char extra[160];
    snprintf(extra, sizeof extra, "event=start version=1 fps=%d scale=%d video=%d audio=%d keyint=%d shm=%s shm_bytes=%u",
             o.fps, o.scale, o.video, o.audio, o.keyint_s, path, size);
    tfrec_stream_header(&r);
    tfrec_info(&r, TFS_INFO, t0, extra);
    tfcap_publish(h, (o.video ? TFCAP_EN_VIDEO : 0u) | (o.audio ? TFCAP_EN_AUDIO : 0u),
                  o.fps > 0 ? 1000000u / (uint32_t)o.fps : 0u);

    int broken = 0;
    while (!g_stop) {
        uint64_t now = mono_us();
        if (seconds > 0 && now - t0 >= (uint64_t)seconds * 1000000u) break;
        h->heartbeat++;
        tfrec_poll(&r, now);
        if (info_s > 0 && now >= next_info) {
            tfrec_info(&r, TFS_INFO, now, h->shim_attaches ? NULL : "waiting=shim");
            next_info = now + (uint64_t)info_s * 1000000u;
        }
        if (flush_out(&r) < 0) { broken = 1; break; }
        struct pollfd pf = { 1, POLLOUT, 0 };
        poll(&pf, tfrec_pending(&r) ? 1 : 0, POLL_MS);
    }

    /* stop the shim first, then drain */
    h->enabled = 0;
    TFCAP_MB();
    h->state = TFCAP_STATE_CLOSED;
    TFCAP_MB();
    if (!broken) {
        tfrec_poll(&r, mono_us());
        tfrec_info(&r, TFS_END, mono_us(), g_stop ? "event=end reason=signal" : "event=end reason=time");
        uint64_t deadline = mono_us() + 3000000u;
        while (tfrec_pending(&r) && mono_us() < deadline) {
            if (flush_out(&r) < 0) break;
            struct pollfd pf = { 1, POLLOUT, 0 };
            if (tfrec_pending(&r)) poll(&pf, 1, 50);
        }
    }
    munmap(m, size);
    unlink(path);
    tfrec_free(&r);
    return 0;
}
