#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/types.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <unistd.h>
#include "fat_boot_policy.h"

/* This helper is staged, not installed. PID1 must call it before mounting SD.
 * Logs and the pre-repair metadata snapshot live in initramfs, never on SD.
 * No timeout is allowed to terminate a filesystem writer.
 */
static volatile uint32_t *wdt;
static uint32_t old_control;
#ifndef R36_FAT_ENABLE_REPAIR
#define R36_FAT_ENABLE_REPAIR 0
#endif

static int run_fsck(const char *tool, const char *device, int repair, int *signalled)
{
    int status, output[2], matches = 0, read_error;
    char line[512] = "", last[512] = "", expected[96];
    FILE *stream;
    pid_t child, got;
    *signalled = 0;
    if (pipe(output)) return -1;
    child = fork();
    if (child < 0) { close(output[0]); close(output[1]); return -1; }
    if (!child) {
        close(output[0]);
        if (dup2(output[1], STDOUT_FILENO) < 0) _exit(127);
        close(output[1]);
        if (repair) execl(tool, tool, "-c", "437", "-a", "-f", device, (char *)NULL);
        else execl(tool, tool, "-c", "437", "-n", device, (char *)NULL);
        _exit(127);
    }
    close(output[1]);
    stream = fdopen(output[0], "r");
    if (!stream) {
        close(output[0]);
        do { got = waitpid(child, &status, 0); } while (got < 0 && errno == EINTR);
        return -1;
    }
    /* Consume the pipe while the child runs, never block it on a full pipe.
     * The marker comes from our patched fsck only after successful fs_close.
     */
    while (fgets(line, sizeof(line), stream)) {
        fputs(line, stdout);
        memcpy(last, line, sizeof(last));
        if (!strncmp(line, "R36_FSCK_COMPLETE_V1 ", sizeof("R36_FSCK_COMPLETE_V1 ") - 1)) matches++;
    }
    read_error = ferror(stream);
    fclose(stream);
    do { got = waitpid(child, &status, 0); } while (got < 0 && errno == EINTR);
    if (got < 0) return -1;
    *signalled = !WIFEXITED(status);
    if (!WIFEXITED(status)) return -1;
    status = WEXITSTATUS(status);
    snprintf(expected, sizeof(expected), "R36_FSCK_COMPLETE_V1 mode=%s status=%d\n",
             repair ? "repair" : "check", status);
    if (read_error || matches != 1 || strcmp(last, expected) || status > 1) return -1;
    return status;
}

static int block_is_offline(const char *device)
{
    struct stat st;
    FILE *file;
    char line[4096];
    unsigned int maj, min;
    if (stat(device, &st) || !S_ISBLK(st.st_mode)) return 0;
    file = fopen("/proc/self/mountinfo", "r");
    if (!file) return 0;
    while (fgets(line, sizeof(line), file)) {
        if (sscanf(line, "%*u %*u %u:%u", &maj, &min) != 2 ||
            (maj == major(st.st_rdev) && min == minor(st.st_rdev))) {
            fclose(file); return 0;
        }
    }
    if (ferror(file)) { fclose(file); return 0; }
    fclose(file);
    file = fopen("/proc/swaps", "r");
    if (!file) return 0;
    if (!fgets(line, sizeof(line), file) || fgets(line, sizeof(line), file) || ferror(file)) {
        fclose(file); return 0;
    }
    fclose(file);
    /* Also rejects a concurrent exclusive block-device holder. PID1 owns boot;
     * no other process is allowed to mount after this check. */
    {
        int fd = open(device, O_RDONLY | O_EXCL | O_CLOEXEC);
        if (fd < 0) return 0;
        close(fd);
    }
    return 1;
}

static int pause_watchdog(void)
{
    int fd = open("/dev/mem", O_RDWR | O_SYNC | O_CLOEXEC);
    void *map;
    if (fd < 0) return -1;
    map = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0x18818000);
    close(fd);
    if (map == MAP_FAILED) return -1;
    wdt = (volatile uint32_t *)((unsigned char *)map + 0x500);
    old_control = wdt[1];
    /* Refuse unknown prescaler/mode instead of assuming any watchdog ABI. */
    if (old_control != 0x26) return -1;
    wdt[1] = 0;
    __sync_synchronize();
    return wdt[1] == 0 ? 0 : -1;
}

