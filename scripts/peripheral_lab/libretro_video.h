/* SPDX-License-Identifier: MIT */
#ifndef R36_LIBRETRO_VIDEO_H
#define R36_LIBRETRO_VIDEO_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* Formats use libretro numeric values: 0RGB1555=0, XRGB8888=1, RGB565=2.
 * Conversion stays outside the legacy video ABI, which explicitly takes565.
 */
static inline int r36_libretro_to565(void *out, size_t capacity, const void *source,
                                    unsigned int width, unsigned int height, size_t pitch, unsigned int format)
{
    unsigned int x, y, bytes = format == 1 ? 4 : 2;
    if (!out || !source || !width || !height || width > 4096 || height > 4096 || format > 2 ||
        pitch < (size_t)width * bytes || pitch > 1048576 || (size_t)width * height > capacity / 2) return -1;
    for (y = 0; y < height; y++) {
        const unsigned char *row = (const unsigned char *)source + y * pitch;
        unsigned char *target = (unsigned char *)out + (size_t)y * width * 2;
        for (x = 0; x < width; x++) {
            uint16_t color;
            if (format == 1) {
                uint32_t value;
                memcpy(&value, row + x * 4, 4);
                color = (uint16_t)(((value >> 8) & 0xf800) | ((value >> 5) & 0x07e0) | ((value >> 3) & 31));
            } else {
                uint16_t value;
                memcpy(&value, row + x * 2, 2);
                if (format == 2) color = value;
                else {
                    unsigned int green = (value >> 5) & 31;
                    color = (uint16_t)(((value & 0x7c00) << 1) | ((green << 1 | green >> 4) << 5) | (value & 31));
                }
            }
            memcpy(target + x * 2, &color, 2);
        }
    }
    return 0;
}
#endif
