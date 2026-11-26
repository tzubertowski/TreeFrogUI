#include <fcntl.h>
#include <dirent.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/wait.h>
#include <unistd.h>
#include "image_bounds.h"

int main(int argc, char **argv)
{
    int fd, rc;
    unsigned long cmd;
    char buffer[128];
    if (argc != 2) {
        fprintf(stderr, "usage: r36bootctl status|prepare|probe|cancel|boot|boot-detached\n");
        return 2;
    }
    fd = open("/proc/r36boot", O_RDWR);
    if (fd < 0) { perror("/proc/r36boot"); return 1; }
    if (!strcmp(argv[1], "status")) {
        rc = read(fd, buffer, sizeof(buffer));
        if (rc > 0) fwrite(buffer, 1, rc, stdout);
        close(fd);
        return rc < 0;
    }
    if (!strcmp(argv[1], "prepare")) cmd = 0x52360001;
    else if (!strcmp(argv[1], "boot") || !strcmp(argv[1], "boot-detached")) cmd = 0x52360002;
    else if (!strcmp(argv[1], "cancel")) cmd = 0x52360003;
    else if (!strcmp(argv[1], "probe")) cmd = 0x52360004;
    else { close(fd); return 2; }
    if (!strcmp(argv[1], "boot-detached")) {
        pid_t child = fork();
        if (child < 0) { perror("fork"); close(fd); return 1; }
        if (child > 0) {
            printf("Detached handoff pid=%ld; syncing and unbinding stock USB gadget\n", (long)child);
            close(fd);
            return 0;
        }
        if (setsid() < 0) _exit(1);
        {
            int nullfd = open("/dev/null", O_RDWR);
            if (nullfd < 0 || dup2(nullfd, 0) < 0 || dup2(nullfd, 1) < 0 || dup2(nullfd, 2) < 0)
                _exit(1);
            if (nullfd > 2) close(nullfd);
        }
        sleep(2);
        sync();
        {
            char rate[16], timeout[16];
            int status;
            pid_t armer;
            snprintf(rate, sizeof(rate), "%u", WATCHDOG_RATE);
            snprintf(timeout, sizeof(timeout), "%u", WATCHDOG_SECONDS);
            armer = fork();
            if (armer < 0) _exit(1);
            if (armer == 0) {
                execl("/mnt/sdcard/cubegm/r36-wdt-diag", "r36-wdt-diag", "--arm", rate, timeout, (char *)NULL);
                _exit(1);
            }
            if (waitpid(armer, &status, 0) != armer || !WIFEXITED(status) || WEXITSTATUS(status))
                _exit(1);
        }
        {
            DIR *dir = opendir("/sys/kernel/config/usb_gadget");
            struct dirent *entry;
            if (dir) {
                while ((entry = readdir(dir))) {
                    char path[512];
                    int udc;
                    if (entry->d_name[0] == '.') continue;
                    snprintf(path, sizeof(path), "/sys/kernel/config/usb_gadget/%s/UDC", entry->d_name);
                    udc = open(path, O_WRONLY);
                    if (udc >= 0) { ssize_t written = write(udc, "\n", 1); (void)written; close(udc); }
                }
                closedir(dir);
            }
        }
        usleep(200000);
    }
    rc = ioctl(fd, cmd, 0);
    if (rc < 0) perror(argv[1]);
    close(fd);
    return rc < 0;
}
