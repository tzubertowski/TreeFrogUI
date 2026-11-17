/* SPDX-License-Identifier: MIT */
#ifndef R36_LEGACY_JOYPAD_H
#define R36_LEGACY_JOYPAD_H
#include <stdint.h>

/* Default names/bits observed in the existing tfkey consumer. Physical serial
 * positions are deliberately not encoded here; those require board calibration.
 * Output bits follow libretro RETRO_DEVICE_ID_JOYPAD_* (B,Y,Select,Start,...).
 */
static inline uint16_t r36_legacy_to_libretro(uint32_t word)
{
    static const unsigned char legacy_bits[12] = {14, 15, 0, 3, 4, 6, 7, 5, 13, 12, 10, 11};
    uint16_t result = 0;
    unsigned int i;
    for (i = 0; i < 12; i++) if (word & (UINT32_C(1) << legacy_bits[i])) result |= (uint16_t)(1u << i);
    return result;
}
#endif
