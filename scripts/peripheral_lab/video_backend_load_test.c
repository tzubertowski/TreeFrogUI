/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    void *library;
    int (*initialize)(void);
    void (*deinitialize)(void);
    if (argc != 2) return 2;
    /* Explicit missing device: this test must not touch real DRM. */
    if (setenv("R36_DRM_DEVICE", "/no-such-device/r36-test", 1)) return 2;
    library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) { fprintf(stderr, "%s\n", dlerror()); return 1; }
    initialize = (int (*)(void))dlsym(library, "video_drivers_init");
    deinitialize = (void (*)(void))dlsym(library, "video_driver_deinit");
    if (!initialize || !deinitialize || !dlsym(library, "video_driver_disp_frame")) return 1;
    if (dlsym(library, "g_render") || dlsym(library, "sound_driver_playframe")) return 1;
    if (initialize() >= 0) { fputs("unexpected dummy-success\n", stderr); return 1; }
    deinitialize();
    dlclose(library);
    puts("MIPS_GLIBC_BACKEND_LOAD_AND_FAIL_CLOSED=PASS");
    return 0;
}
