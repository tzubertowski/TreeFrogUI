/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

/* Bounded integration harness for unchanged frontend ABI. Not installed as UI.
 * Real DRM/backend test only; no sound or key injection, no fake success.
 */
int main(int argc, char **argv)
{
    void *library;
    int (*initialize)(void), (*display)(void *, int, int, int);
    void (*deinitialize)(void);
    uint16_t *frame;
    unsigned int x, y, n;
    if (argc != 2) return 2;
    library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) { fprintf(stderr, "%s\n", dlerror()); return 1; }
    initialize = (int (*)(void))dlsym(library, "video_drivers_init");
    display = (int (*)(void *, int, int, int))dlsym(library, "video_driver_disp_frame");
    deinitialize = (void (*)(void))dlsym(library, "video_driver_deinit");
    if (!initialize || !display || !deinitialize) { dlclose(library); return 1; }
    if (initialize() <= 0) { dlclose(library); return 1; }
    frame = malloc(320 * 240 * sizeof(*frame));
    if (!frame) { deinitialize(); dlclose(library); return 1; }
    for (n = 0; n < 60; n++) {
        for (y = 0; y < 240; y++)
            for (x = 0; x < 320; x++)
                frame[y * 320 + x] = (uint16_t)(((x + n) & 31) << 11 | (y & 63) << 5 | ((x / 10) & 31));
        if (display(frame, 320, 240, 640) < 0) {
            free(frame); deinitialize(); dlclose(library); return 1;
        }
    }
    free(frame); deinitialize(); dlclose(library);
    puts("FRONTEND_ABI_DRM_HARNESS=PASS\nfull_ui_or_game_verified=0");
    return 0;
}
