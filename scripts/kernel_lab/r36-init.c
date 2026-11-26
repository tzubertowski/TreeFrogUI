#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/klog.h>
#include <sys/mman.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <unistd.h>
#include "user_trace.h"

static unsigned char wanted[12288];

static int copy_file(int out, const char *path)
{
    char buffer[4096];
    int fd = open(path, O_RDONLY), n;
    if (fd < 0) return -1;
    dprintf(out, "\n--- %s ---\n", path);
    while ((n = read(fd, buffer, sizeof(buffer))) > 0)
        if (write(out, buffer, n) != n) { close(fd); return -1; }
    close(fd);
    return n < 0 ? -1 : 0;
}

static int load_module(const char *name)
{
    char path[128];
    int fd, result;
    snprintf(path, sizeof(path), "/sd/cubegm/%s.ko", name);
    fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    result = syscall(SYS_finit_module, fd, "", 0);
    close(fd);
    return result;
}

static int driver_test(int out)
{
    int loaded = load_module("r36hello"), fd, n, parameter_ok = 0, unloaded;
    char marker[64] = {0};
    dprintf(out, "driver_load_rc=%d errno=%d\n", loaded, loaded ? errno : 0);
    fd = open("/sys/module/r36hello/parameters/marker", O_RDONLY);
    if (fd >= 0) {
        n = read(fd, marker, sizeof(marker) - 1);
        parameter_ok = n > 0 && strtoul(marker, NULL, 10) == 0x523336;
        close(fd);
    }
    dprintf(out, "driver_parameter_ok=%d marker=%s", parameter_ok, marker);
    unloaded = loaded ? -1 : syscall(SYS_delete_module, "r36hello", O_NONBLOCK);
    dprintf(out, "\ndriver_unload_rc=%d\ndriver_sysfs_removed=%d\n", unloaded,
            access("/sys/module/r36hello", F_OK) != 0);
    return loaded == 0 && parameter_ok && unloaded == 0 &&
           access("/sys/module/r36hello", F_OK) != 0;
}

static int page_ownership_test(int out)
{
    struct old_page { uint32_t address, usable; } *plan;
    int fd = open("/sd/cubegm/r36-reclaim-plan.bin", O_RDONLY), proc, loaded;
    struct stat st;
    ssize_t n;
    size_t i, records;
    char report[2048] = {0};
    unsigned long total = 0, valid = 0, managed = 0;
    char *found;
    if (fd < 0 || fstat(fd, &st) || st.st_size <= 0 ||
        st.st_size > 12288 * 8 || st.st_size % 8) {
        if (fd >= 0) close(fd);
        dprintf(out, "page_plan_valid=0\n");
        return 0;
    }
    plan = malloc(st.st_size);
    if (!plan) { close(fd); return 0; }
    n = read(fd, plan, st.st_size);
    close(fd);
    if (n != st.st_size) { free(plan); return 0; }
    records = st.st_size / sizeof(*plan);
    for (i = 0; i < records; i++) {
        uint32_t pfn = (plan[i].address & 0x1fffffff) >> 12;
        if (plan[i].usable && pfn < sizeof(wanted)) wanted[pfn] = 1;
    }
    loaded = load_module("r36memcheck");
    dprintf(out, "page_plan_records=%lu\nmemcheck_load_rc=%d\n", (unsigned long)records, loaded);
    proc = loaded ? -1 : open("/proc/r36memcheck", O_RDWR);
    n = proc < 0 ? -1 : write(proc, plan, st.st_size);
    free(plan);
    if (proc >= 0 && n == st.st_size && lseek(proc, 0, SEEK_SET) == 0) {
        n = read(proc, report, sizeof(report) - 1);
        if (n > 0) {
            report[n] = 0;
            dprintf(out, "%s", report);
            found = strstr(report, "stage_total=");
            if (found) total = strtoul(found + strlen("stage_total="), NULL, 10);
            found = strstr(report, "stage_valid=");
            if (found) valid = strtoul(found + strlen("stage_valid="), NULL, 10);
            found = strstr(report, "stage_managed=");
            if (found) managed = strtoul(found + strlen("stage_managed="), NULL, 10);
        }
    }
    if (proc >= 0) close(proc);
    n = loaded ? -1 : syscall(SYS_delete_module, "r36memcheck", O_NONBLOCK);
    dprintf(out, "memcheck_unload_rc=%ld\n", (long)n);
    return total > 0 && valid == total && managed > 0 && n == 0;
}

