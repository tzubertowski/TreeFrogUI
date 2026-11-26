/* SPDX-License-Identifier: MIT */
#ifndef R36_CORE_CONSOLE_PROBE_H
#define R36_CORE_CONSOLE_PROBE_H
#include <signal.h>
#include <sys/wait.h>

static int console_core_probe(void)
{
    static const char *const cores[] = {"gambatte", "fceumm"};
    static const char *const roms[] = {"/sd/cubegm/r36-synthetic-input.gb", "/sd/cubegm/r36-synthetic-input.nes"};
    unsigned int i;
    puts("R36 CORE CONSOLE PROBE V1");
    if (mkdir("/tmp", 01777) && errno != EEXIST) return -1;
    for (i = 0; i < 2; i++) {
        char core[128], work[64];
        int status = 0, complete = 0;
        pid_t child, got;
        snprintf(core, sizeof(core), "/sd/cubegm/cores/%s_libretro.so", cores[i]);
        snprintf(work, sizeof(work), "/tmp/r36-core-%s", cores[i]);
        if (mkdir(work, 0700)) return -1;
        printf("core_begin=%s\n", cores[i]); fflush(stdout);
        child = fork();
        if (child < 0) return -1;
        if (!child) {
            if (chdir(work)) _exit(126);
            /* Execute the actual SD loader, not a replacement runtime. No
             * stock init, module loader, device backend or real ROM is run. */
            execl("/sd/rootfs/lib/ld.so.1", "ld.so.1", "--library-path",
                  "/sd/cubegm/lib:/sd/rootfs/lib:/sd/rootfs/usr/lib",
                  "/sd/cubegm/r36-libretro-smoke-console", core, roms[i], (char *)NULL);
            _exit(127);
        }
        for (unsigned int tick = 0; tick < 80; tick++) {
            got = waitpid(child, &status, WNOHANG);
            if (got == child) { complete = 1; break; }
            if (got < 0 && errno != EINTR) break;
            usleep(100000);
        }
        if (!complete) {
            /* Test child only writes its RAM cwd and diagnostic stdout; no
             * fsck or save writer is allowed in this harness. */
            kill(child, SIGKILL);
            do { got = waitpid(child, &status, 0); } while (got < 0 && errno == EINTR);
            printf("core_timeout=%s\n", cores[i]);
            return -1;
        }
        printf("core_end=%s exit=%d signalled=%d\n", cores[i], WIFEXITED(status) ? WEXITSTATUS(status) : -1, !WIFEXITED(status));
        if (!WIFEXITED(status) || WEXITSTATUS(status)) return -1;
    }
    puts("console_core_execution=PASS\nphysical_video_audio_input=NOT_TESTED\nR36 CORE CONSOLE PROBE END");
    return 0;
}
#endif
