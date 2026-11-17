/* SPDX-License-Identifier: MIT */
#ifndef R36_UI_LIVE_CHECKPOINT_H
#define R36_UI_LIVE_CHECKPOINT_H
#include <stdlib.h>
#include <time.h>
static struct timespec checkpoint_start;
static int checkpoint_started, checkpoint_attempted;

static void checkpoint_begin(void)
{
    if (!checkpoint_started && !clock_gettime(CLOCK_MONOTONIC, &checkpoint_start))
        checkpoint_started = 1;
}
/* Run on the existing frontend thread after a real core call. No extra video,
 * input, sleep, worker or signal handler; resolve only an already loaded driver. */
static void checkpoint_poll(unsigned int count)
{
    struct timespec now;
    void *library;
    void (*observe)(void);
    const char *path;
    long long elapsed;
    if (!checkpoint_started || checkpoint_attempted || count % 60) return;
    if (clock_gettime(CLOCK_MONOTONIC, &now)) return;
    elapsed = ((long long)now.tv_sec - checkpoint_start.tv_sec) * 1000000000LL +
              now.tv_nsec - checkpoint_start.tv_nsec;
    if (elapsed < 10000000000LL) return;
    checkpoint_attempted = 1;
    path = getenv("PICOARCH_DRIVER");
    if (!path || !*path) goto fail;
    library = dlopen(path, RTLD_NOW | RTLD_NOLOAD | RTLD_LOCAL);
    if (!library) goto fail;
    *(void **)(&observe) = next_dlsym(library, "r36_scanout_live_checkpoint");
    if (!observe) { dlclose(library); goto fail; }
    dprintf(2, "ui-live: checkpoint_elapsed_ms=%lld run=%u\n", elapsed / 1000000LL, count);
    observe();
    dlclose(library);
    return;
fail:
    dprintf(2, "ui-live: checkpoint_unavailable=1\n");
}
#endif
