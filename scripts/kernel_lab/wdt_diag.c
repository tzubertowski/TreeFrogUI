#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include "ports/r36-trace.h"

static uint64_t ns(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000000ULL + t.tv_nsec;
}

int main(int argc, char **argv)
{
    int fd;
    volatile uint32_t *sys, *wdt, *trace;
    uint32_t gate, old_count, old_control, first, last;
    uint64_t begin, elapsed, rate, ticks, seconds;
    int sample = argc == 2 && !strcmp(argv[1], "--sample");
    int arm = argc == 4 && !strcmp(argv[1], "--arm");
    if (argc != 1 && !sample && !arm) {
        fprintf(stderr, "usage: r36-wdt-diag [--sample | --arm measured_hz seconds]\n");
        return 2;
    }
    fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) { perror("/dev/mem"); return 1; }
    sys = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0x18800000);
    wdt = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0x18818000);
    if (sys == MAP_FAILED || wdt == MAP_FAILED) { perror("mmap"); return 1; }
    gate = sys[0x60 / 4];
    old_count = wdt[0x500 / 4];
    old_control = wdt[0x504 / 4];
    printf("gate0=%08" PRIx32 " counter=%08" PRIx32 " control=%08" PRIx32 "\n",
           gate, old_count, old_control);
    trace = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, R36_TRACE_PHYS);
    if (trace != MAP_FAILED)
        printf("trace_magic=%08" PRIx32 " trace_version=%" PRIu32 " trace_stage=%" PRIu32
               " trace_tag=%08" PRIx32 "\n", trace[0], trace[3], trace[4], trace[10]);
    if (!sample && !arm) return 0;
    if (old_control & 4) {
        fprintf(stderr, "watchdog already running; leaving it unchanged\n");
        return 1;
    }
    rate = ticks = seconds = 0;
    if (arm) {
        char *end1, *end2;
        errno = 0;
        rate = strtoull(argv[2], &end1, 0);
        seconds = strtoull(argv[3], &end2, 0);
        if (errno || argv[2][0] == '-' || argv[3][0] == '-' || *end1 || *end2 ||
            !rate || !seconds || rate > 1000000000ULL || seconds > 600 || rate > UINT32_MAX / seconds) {
            fprintf(stderr, "requested delay does not fit watchdog counter\n");
            return 2;
        }
        ticks = rate * seconds;
    }
    sync();
    sys[0x60 / 4] = gate & ~(1U << 22);
    __sync_synchronize();
    wdt[0x500 / 4] = arm ? (uint32_t)(0ULL - ticks) : 0;
    wdt[0x504 / 4] = 0x26;
    __sync_synchronize();
    if (arm) {
        if (trace != MAP_FAILED) {
            unsigned int i;
            for (i = 0; i < R36_TRACE_HEADER / 4; i++) trace[i] = 0;
            trace[0] = R36_TRACE_MAGIC;
            trace[2] = R36_TRACE_CAPACITY;
            trace[3] = R36_TRACE_VERSION;
            trace[4] = R36_STAGE_STOCK_WDT;
            trace[8] = rate;
            trace[9] = seconds;
            trace[10] = (uint32_t)ns();
            __sync_synchronize();
            printf("armed_trace_tag=%08" PRIx32 "\n", trace[10]);
        }
        printf("armed_hz=%" PRIu64 " ticks=%" PRIu64 "\n", rate, ticks);
        return 0;
    }
    first = wdt[0x500 / 4];
    begin = ns();
    usleep(20000);
    last = wdt[0x500 / 4];
    elapsed = ns() - begin;
    wdt[0x504 / 4] = 0;
    __sync_synchronize();
    wdt[0x500 / 4] = old_count;
    wdt[0x504 / 4] = old_control;
    sys[0x60 / 4] = (sys[0x60 / 4] & ~(1U << 22)) | (gate & (1U << 22));
    __sync_synchronize();
    rate = elapsed ? (uint64_t)(uint32_t)(last - first) * 1000000000ULL / elapsed : 0;
    printf("sample_first=%" PRIu32 " sample_last=%" PRIu32 " elapsed_ns=%" PRIu64
           " measured_hz=%" PRIu64 " restored=1\n", first, last, elapsed, rate);
    return rate ? 0 : 1;
}
