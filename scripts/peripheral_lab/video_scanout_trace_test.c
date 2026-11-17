/* SPDX-License-Identifier: MIT
 * Real observation code with synthetic health and DMA memory; no devices. */
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <assert.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
static unsigned char cpu[1344 * 480], dma[(1344 * 480 + 4095) & ~4095u];
static void *pixels = cpu;
static unsigned stride = 1344;
static int active = 1, corrupt, bad_health, fail_memory, reads, readonly_maps;
static int fake_open(const char *path, int flags) {
    assert(!(flags & O_RDWR) && !(flags & O_WRONLY));
    if (!strcmp(path,"/dev/mem")) return fail_memory ? -1 : 12;
    assert(strstr(path,"/health"));return 11;
}
static ssize_t fake_read(int fd,void *out,size_t length) {
    int n;
    assert(fd==11);reads++;
    n=snprintf(out,length,"boot_descriptor=02f92a80 active_descriptor=02f90400 programmed_descriptor=%08x line=%u flip_timeouts=0 timing_stable=1 active_on=1 pixel=01500000 format=6 width=640 height=480 pitch=1344\n",bad_health?0x02f90420:0x02f90400,reads%518);
    return n;
}
static int fake_close(int fd) { assert(fd==11||fd==12);return 0; }
static void *fake_mmap(void *p,size_t n,int prot,int flags,int fd,off_t offset) {
    (void)p;assert(n==sizeof(dma) && prot==PROT_READ && flags==MAP_SHARED && fd==12 && offset==0x01500000);
    readonly_maps++;memcpy(dma,cpu,sizeof(cpu));if(corrupt)dma[0]^=1;return dma;
}
static int fake_munmap(void *p,size_t n) { assert(p==dma && n==sizeof(dma));return 0; }
static int fake_usleep(useconds_t us) { assert(us==5000);return 0; }
#define open fake_open
#define read fake_read
#define close fake_close
#define mmap fake_mmap
#define munmap fake_munmap
#define usleep fake_usleep
#include "video_scanout_trace.h"
#undef open
#undef read
#undef close
#undef mmap
#undef munmap
#undef usleep
int main(void) {
    struct r36_scanout_health h;
    memset(cpu,0,sizeof(cpu));cpu[0]=1;
    uint32_t hash=scanout_hash(cpu,stride);
    cpu[1280]=1;assert(scanout_hash(cpu,stride)==hash);cpu[1280]=0;
    scanout_expected_hash=hash;scanout_expected_ready=1;
    scanout_trace("match",scanout_expected_hash,scanout_expected_ready);assert(readonly_maps==1);
    corrupt=1;scanout_trace("corrupt",hash,1);assert(readonly_maps==2);corrupt=0;
    bad_health=1;scanout_trace("bad_health",hash,1);assert(readonly_maps==2);bad_health=0;
    fail_memory=1;scanout_trace("no_memory",hash,1);assert(readonly_maps==2);fail_memory=0;
    assert(!scanout_health(&h) && scanout_valid(&h,stride));
    h.pixel=0x1883a000;assert(!scanout_valid(&h,stride));h.pixel=0x02f90000;assert(!scanout_valid(&h,stride));
    h.pixel=0x01500000;h.active=h.boot;assert(!scanout_valid(&h,stride));
    assert(scanout_parse("boot_descriptor=0",&h));
    puts("SCANOUT_OBSERVER_MOCK=PASS");return 0;
}
