#ifndef R36_USER_TRACE_H
#define R36_USER_TRACE_H
#include <fcntl.h>
#include <stdint.h>
#include <sys/mman.h>
#include <unistd.h>
#include "ports/r36-trace.h"

static void mark_userspace(void)
{
    int fd;
    volatile uint32_t *trace;
    if (getpid() != 1) return;
    fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) return;
    trace = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, R36_TRACE_PHYS);
    if (trace != MAP_FAILED) {
        if (trace[0] == R36_TRACE_MAGIC && trace[3] == R36_TRACE_VERSION) {
            trace[4] = R36_STAGE_USERSPACE;
            __sync_synchronize();
        }
        munmap((void *)trace, 4096);
    }
    close(fd);
}
#endif
