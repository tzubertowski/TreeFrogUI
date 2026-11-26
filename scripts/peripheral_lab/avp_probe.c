#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>
#include "../kernel_lab/ports/amprpc-mailbox-plan.h"
#include "../kernel_lab/ports/amprpc-open-wire.h"

#define PAGE_BYTES 4096u
#define TRACE_PHYS 0x02f91000u
#define RAM_END 0x02f91000u
static void *held_page;
static volatile uint32_t *message;
static volatile uint32_t *tx, *rx;
static int memory_fd = -1;

static uint64_t milliseconds(void)
{
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now)) return UINT64_MAX;
    return (uint64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static void barrier(void) { __sync_synchronize(); }

static int wait_clear(volatile uint32_t *p, uint32_t mask)
{
    uint64_t deadline = milliseconds() + 100;
    do {
        if (!(*p & mask)) return 0;
        usleep(1000);
    } while (milliseconds() < deadline);
    return -1;
}

static void snapshot(const char *label)
{
    unsigned i;
    printf("MAILBOX %s\n", label);
    for (i = 0; i < 8; i++)
        printf("slot=%u tx=%08x,%08x,%08x,%08x rx=%08x,%08x,%08x,%08x\n", i,
               tx[i * 8], tx[i * 8 + 1], tx[i * 8 + 2], tx[i * 8 + 3],
               rx[i * 8], rx[i * 8 + 1], rx[i * 8 + 2], rx[i * 8 + 3]);
}

static int map_registers(void)
{
    void *a, *b;
    memory_fd = open("/dev/mem", O_RDWR | O_SYNC | O_CLOEXEC);
    if (memory_fd < 0) return -1;
    a = mmap(NULL, PAGE_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, memory_fd, 0x18800000);
    b = mmap(NULL, PAGE_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, memory_fd, 0x18866000);
    if (a == MAP_FAILED || b == MAP_FAILED) return -1;
    tx = (volatile uint32_t *)((unsigned char *)a + 0x800);
    rx = (volatile uint32_t *)((unsigned char *)b + 0x800);
    return 0;
}

static int allocate_message(uint32_t *physical)
{
    uint64_t entry;
    int fd;
    off_t offset;
    held_page = mmap(NULL, PAGE_BYTES, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (held_page == MAP_FAILED || mlock(held_page, PAGE_BYTES)) return -1;
    memset(held_page, 0, PAGE_BYTES);
    fd = open("/proc/self/pagemap", O_RDONLY | O_CLOEXEC);
    if (fd < 0) return -1;
    offset = ((uintptr_t)held_page / PAGE_BYTES) * 8;
    if (pread(fd, &entry, sizeof(entry), offset) != sizeof(entry)) { close(fd); return -1; }
    close(fd);
    if (!(entry & (1ULL << 63))) return -1;
    entry = (entry & ((1ULL << 55) - 1)) * PAGE_BYTES;
    if (entry < 0x100000 || entry + PAGE_BYTES > RAM_END) return -1;
    *physical = (uint32_t)entry;
    /* Stop dirty cached aliases from overwriting the uncached shared packet. */
    if (syscall(SYS_cacheflush, held_page, PAGE_BYTES, 3)) return -1;
    message = mmap(NULL, PAGE_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, memory_fd, *physical);
    if (message == MAP_FAILED) return -1;
    return 0;
}

static int transaction(void)
{
    static const char path[] = "/dev/r36_probe_no_such_device";
    uint32_t physical = 0, pointer;
    uint64_t deadline;
    unsigned i, tx_released = 0, rx_seen = 0;
    int response_seen = 0;
    int32_t result = 0;
    for (i = 0; i < 8; i++) {
        if ((tx[i * 8 + 2] & R36_AMP_PENDING_MASK) || rx[i * 8 + 3] || (tx[i * 8] & 1)) {
            puts("refused=preexisting_mailbox_activity");
            return -1;
        }
    }
    if (allocate_message(&physical)) { printf("allocation_failed errno=%d\n", errno); return -1; }
    pointer = 0xa0000000u | physical;
    printf("packet_phys=0x%08x packet_kseg1=0x%08x\n", physical, pointer);
    for (i = 0; i < PAGE_BYTES / 4; i++) message[i] = 0;
    if (r36_amp_open_packet(message, pointer + 0x100, path, 0, 0)) return -1;
    barrier();
    for (i = 0; i < 8; i++) tx[i * 8 + 2] = i < 4 ? 0x00010002 : 0x00000101;
    barrier();
    for (i = 0; i < 8; i++)
        if (wait_clear(tx + i * 8 + 2, R36_AMP_PENDING_MASK)) {
            puts("configuration_ack_timeout"); return -1;
        }
    tx[3] = pointer;
    barrier();
    if (tx[3] != pointer) { puts("payload_readback_mismatch"); return -1; }
    tx[0] |= 1;
    barrier();
    deadline = milliseconds() + 8000;
    do {
        for (i = 0; i < 8; i++) {
            uint32_t status = tx[i * 8 + 2], data = rx[i * 8 + 3];
            struct r36_amp_irq_plan plan = r36_amp_plan_irq(i, status, data);
            if (plan.action == R36_AMP_UNEXPECTED_PENDING) {
                printf("unexpected_pending slot=%u status=%08x\n", i, status); return -1;
            }
            if (plan.action == R36_AMP_RELEASE_TX) {
                if (i != 0) { puts("unrelated_tx_release"); return -1; }
                tx[i * 8 + 2] = plan.acknowledge;
                barrier();
                if (wait_clear(tx + i * 8 + 2, R36_AMP_TX_RELEASE_PENDING)) return -1;
                tx_released = 1;
            } else if (plan.action == R36_AMP_RECEIVE_MESSAGE) {
                if ((data & 0x1fffffff) != physical || (data >> 29) < 4 || (data >> 29) > 5) {
                    printf("unrelated_rx slot=%u pointer=%08x\n", i, data); return -1;
                }
                barrier();
                printf("response slot=%u state=%u opcode=%08x peer=%u result=%d\n",
                       i, message[0], message[1], message[2], (int32_t)message[4]);
                if (message[0] != 2 || message[1] != 0x1000 || message[2] != 3) return -1;
                result = (int32_t)message[4];
                response_seen = 1;
                rx[i * 8 + 3] = 0;
                barrier();
                if (wait_clear(rx + i * 8 + 3, 0xffffffff)) return -1;
                tx[i * 8 + 2] = plan.acknowledge;
                barrier();
                if (wait_clear(tx + i * 8 + 2, R36_AMP_RX_MESSAGE_PENDING)) return -1;
                tx[i * 8 + 1] = 1;
                barrier();
                message[2] = 4;
                barrier();
                rx_seen = 1;
            }
        }
        if (response_seen && tx_released && rx_seen) {
            printf("remote_nonexistent_open_result=%d\n", result);
            puts(result < 0 ? "transport=PASS" : "transport=FAIL_UNEXPECTED_FD");
            return result < 0 ? 0 : -1;
        }
        usleep(1000);
    } while (milliseconds() < deadline);
    printf("timeout state=%u opcode=%08x peer=%u result=%d tx_released=%u rx_seen=%u\n",
           message[0], message[1], message[2], (int32_t)message[4], tx_released, rx_seen);
    return -1;
}

static int prepare_pid1(const struct utsname *info)
{
    int attempt, fd;
    char id[80] = {0};
    FILE *file;
    volatile uint32_t *trace;
    mkdir("/dev", 0755); mkdir("/proc", 0755); mkdir("/sys", 0755); mkdir("/sd", 0755);
    mount("devtmpfs", "/dev", "devtmpfs", 0, NULL);
    mount("proc", "/proc", "proc", 0, NULL);
    mount("sysfs", "/sys", "sysfs", 0, NULL);
    fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd >= 0) {
        trace = mmap(NULL, PAGE_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, fd, TRACE_PHYS);
        if (trace != MAP_FAILED) { trace[4] = 6; barrier(); munmap((void *)trace, PAGE_BYTES); }
        close(fd);
    }
    for (attempt = 0; attempt < 20; attempt++) {
        if (!mount("/dev/mmcblk0p1", "/sd", "vfat", MS_NOATIME, "iocharset=iso8859-1")) break;
        sleep(1);
    }
    if (attempt == 20) return -1;
    file = fopen("/sd/cubegm/r36-run-id.txt", "r");
    if (file) { if (!fgets(id, sizeof(id), file)) id[0] = 0; fclose(file); }
    id[strcspn(id, "\r\n")] = 0;
    file = fopen("/sd/cubegm/r36-own-kernel-proof.txt", "w");
    if (file) {
        fprintf(file, "R36 OWN KERNEL USERSPACE REACHED\nrun_id=%s\nsysname=Linux\nrelease=%s\nversion=%s\nmachine=%s\npid=1\n",
                id, info->release, info->version, info->machine);
        fflush(file); fsync(fileno(file)); fclose(file);
    }
    fd = open("/sd/cubegm/r36-avp-probe.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return -1;
    dup2(fd, STDOUT_FILENO); dup2(fd, STDERR_FILENO); close(fd);
    printf("run_id=%s\n", id);
    return 0;
}

static int kernel_transaction(void)
{
    const char *directory = "/sys/bus/platform/devices/18800800.amprpc-poll/";
    char path[256], report[512] = {0};
    ssize_t count;
    int fd, rc;
    puts("transport_mode=kernel_module");
    fd = open("/sd/cubegm/r36_amprpc_poll.ko", O_RDONLY | O_CLOEXEC);
    if (fd < 0) { printf("module_open_errno=%d\n", errno); return -1; }
    rc = syscall(SYS_finit_module, fd, "", 0);
    close(fd);
    if (rc) { printf("module_load_errno=%d\n", errno); return -1; }
    snprintf(path, sizeof(path), "%stest_roundtrip", directory);
    fd = open(path, O_WRONLY | O_CLOEXEC);
    if (fd < 0) { printf("sysfs_open_errno=%d\n", errno); return -1; }
    count = write(fd, "1", 1);
    printf("sysfs_write_rc=%ld errno=%d\n", (long)count, count < 0 ? errno : 0);
    close(fd);
    snprintf(path, sizeof(path), "%slast_result", directory);
    fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return -1;
    rc = read(fd, report, sizeof(report) - 1);
    close(fd);
    if (rc > 0) { report[rc] = 0; printf("kernel_report=%s", report); }
    rc = count == 1 && rc > 0 && !strncmp(report, "result=PASS ", sizeof("result=PASS ") - 1);
    puts(rc ? "kernel_transport=PASS" : "kernel_transport=FAIL");
    return rc ? 0 : -1;
}

int main(int argc, char **argv)
{
    struct utsname info;
    int pid1 = getpid() == 1, result = -1;
    setvbuf(stdout, NULL, _IOLBF, 0);
    if (uname(&info)) return 1;
    if (pid1 && prepare_pid1(&info)) for (;;) pause();
    printf("R36 AVP TRANSPORT PROBE V1\nkernel=%s %s\n", info.release, info.version);
    if (pid1 && !strncmp(info.release, "7.2.0-rc5-r36", sizeof("7.2.0-rc5-r36") - 1) &&
        argc == 2 && !strcmp(argv[1], "--kernel-probe")) result = kernel_transaction();
    else if (map_registers()) printf("register_mapping_failed errno=%d\n", errno);
    else {
        snapshot("before");
        if (pid1 && !strncmp(info.release, "7.2.0-rc5-r36", sizeof("7.2.0-rc5-r36") - 1)) result = transaction();
        else if (argc != 2 || strcmp(argv[1], "--inspect")) puts("request_refused=requires_own_kernel_PID1");
        else result = 0;
        snapshot("after");
    }
    printf("probe_rc=%d\nR36 AVP PROBE END\n", result);
    fflush(stdout);
    if (pid1) {
        fsync(STDOUT_FILENO);
        close(STDOUT_FILENO); close(STDERR_FILENO);
        sync();
        if (umount("/sd")) {
            mount(NULL, "/sd", "vfat", MS_REMOUNT | MS_RDONLY, NULL);
            sync();
        }
        /* Keep the allocated packet alive until the pre-armed watchdog reset. */
        for (;;) pause();
    }
    return result != 0;
}
