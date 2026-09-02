#include <sys/ipc.h>
#include <sys/shm.h>
#include <unistd.h>
#include <signal.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdint.h>

/* Watch cubevol's shared button word while the MTP helper owns the UI.
 * Logical B is raw bit 14 (the same mapping used by FrogUI). */
int main(int argc, char **argv) {
    if (argc < 2) return 2;
    pid_t responder = (pid_t)strtol(argv[1], NULL, 10);
    key_t key = ftok("/tmp/joy_key", 'a');
    if (key == (key_t)-1) return 3;
    int shmid = shmget(key, sizeof(uint32_t), 0666);
    if (shmid < 0) return 4;
    volatile uint32_t *keys = (volatile uint32_t *)shmat(shmid, NULL, SHM_RDONLY);
    if (keys == (void *)-1) return 5;
    /* B is often still asserted for a few frames after it has returned the
     * previous USB session to FrogUI.  Do not treat that stale state as a
     * request to immediately terminate the next session: arm only after B
     * has been released continuously for 300ms, then require a fresh 100ms
     * B hold. */
    int released_samples = 0;
    int held_samples = 0;
    int armed = 0;
    for (;;) {
        int down = ((*keys & (1u << 14)) != 0);
        if (!armed) {
            if (down) released_samples = 0;
            else if (++released_samples >= 15) armed = 1;
            usleep(20000);
            continue;
        }
        if (down) {
            held_samples++;
        } else {
            held_samples = 0;
        }
        if (held_samples >= 5) {
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
