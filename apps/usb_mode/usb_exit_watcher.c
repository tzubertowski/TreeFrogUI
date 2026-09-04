#include <sys/ipc.h>
#include <sys/shm.h>
#include <unistd.h>
#include <signal.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdarg.h>

/* Watch cubevol's shared button word while the MTP helper owns the UI.
 * FrogUI may persist a device-specific B mapping, so use it when available.
 * This helper deliberately reads the same shared-memory source as FrogUI: once
 * the MTP helper has replaced the frontend, libretro button callbacks no longer
 * reach the UI. */
#define KEYMAP_FILE "/mnt/sdcard/frogui/keymap.txt"
#define DEBUG_LOG   "/mnt/sdcard/log.txt"

/* Match TreeFrogUI's opt-in diagnostic convention: write only when log.txt
 * exists.  This watcher runs outside the UI, so these lines are the only way
 * to distinguish a genuine B match from a collapsed/aliased raw input bit. */
static FILE *debug_log;
static void debug(const char *fmt, ...) {
    va_list ap;
    if (!debug_log) return;
    va_start(ap, fmt);
    vfprintf(debug_log, fmt, ap);
    va_end(ap);
    fflush(debug_log);
}

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
    int back_bit = get_back_bit();
    uint32_t back_mask = 1u << back_bit;
    const uint32_t direction_mask = (1u << 4) | (1u << 5) | (1u << 6) | (1u << 7);
    uint32_t previous_raw = ~0u;
    if (access(DEBUG_LOG, F_OK) == 0)
        debug_log = fopen(DEBUG_LOG, "a");
    debug("USB_EXIT watcher start pid=%d responder=%d B_bit=%d mask=0x%04x\n",
          (int)getpid(), (int)responder, back_bit, (unsigned)back_mask);
    /* The MTP mode is entered with A, then the launch screen waits two seconds,
     * so B cannot be stale here.  A short debounce makes a normal B tap work
     * while still rejecting cubevol's one-sample input noise. */
    int released_samples = 0;
    int held_samples = 0;
    int armed = 0;
    for (;;) {
        uint32_t raw = *keys & 0xFFFFu;
        int down = (raw & back_mask) != 0;
        /* Only state changes involving B or directions are recorded.  This is
         * enough to diagnose reports that a D-pad/stick action exits MTP,
         * without turning normal operation into a noisy polling log. */
        if (raw != previous_raw && ((raw | previous_raw) & (back_mask | direction_mask))) {
            debug("USB_EXIT input raw=0x%04x B=%d dirs=0x%02x armed=%d held=%d\n",
                  (unsigned)raw, down, (unsigned)((raw & direction_mask) >> 4),
                  armed, held_samples);
        }
        previous_raw = raw;
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
            debug("USB_EXIT trigger raw=0x%04x B_bit=%d\n", (unsigned)raw, back_bit);
            int fd = open("/tmp/treefrog_mtp_exit", O_WRONLY | O_CREAT | O_TRUNC, 0600);
            if (fd >= 0) close(fd);
            kill(responder, SIGTERM);
            break;
        }
        usleep(20000);
    }
    shmdt((const void *)keys);
    if (debug_log) fclose(debug_log);
    return 0;
}
