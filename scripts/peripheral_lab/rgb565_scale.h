/* SPDX-License-Identifier: MIT */
#ifndef R36_RGB565_SCALE_H
#define R36_RGB565_SCALE_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* Preserve aspect ratio, letterbox, synchronous copy. No caller buffer survives
 * this call. Input byte pitch may include padding; source must be RGB565. */
static inline int r36_scale565(void *destination, unsigned int dst_pitch,
                               const void *source, int width, int height, int src_pitch)
{
    unsigned int x, y, out_w, out_h, left, top;
    if (!destination || !source || width < 1 || height < 1 || width > 4096 || height > 4096 ||
        src_pitch < width * 2 || src_pitch > 1024 * 1024 || dst_pitch < 1280 || dst_pitch > 65536)
        return -1;
    if ((unsigned int)width * 480 > (unsigned int)height * 640) {
        out_w = 640; out_h = (unsigned int)height * 640 / (unsigned int)width;
    } else {
        out_h = 480; out_w = (unsigned int)width * 480 / (unsigned int)height;
    }
    if (!out_w) out_w = 1;
    if (!out_h) out_h = 1;
    left = (640 - out_w) / 2; top = (480 - out_h) / 2;
    for (y = 0; y < 480; y++) memset((unsigned char *)destination + y * dst_pitch, 0, 1280);
    for (y = 0; y < out_h; y++) {
        const unsigned char *row = (const unsigned char *)source +
            (size_t)(y * (unsigned int)height / out_h) * (unsigned int)src_pitch;
        unsigned char *out = (unsigned char *)destination + (y + top) * dst_pitch + left * 2;
        for (x = 0; x < out_w; x++) {
            unsigned int offset = (x * (unsigned int)width / out_w) * 2;
            out[x * 2] = row[offset]; out[x * 2 + 1] = row[offset + 1];
        }
    }
    return 0;
}
#endif
