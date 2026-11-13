// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Pavel Kotek
/*
 * tfkey - read / inject R36S (TreeFrogUI, cubevol) button state.
 *
 * Games and FrogUI read a 32-bit button word from SysV shared memory
 * ftok("/tmp/joy_key",'a'), written by the stock cubevol daemon.
 *
 *   tfkey get                       print the raw word
 *   tfkey probe                     measure how cubevol rewrites the word
 *   tfkey press A [B ...] [-t ms]   hold buttons for ms (default 120), then release
 *   tfkey hold  A [B ...] -t ms     same, long hold
 *   tfkey seq "A 100, 200, START 120"   press/wait sequence (BTN ms | wait ms)
 * Names: UP DOWN LEFT RIGHT A B X Y L1 R1 START SELECT or bit numbers 0-31.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <strings.h>
#include <time.h>
#include <unistd.h>
#include <sys/ipc.h>
#include <sys/shm.h>

static volatile uint32_t *g_keys;

static struct { const char *n; int bit; } g_names[] = {
    {"SELECT", 0}, {"START", 3}, {"UP", 4}, {"RIGHT", 5}, {"DOWN", 6}, {"LEFT", 7},
    {"L1", 10}, {"R1", 11}, {"X", 12}, {"A", 13}, {"B", 14}, {"Y", 15}, {"L", 10}, {"R", 11},
};

static double now_ms(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1e3 + t.tv_nsec / 1e6; }

static int bit_of(const char *s) {
    for (size_t i = 0; i < sizeof g_names / sizeof g_names[0]; i++) if (!strcasecmp(s, g_names[i].n)) return g_names[i].bit;
    char *e; long v = strtol(s, &e, 10);
    return (*s && !*e && v >= 0 && v < 32) ? (int)v : -1;
}

static void load_keymap(void) {          /* honour a user-remapped FrogUI keymap */
    FILE *f = fopen("/mnt/sdcard/frogui/keymap.txt", "r");
    char line[64], name[16]; int v;
    if (!f) return;
    while (fgets(line, sizeof line, f))
        if (sscanf(line, "%15[^=]=%d", name, &v) == 2 && v >= 0 && v < 32)
            for (size_t i = 0; i < sizeof g_names / sizeof g_names[0]; i++)
                if (!strcasecmp(name, g_names[i].n)) g_names[i].bit = v;
    fclose(f);
}

/* hold `mask` for ms: re-assert every 1 ms so a cubevol rewrite never wins for long */
static void hold(uint32_t mask, double ms) {
    double end = now_ms() + ms;
    while (now_ms() < end) { *g_keys |= mask; usleep(200); }
    *g_keys &= ~mask;
}

static int probe(void) {
    const uint32_t M = 1u << 31;
    int n = 20; double sum = 0, mx = 0, mn = 1e9; int never = 0;
    printf("raw=0x%08x\n", *g_keys);
    for (int i = 0; i < n; i++) {
        *g_keys |= M;
        double t0 = now_ms(), t;
        while ((*g_keys & M) && (t = now_ms()) - t0 < 1000) ;
        t = now_ms() - t0;
        if (*g_keys & M) { never++; *g_keys &= ~M; }
        else { sum += t; if (t > mx) mx = t; if (t < mn) mn = t; }
        usleep(37000);
    }
    if (never == n) printf("marker bit never cleared within 1 s: cubevol writes only on change\n");
    else printf("marker cleared in %d/%d tries: min %.2f ms avg %.2f ms max %.2f ms (cubevol rewrite period)\n",
                n - never, n, mn, sum / (n - never), mx);
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: tfkey get|probe|press BTN.. [-t ms]|seq \"BTN ms, ms, ...\"\n"); return 2; }
    key_t k = ftok("/tmp/joy_key", 'a');
    int id = k == (key_t)-1 ? -1 : shmget(k, 4, 0666);
    if (id < 0) { fprintf(stderr, "tfkey: joy_key shared memory not found (cubevol not running?)\n"); return 3; }
    g_keys = shmat(id, NULL, 0);
    if (g_keys == (void *)-1) { perror("shmat"); return 3; }
    load_keymap();
    if (!strcmp(argv[1], "get")) { printf("0x%08x\n", *g_keys); return 0; }
    if (!strcmp(argv[1], "probe")) return probe();
    if (!strcmp(argv[1], "press") || !strcmp(argv[1], "hold")) {
        uint32_t mask = 0; double ms = 120;
        for (int i = 2; i < argc; i++) {
            if (!strcmp(argv[i], "-t") && i + 1 < argc) { ms = atof(argv[++i]); continue; }
            int b = bit_of(argv[i]);
            if (b < 0) { fprintf(stderr, "tfkey: unknown button %s\n", argv[i]); return 2; }
            mask |= 1u << b;
        }
        if (!mask) return 2;
        hold(mask, ms);
        return 0;
    }
    if (!strcmp(argv[1], "seq") && argc > 2) {
        char *s = strdup(argv[2]), *tok, *save;
        for (tok = strtok_r(s, ",", &save); tok; tok = strtok_r(NULL, ",", &save)) {
            char a[16] = "", b[16] = ""; uint32_t mask = 0; double ms = 120;
            int n = sscanf(tok, "%15s %15s", a, b);
            if (n >= 1 && bit_of(a) < 0) { ms = atof(a); usleep((useconds_t)(ms * 1000)); continue; }   /* plain wait */
            /* "A+B 100" */
            char *p, *sv; for (p = strtok_r(a, "+", &sv); p; p = strtok_r(NULL, "+", &sv)) { int bt = bit_of(p); if (bt < 0) { fprintf(stderr, "bad %s\n", p); return 2; } mask |= 1u << bt; }
            if (n == 2) ms = atof(b);
            hold(mask, ms);
            usleep(60000);           /* gap so readers see a release between presses */
        }
        return 0;
    }
    fprintf(stderr, "tfkey: unknown command\n");
    return 2;
}
