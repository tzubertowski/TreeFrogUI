#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

/* Staged PID1: the guard and fsck are embedded in RAM. The card must not be
 * mounted until the guard exits successfully. Failure does not launch a UI
 * or mount dirty media just to save a log. Existing watchdog handles return.
 */
int main(int argc, char **argv)
{
    int attempt, log, status;
    pid_t child, waited;
    mkdir("/dev", 0755); mkdir("/proc", 0755); mkdir("/sys", 0755);
    mkdir("/sd", 0755); mkdir("/tmp", 01777);
    if (mount("devtmpfs", "/dev", "devtmpfs", 0, NULL) ||
        mount("proc", "/proc", "proc", 0, NULL) ||
        mount("sysfs", "/sys", "sysfs", 0, NULL)) goto failed;
    for (attempt = 0; attempt < 20; attempt++) {
        if (!access("/dev/mmcblk0p1", F_OK)) break;
        sleep(1);
    }
    if (attempt == 20) goto failed;
    log = open("/tmp/fat-boot.log", O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (log < 0) goto failed;
    child = fork();
    if (child < 0) { close(log); goto failed; }
    if (!child) {
        if (dup2(log, 1) < 0 || dup2(log, 2) < 0) _exit(127);
        close(log);
        execl("/sbin/fat-boot-guard", "fat-boot-guard", (char *)NULL);
        _exit(127);
    }
    close(log);
    do { waited = waitpid(child, &status, 0); } while (waited < 0 && errno == EINTR);
    if (waited != child || !WIFEXITED(status) || WEXITSTATUS(status)) goto failed;
    argv[0] = "/next-init";
    execv("/next-init", argv);
failed:
    /* Do not force a reset here: a failed repair may require SD recovery.
     * The guard controls when watchdog is rearmed, never during a writer. */
    (void)argc;
    for (;;) pause();
}
