/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Pavel Kotek
 *
 * tfcodec - cheap lossless coder for RGB565 frames (16-bit pixels).
 *
 * A frame is w*h pixels, rows packed, scanned as one array of n = w*h pixels.
 * The bitstream is a sequence of ops; each starts with one byte:
 *
 *     op = byte >> 5, L = byte & 31
 *     count = L + 1            if L < 31
 *     count = 32 + varint      if L == 31   (varint: unsigned LEB128)
 *
 *   0 SKIP  count   pixels equal to the previous frame (delta frames only)
 *   1 UP    count   pixels equal to the pixel one row above (out[i] = out[i-w];
 *                   sequential semantics, so count may exceed w)
 *   2 RUN   count   pixels equal to the following u16 value
 *   3 LIT   count   u16 values follow (count*2 bytes)
 *   4 DLIT  count   u16 values follow, each written twice (2*count pixels)
 *   5..7    reserved (decoder error)
 *
 * The ops must cover exactly n pixels. Pixel values are little-endian u16.
 * Key frames contain no SKIP. Worst case size: 2*n + n/8 + 64 bytes
 * (see TFC_MAX_BYTES).
 */
#ifndef TFCODEC_H
#define TFCODEC_H

#include <stddef.h>
#include <stdint.h>

#define TFC_SKIP 0
#define TFC_UP   1
#define TFC_RUN  2
#define TFC_LIT  3
#define TFC_DLIT 4

#define TFC_MAX_BYTES(npix) ((size_t)(npix) * 2u + (size_t)(npix) / 8u + 64u)

#ifdef _WIN32
#define TFC_API __declspec(dllexport)
#else
#define TFC_API
#endif

/* Encode cur (w*h packed) as a delta against prev (NULL = key frame).
 * If prev is non-NULL it is updated in place to equal cur (only changed
 * pixels are written). Returns bytes written, or 0 if `cap` was too small
 * (prev is then partially updated: send a key frame next). */
TFC_API size_t tfc_encode(const uint16_t *cur, uint16_t *prev, int w, int h, uint8_t *out, size_t cap);

/* Decode into out (w*h). prev = previous frame (required for SKIP ops, may
 * alias out for in-place delta decoding). Returns 0 on success, <0 on a
 * malformed stream. */
TFC_API int tfc_decode(const uint8_t *in, size_t len, const uint16_t *prev, uint16_t *out, int w, int h);

/* 2x2 box downscale of an RGB565 image (w,h even or odd: last odd row/column
 * is dropped). Each channel: (a+b+c+d+2)>>2. dst is (w/2)*(h/2). */
TFC_API void tfc_downscale2(const uint16_t *src, int w, int h, uint16_t *dst);

#endif