static int memory_test(int out)
{
    FILE *info = fopen("/proc/meminfo", "r");
    char line[256];
    unsigned long available = 0, size, words, i, errors = 0;
    volatile uint32_t *memory;
    unsigned int pass, present = 0, reused = 0;
    int pagemap;
    if (info) {
        while (fgets(line, sizeof(line), info))
            if (sscanf(line, "MemAvailable: %lu kB", &available) == 1) break;
        fclose(info);
    }
    if (available < 16384) { dprintf(out, "ram_test_error=insufficient headroom\n"); return 0; }
    size = (available - 8192) * 1024;
    if (size > 24 * 1024 * 1024) size = 24 * 1024 * 1024;
    size &= ~4095UL;
    memory = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (memory == MAP_FAILED) { dprintf(out, "ram_test_error=mmap errno %d\n", errno); return 0; }
    words = size / sizeof(*memory);
    for (pass = 0; pass < 3; pass++) {
        uint32_t seed = pass == 0 ? 0x13579bdf : pass == 1 ? 0xeca86420 : 0x55aa55aa;
        for (i = 0; i < words; i++) memory[i] = (uint32_t)i * 2654435761U ^ seed;
        for (i = 0; i < words; i++) {
            uint32_t expected = (uint32_t)i * 2654435761U ^ seed;
            if (memory[i] != expected) { errors++; break; }
        }
    }
    copy_file(out, "/proc/meminfo");
    pagemap = open("/proc/self/pagemap", O_RDONLY);
    if (pagemap >= 0) {
        for (i = 0; i < size / 4096; i++) {
            uint64_t entry = 0, pfn;
            off_t offset = (((uintptr_t)memory >> 12) + i) * 8;
            if (pread(pagemap, &entry, sizeof(entry), offset) != sizeof(entry)) continue;
            if (!(entry & (1ULL << 63))) continue;
            present++;
            pfn = entry & ((1ULL << 55) - 1);
            if (pfn < sizeof(wanted) && wanted[pfn]) reused++;
        }
        close(pagemap);
    }
    munmap((void *)memory, size);
    dprintf(out, "ram_test_bytes=%lu\nram_test_passes=3\nram_test_errors=%lu\n"
            "ram_pages_present=%u\nformer_loader_pages_reused=%u\n",
            size, errors, present, reused);
    return errors == 0 && present == size / 4096 && reused > 0;
}

static void save_kernel_log(void)
{
    char *buffer = malloc(256 * 1024);
    int fd, n;
    if (!buffer) return;
    n = klogctl(3, buffer, 256 * 1024);
    fd = open("/sd/cubegm/r36-memory-kmsg.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (n > 0 && fd >= 0) {
        int done = 0;
        while (done < n) {
            int written = write(fd, buffer + done, n - done);
            if (written <= 0) break;
            done += written;
        }
        fsync(fd);
    }
    if (fd >= 0) close(fd);
    free(buffer);
}

static void restart_stock(void)
{
    int fd = open("/dev/mem", O_RDWR | O_SYNC);
    volatile uint32_t *regs;
    if (fd < 0) return;
    regs = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0x18818000);
    if (regs == MAP_FAILED) { close(fd); return; }
    /* Exact iowrite32 sequence from stock board_restart at 0x80000e4c. */
    regs[0x500 / 4] = 0xfffffffa;
    __sync_synchronize();
    regs[0x504 / 4] = 0x26;
    __sync_synchronize();
    munmap((void *)regs, 4096);
    close(fd);
}

int main(void)
{
    struct utsname u;
    int fd, attempt, automatic_return = 0;
    mkdir("/dev", 0755);
    mkdir("/proc", 0755);
    mkdir("/sys", 0755);
    mkdir("/sd", 0755);
    mount("devtmpfs", "/dev", "devtmpfs", 0, NULL);
    mount("proc", "/proc", "proc", 0, NULL);
    mount("sysfs", "/sys", "sysfs", 0, NULL);
    uname(&u);
    mark_userspace();
    fd = open("/dev/console", O_WRONLY);
    if (fd >= 0) {
        dprintf(fd, "R36 OWN KERNEL: %s %s; PID=%ld\n", u.release, u.version, (long)getpid());
        close(fd);
    }
    for (attempt = 0; attempt < 60; attempt++) {
        if (!mount("/dev/mmcblk0p1", "/sd", "vfat", MS_NOATIME, "iocharset=iso8859-1"))
            break;
        sleep(1);
    }
    if (attempt < 60) {
        /* Separate proof file: never replace stock boot files. */
        fd = open("/sd/cubegm/r36-own-kernel-proof.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (fd >= 0) {
            dprintf(fd, "R36 OWN KERNEL USERSPACE REACHED\nsysname=%s\nrelease=%s\nversion=%s\nmachine=%s\npid=%ld\n",
                    u.sysname, u.release, u.version, u.machine, (long)getpid());
            fsync(fd);
            close(fd);
        }
        automatic_return = access("/sd/cubegm/r36-test-autoreboot", F_OK) == 0;
        fd = open("/sd/cubegm/r36-memory-test.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (fd >= 0) {
            int driver_ok, ownership_ok, memory_ok;
            dprintf(fd, "R36 MEMORY AND MODULE TEST V1\nrelease=%s\nversion=%s\npid=%ld\n",
                    u.release, u.version, (long)getpid());
            copy_file(fd, "/proc/meminfo");
            copy_file(fd, "/proc/iomem");
            copy_file(fd, "/proc/buddyinfo");
            driver_ok = driver_test(fd);
            ownership_ok = page_ownership_test(fd);
            memory_ok = memory_test(fd);
            copy_file(fd, "/proc/meminfo");
            copy_file(fd, "/proc/modules");
            dprintf(fd, "driver_test=%s\npage_ownership_test=%s\nram_test=%s\noverall=%s\n"
                    "automatic_return_requested=%d\n",
                    driver_ok ? "PASS" : "FAIL", ownership_ok ? "PASS" : "FAIL",
                    memory_ok ? "PASS" : "FAIL", driver_ok && ownership_ok && memory_ok ? "PASS" : "FAIL",
                    automatic_return);
            fsync(fd);
            close(fd);
        }
        save_kernel_log();
        sync();
        umount("/sd");
    }
    if (automatic_return) { sleep(5); restart_stock(); }
    /* Keep PID 1 alive; this diagnostic image does not power down the device. */
    for (;;)
        pause();
}
