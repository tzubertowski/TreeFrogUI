/*
 * nosleep - live-patch the running cubevol to disable sleep.
 *
 * SF3500 verifies cubevol on disk at boot (hash/signature), so a byte-patched
 * file shows "sdcard is damaged". Instead we leave the on-disk binary pristine
 * (passes verification, loads, runs) and NOP the two sleep-arm instructions in
 * the LIVE process image via ptrace. cubevol is ET_EXEC (non-PIE), so link
 * address == runtime address - the caller passes absolute text addresses.
 *
 * cubevol is respawned during a session (FrogUI restarts it for the battery/
 * volume OSD), which re-arms sleep, so this runs as a persistent WATCHER:
 * launched once by zhijack, it re-patches whenever a fresh cubevol appears.
 *
 * Usage:
 *   nosleep -w <hexaddr> [<hexaddr> ...]   watch: patch every new cubevol pid
 *   nosleep <pid> <hexaddr> [...]          one-shot: patch a specific pid
 *
 * Each address is overwritten with a MIPS NOP (0x00000000). Runs as root.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <sys/types.h>

static int patch_pid(pid_t pid, int naddr, char **addrs)
{
    if (ptrace(PTRACE_ATTACH, pid, 0, 0) < 0) { perror("nosleep: attach"); return -1; }
    int status;
    if (waitpid(pid, &status, 0) < 0) { ptrace(PTRACE_DETACH, pid, 0, 0); return -1; }

    int patched = 0;
    for (int i = 0; i < naddr; i++) {
        char *end = NULL;
        unsigned long addr = strtoul(addrs[i], &end, 0);
        unsigned long expected = 0;
        int validate = end && *end == ':';
        if (validate) expected = strtoul(end + 1, NULL, 0);

        /* cubevol differs between otherwise compatible device/firmware builds.
         * Never NOP a borrowed absolute address unless the instruction there is
         * exactly the one we reverse-engineered. A mismatch is a harmless
         * unsupported variant, not permission to corrupt unrelated code. */
        if (validate) {
            errno = 0;
            unsigned long original = (unsigned long)ptrace(
                PTRACE_PEEKTEXT, pid, (void *)addr, 0);
            if (errno || (original & 0xfffffffful) != expected) continue;
        }
        /* POKETEXT writes one word (4 bytes on MIPS32); NOP = 0x00000000 */
        if (ptrace(PTRACE_POKETEXT, pid, (void *)addr, (void *)0) < 0) {
            fprintf(stderr, "nosleep: POKETEXT @0x%lx failed\n", addr);
        } else {
            printf("nosleep: NOP @0x%lx (pid %d)\n", addr, (int)pid);
            patched++;
        }
    }
    ptrace(PTRACE_DETACH, pid, 0, 0);
    fflush(stdout);
    /* 0 = patched, 1 = valid process but unsupported cubevol build, -1 = the
     * attach/write itself failed. Watch mode must remember both 0 and 1 so an
     * unknown firmware is not ptrace-paused again every two seconds. */
    return patched > 0 ? 0 : 1;
}

/* Collect all pids whose comm == name (/proc/<pid>/comm). Returns count. */
static int find_pids(const char *name, pid_t *out, int max)
{
    DIR *d = opendir("/proc");
    if (!d) return 0;
    struct dirent *e;
    int n = 0;
    while ((e = readdir(d)) && n < max) {
        if (e->d_name[0] < '0' || e->d_name[0] > '9') continue;
        char path[64], comm[64];
        snprintf(path, sizeof(path), "/proc/%s/comm", e->d_name);
        FILE *f = fopen(path, "r");
        if (!f) continue;
        if (fgets(comm, sizeof(comm), f)) {
            comm[strcspn(comm, "\n")] = 0;
            if (strcmp(comm, name) == 0) out[n++] = (pid_t)atoi(e->d_name);
        }
        fclose(f);
    }
    closedir(d);
    return n;
}

int main(int argc, char **argv)
{
    if (argc >= 3 && strcmp(argv[1], "-w") == 0) {
        /* watch mode: patch EVERY cubevol instance (there are two on these
         * devices), and any respawn, forever. Track already-patched pids so we
         * don't re-ptrace (and briefly pause) a process every cycle. Text pages
         * are shared+COW, so each process must be poked individually. */
        #define MAXPIDS 16
        pid_t patched[MAXPIDS]; int npatched = 0;
        for (;;) {
            pid_t pids[MAXPIDS];
            int n = find_pids("cubevol", pids, MAXPIDS);
            /* forget patched pids that no longer exist (pid may be reused) */
            for (int i = 0; i < npatched; ) {
                int alive = 0;
                for (int j = 0; j < n; j++) if (pids[j] == patched[i]) { alive = 1; break; }
                if (!alive) patched[i] = patched[--npatched]; else i++;
            }
            for (int j = 0; j < n; j++) {
                int seen = 0;
                for (int i = 0; i < npatched; i++) if (patched[i] == pids[j]) { seen = 1; break; }
                if (!seen) {
                    int rc = patch_pid(pids[j], argc - 2, &argv[2]);
                    if (rc >= 0 && npatched < MAXPIDS)
                        patched[npatched++] = pids[j];
                }
            }
            sleep(2);
        }
        return 0;   /* unreachable */
    }

    if (argc >= 3) {
        pid_t pid = (pid_t)strtol(argv[1], NULL, 0);
        if (pid <= 0) { fprintf(stderr, "nosleep: bad pid\n"); return 2; }
        return patch_pid(pid, argc - 2, &argv[2]) == 0 ? 0 : 1;
    }

    fprintf(stderr, "usage: %s -w <addr[:expected-word]>...   |   %s <pid> <addr[:expected-word]>...\n", argv[0], argv[0]);
    return 2;
}
