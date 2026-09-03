#include <sys/ipc.h>
#include <sys/shm.h>
#include <unistd.h>
#include <signal.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

/* Watch cubevol's shared button word while the MTP helper owns the UI.
 * FrogUI may persist a device-specific B mapping, so use it when available.
 * This helper deliberately reads the same shared-memory source as FrogUI: once
 * the MTP helper has replaced the frontend, libretro button callbacks no longer
 * reach the UI. */
#define KEYMAP_FILE "/mnt/sdcard/frogui/keymap.txt"

static int get_back_bit(void) {
    FILE *f = fopen(KEYMAP_FILE, "r");
    char line[64];
    int bit = 14; /* TreeFrogUI's default logical B mapping. */

    if (!f)
        return bit;
    while (fgets(line, sizeof(line), f)) {
        int value;
        if (sscanf(line, "B=%d", &value) == 1 && value >= 0 && value <= 15) {
            bit = value;
            break;
        }
    }
    fclose(f);
    return bit;
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    pid_t responder = (pid_t)strtol(argv[1], NULL, 10);
    key_t key = ftok("/tmp/joy_key", 'a');
    if (key == (key_t)-1) return 3;
    int shmid = shmget(key, sizeof(uint32_t), 0666);
    if (shmid < 0) return 4;
    volatile uint32_t *keys = (volatile uint32_t *)shmat(shmid, NULL, SHM_RDONLY);
    if (keys == (void *)-1) return 5;
    uint32_t back_mask = 1u << get_back_bit();
    /* The MTP mode is entered with A, then the launch screen waits two seconds,
     * so B cannot be stale here.  A short debounce makes a normal B tap work
     * while still rejecting cubevol's one-sample input noise. */
    int released_samples = 0;
    int held_samples = 0;
    int armed = 0;
    for (;;) {
        int down = ((*keys & back_mask) != 0);
        if (!armed) {
            if (down) released_samples = 0;
            else if (++released_samples >= 3) armed = 1;
            usleep(20000);
            continue;
        }
        if (down) {
            held_samples++;
        } else {
            held_samples = 0;
        }
        if (held_samples >= 2) {
            int fd = open("/tmp/treefrog_mtp_exit", O_WRONLY | O_CREAT | O_TRUNC, 0600);
            if (fd >= 0) close(fd);
            kill(responder, SIGTERM);
            break;
        }
        usleep(20000);
    }
    shmdt((const void *)keys);
    return 0;
}
