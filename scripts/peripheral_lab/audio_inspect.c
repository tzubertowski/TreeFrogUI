/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>

/* Passive ownership evidence, not a driver: read only selected SND0/system
 * registers, never clear IRQs/reset/PLL or set GPIO. A quiet snapshot does not
 * prove the AVP will never access this hardware later.
 */
int main(void)
{
    int fd = open("/dev/mem", O_RDONLY | O_SYNC | O_CLOEXEC);
    volatile uint32_t *sound, *system;
    volatile uint16_t *positions;
    volatile uint8_t *gain;
    unsigned int sample;
    if (fd < 0) { perror("/dev/mem"); return 1; }
    sound = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, 0x1880a000);
    system = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, 0x18800000);
    close(fd);
    if (sound == MAP_FAILED || system == MAP_FAILED) {
        if (sound != MAP_FAILED) munmap((void *)sound, 4096);
        if (system != MAP_FAILED) munmap((void *)system, 4096);
        return 1;
    }
    positions = (volatile uint16_t *)((volatile uint8_t *)sound + 0x38);
    gain = (volatile uint8_t *)sound + 0x92;
    puts("R36 AUDIO PASSIVE V1");
    for (sample = 0; sample < 6; sample++) {
        printf("sample=%u control=%08x format=%08x dma=%08x config=%08x wr=%u rd=%u gain=%u current_gain=%u\n",
               sample, sound[1], sound[0x50 / 4], sound[0x30 / 4], sound[0x34 / 4],
               positions[0], positions[1], gain[0], gain[1]);
        usleep(20000);
    }
    printf("gate=%08x reset=%08x pad_clock=%08x divider=%08x pad=%08x pll_control=%08x pll_fraction=%08x pll_integer=%08x\n",
           system[0x64 / 4], system[0x80 / 4], system[0x8c / 4], system[0x148 / 4],
           system[0x154 / 4], system[0x470 / 4], system[0x474 / 4], system[0x478 / 4]);
    puts("ownership_exclusive=NOT_PROVEN\nR36 AUDIO PASSIVE END");
    munmap((void *)sound, 4096); munmap((void *)system, 4096);
    return 0;
}
