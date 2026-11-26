/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

#ifdef R36_UI_STATE_TRACE
#include "ui_state_trace.h"
#endif

/* Child-only observation of standard libretro calls, no binary patch, no fake
 * frames or return values. Never changes the input callback or core state.
 * dlsym resolution is versioned for measured MIPS glibc libdl, avoiding recursion.
 */
typedef void (*video_callback)(const void *, unsigned int, unsigned int, size_t);
static void *(*next_dlsym)(void *, const char *);
static void (*core_run)(void);
static void (*core_set_video)(video_callback);
static video_callback frontend_video;
static unsigned int runs, videos;
static int traced_handle_ready;
static void *traced_handle;

#ifdef R36_UI_LIVE_CHECKPOINT
#include "ui_live_checkpoint.h"
#endif

static void observe_video(const void *data, unsigned int w, unsigned int h, size_t pitch)
{
    unsigned int count = ++videos;
    if (count <= 2 || count % 60 == 0) {
        uint32_t hash = 2166136261u;
        unsigned int nonzero = 0;
        /* This UI diagnostic accepts only the actual observed RGB565 geometry.
         * For any other callback format forward untouched without inspecting. */
        if (data && data != (void *)-1 && w == 640 && h == 480 && pitch == 1280) {
            const unsigned char *bytes = data;
            for (size_t i = 0; i < pitch * h; i++) {
                hash = (hash ^ bytes[i]) * 16777619u;
                nonzero += bytes[i] != 0;
            }
            dprintf(2, "ui-core: video=%u RGB565_hash=%08x nonzero_bytes=%u\n", count, hash, nonzero);
        } else dprintf(2, "ui-core: video=%u geometry=%ux%u pitch=%lu inspected=0\n", count, w, h, (unsigned long)pitch);
    }
    if (frontend_video) frontend_video(data, w, h, pitch);
#ifdef R36_UI_LIVE_CHECKPOINT
    checkpoint_begin();
#endif
}
static void observe_run(void)
{
    unsigned int count = ++runs;
    if (count <= 2 || count % 60 == 0)
        dprintf(2, "ui-core: run_enter=%u videos=%u\n", count, videos);
#ifdef R36_UI_STATE_TRACE
    state_sample(count, "enter");
#endif
    core_run();
#ifdef R36_UI_LIVE_CHECKPOINT
    checkpoint_poll(count);
#endif
#ifdef R36_UI_STATE_TRACE
    state_sample(count, "leave");
#endif
    if (count <= 2 || count % 60 == 0)
        dprintf(2, "ui-core: run_leave=%u videos=%u\n", count, videos);
}
static void observe_set_video(video_callback callback)
{
    frontend_video = callback;
    core_set_video(callback ? observe_video : NULL);
    dprintf(2, "ui-core: video_callback_installed=%u\n", callback != NULL);
}
void *dlsym(void *handle, const char *name)
{
    void *symbol;
    if (!next_dlsym) {
        *(void **)(&next_dlsym) = dlvsym(RTLD_NEXT, "dlsym", "GLIBC_2.0");
        if (!next_dlsym) {
            /* A missing resolver cannot be represented as a successful symbol. */
            const char text[] = "ui-core: cannot resolve original dlsym\n";
            syscall(SYS_write, 2, text, sizeof(text) - 1);
            return NULL;
        }
    }
    symbol = next_dlsym(handle, name);
    if (!symbol) return NULL;
    if (!strcmp(name, "retro_run") || !strcmp(name, "retro_set_video_refresh")) {
        Dl_info info;
        /* Ignore unrelated libraries or RTLD_DEFAULT requests. Bind to a single
         * actual FrogUI object; observers are not substitutes for other cores. */
        if (!dladdr(symbol, &info) || !info.dli_fname ||
            !strstr(info.dli_fname, "/frogui_libretro.so")) return symbol;
        if (traced_handle_ready && handle != traced_handle) return symbol;
        traced_handle = handle; traced_handle_ready = 1;
        if (!strcmp(name, "retro_run")) {
            *(void **)(&core_run) = symbol;
#ifdef R36_UI_STATE_TRACE
            state_bind(symbol, &info);
#endif
            return (void *)observe_run;
        }
        *(void **)(&core_set_video) = symbol;
        return (void *)observe_set_video;
    }
    return symbol;
}