static void resume_watchdog(void)
{
    if (!wdt) return;
    /* Same measured 187500 Hz/reload/control as the accepted diagnostic loader. */
    wdt[0] = (uint32_t)(0u - 187500u * 30u);
    wdt[1] = old_control;
    __sync_synchronize();
}

static int metadata_snapshot(const char *device)
{
    const size_t limit = 8u * 1024u * 1024u;
    unsigned char buffer[16384];
    size_t done = 0;
    int in = open(device, O_RDONLY | O_CLOEXEC);
    int out = open("/tmp/fat-before-metadata.bin", O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    int result = -1;
    if (in < 0 || out < 0) goto finish;
    while (done < limit) {
        ssize_t n = read(in, buffer, sizeof(buffer));
        ssize_t offset = 0;
        if (n <= 0) goto finish;
        while (offset < n) {
            ssize_t wrote = write(out, buffer + offset, (size_t)(n - offset));
            if (wrote <= 0) goto finish;
            offset += wrote;
        }
        done += (size_t)n;
    }
    result = fsync(out);
finish:
    if (in >= 0) close(in);
    if (out >= 0) close(out);
    /* This contains both FATs on this board, NOT all directory/file data. */
    return result;
}

int main(int argc, char **argv)
{
    const char *device = "/dev/mmcblk0p1", *tool = "/sbin/fsck.fat";
    struct utsname identity;
    int testing = argc == 4 && !strcmp(argv[1], "--image-test");
    int status, signalled, result = 2;
    setvbuf(stdout, NULL, _IOLBF, 0);
    if (testing) {
        struct stat st;
        tool = argv[2]; device = argv[3];
        /* Test mode cannot access block devices or any real watchdog. */
        if (stat(device, &st) || !S_ISREG(st.st_mode)) return 2;
    } else {
        if (argc != 1 || getppid() != 1 || uname(&identity) ||
            strncmp(identity.release, "7.2.0-rc5-r36", sizeof("7.2.0-rc5-r36") - 1)) return 2;
        if (!block_is_offline(device)) { puts("fat_guard=REFUSED_NOT_OFFLINE"); return 2; }
        /* Read-only checking keeps the diagnostic watchdog armed. A hang may
         * reset safely because no filesystem writer has been started. */
    }
    status = run_fsck(tool, device, 0, &signalled);
    printf("fat_check_exit=%d signalled=%d\n", status, signalled);
    switch (r36_fat_after_check(status, signalled)) {
    case R36_FAT_BOOT:
        puts("fat_guard=CLEAN"); result = 0; break;
    case R36_FAT_STOP:
        puts("fat_guard=CHECK_FAILED_NO_REPAIR"); break;
    case R36_FAT_REPAIR:
        /* Production writes remain locked until the bundled fsck's CP437,
         * fatal-vs-complete status and real image tests have been accepted.
         * A status of 1 alone must NEVER authorize writing to the SD card.
         */
        if (!testing && !R36_FAT_ENABLE_REPAIR) {
            puts("fat_guard=REPAIR_NOT_VALIDATED_NO_WRITE");
            break;
        }
        if (!testing && (!block_is_offline(device) || metadata_snapshot(device))) {
            puts("fat_guard=REFUSED_BACKUP_OR_MOUNT"); break;
        }
        if (!testing && pause_watchdog()) {
            puts("fat_guard=REFUSED_WATCHDOG"); break;
        }
        status = run_fsck(tool, device, 1, &signalled);
        printf("fat_repair_exit=%d signalled=%d\n", status, signalled);
        sync();
        if (!r36_fat_repair_may_verify(status, signalled)) {
            puts("fat_guard=REPAIR_FAILED"); break;
        }
        status = run_fsck(tool, device, 0, &signalled);
        printf("fat_verify_exit=%d signalled=%d\n", status, signalled);
        if (r36_fat_verified(status, signalled)) {
            puts("fat_guard=REPAIRED_VERIFIED"); result = 0;
        } else puts("fat_guard=VERIFY_FAILED");
        break;
    }
    sync();
    if (!testing) resume_watchdog();
    return result;
}
