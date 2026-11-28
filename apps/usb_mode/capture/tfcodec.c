/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Pavel Kotek
 *
 * tfcodec - see tfcodec.h for the bitstream description.
 */
#include "tfcodec.h"
#include <string.h>

typedef uint32_t __attribute__((may_alias, aligned(4))) u32a;

/* Number of leading equal pixels of a[] and b[], at most max. Uses 32-bit
 * compares when both pointers have the same alignment. */
static inline size_t match_len(const uint16_t *a, const uint16_t *b, size_t max)
{
    size_t k = 0;
    if ((((uintptr_t)a ^ (uintptr_t)b) & 3u) == 0) {
        if (((uintptr_t)a & 2u) && max) {
            if (a[0] != b[0]) return 0;
            k = 1;
        }
        while (k + 8 <= max) {             /* 4 words per iteration */
            const u32a *pa = (const u32a *)(a + k), *pb = (const u32a *)(b + k);
            if (pa[0] != pb[0] || pa[1] != pb[1] || pa[2] != pb[2] || pa[3] != pb[3]) break;
            k += 8;
        }
        while (k + 2 <= max && *(const u32a *)(a + k) == *(const u32a *)(b + k)) k += 2;
    }
    while (k < max && a[k] == b[k]) k++;
    return k;
}

static inline size_t run_len(const uint16_t *a, size_t max)
{
    uint16_t v = a[0];
    size_t k = 1;
    while (k < max && a[k] == v) k++;
    return k;
}

static inline uint8_t *put_op(uint8_t *o, unsigned op, size_t count)
{
    if (count <= 31) {
        *o++ = (uint8_t)((op << 5) | (unsigned)(count - 1));
    } else {
        *o++ = (uint8_t)((op << 5) | 31u);
        size_t v = count - 32;
        while (v >= 0x80) { *o++ = (uint8_t)(v | 0x80); v >>= 7; }
        *o++ = (uint8_t)v;
    }
    return o;
}

static inline uint8_t *put_px(uint8_t *o, uint16_t v)
{
    o[0] = (uint8_t)v; o[1] = (uint8_t)(v >> 8);
    return o + 2;
}

/* Emit literal pixels cur[a..b) as LIT/DLIT pieces. */
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
static inline uint8_t *put_pixels(uint8_t *o, const uint16_t *src, size_t cnt)
{
    memcpy(o, src, cnt * 2);                   /* pixels are stored little-endian */
    return o + cnt * 2;
}
#else
static inline uint8_t *put_pixels(uint8_t *o, const uint16_t *src, size_t cnt)
{
    for (size_t k = 0; k < cnt; k++) o = put_px(o, src[k]);
    return o;
}
#endif

/* Emit literal pixels cur[a..b) as LIT/DLIT pieces (DLIT = >= 2 doubled pairs). */
static uint8_t *flush_lit(uint8_t *o, uint8_t *end, const uint16_t *cur, size_t a, size_t b)
{
    size_t lit0 = a, j = a;
    while (j + 3 < b) {
        if (cur[j] != cur[j + 1] || cur[j + 2] != cur[j + 3]) { j++; continue; }
        size_t p = 2;
        while (j + 2 * p + 1 < b && cur[j + 2 * p] == cur[j + 2 * p + 1]) p++;
        if (j > lit0) {
            if ((size_t)(end - o) < 4 + 2 * (j - lit0)) return NULL;
            o = put_op(o, TFC_LIT, j - lit0);
            o = put_pixels(o, cur + lit0, j - lit0);
        }
        if ((size_t)(end - o) < 4 + 2 * p) return NULL;
        o = put_op(o, TFC_DLIT, p);
        for (size_t k = 0; k < p; k++) o = put_px(o, cur[j + 2 * k]);
        j += 2 * p;
        lit0 = j;
    }
    if (b > lit0) {
        if ((size_t)(end - o) < 4 + 2 * (b - lit0)) return NULL;
        o = put_op(o, TFC_LIT, b - lit0);
        o = put_pixels(o, cur + lit0, b - lit0);
    }
    return o;
}

/* First j >= start where a SKIP (>= 2, or the final pixel), UP (>= 2) or
 * RUN (>= 3) could begin; cheap two/three-pixel tests only. */
static inline __attribute__((always_inline))
size_t lit_end(const uint16_t *cur, const uint16_t *prev, size_t j, size_t n, size_t W, const int has_prev)
{
    for (; j + 2 < n; j++) {                   /* body: j+1, j+2 in range */
        uint16_t c = cur[j], c1 = cur[j + 1];
        if (has_prev && c == prev[j] && c1 == prev[j + 1]) return j;
        if (c == c1 && c == cur[j + 2]) return j;
        if (j >= W && c == cur[j - W] && c1 == cur[j + 1 - W]) return j;
    }
    for (; j < n; j++) {                       /* last two pixels */
        uint16_t c = cur[j];
        if (has_prev && c == prev[j] && (j + 1 == n || cur[j + 1] == prev[j + 1])) return j;
        if (j + 1 < n && j >= W && c == cur[j - W] && cur[j + 1] == cur[j + 1 - W]) return j;
    }
    return n;
}

size_t tfc_encode(const uint16_t *cur, uint16_t *prev, int w, int h, uint8_t *out, size_t cap)
{
    if (w <= 0 || h <= 0) return 0;
    const size_t n = (size_t)w * (size_t)h, W = (size_t)w;
    uint8_t *o = out, *end = out + cap;
    size_t i = 0;

    while (i < n) {
        size_t rem = n - i;
        if (prev && cur[i] == prev[i]) {
            size_t s = match_len(cur + i, prev + i, rem);
            if (s >= 2 || s == rem) {
                if (end - o < 4) return 0;
                o = put_op(o, TFC_SKIP, s);
                i += s;
                continue;
            }
        }
        size_t best = 0;
        unsigned bop = 0;
        if (i >= W && cur[i] == cur[i - W]) {
            size_t u = match_len(cur + i, cur + i - W, rem);
            if (u >= 2) { best = u; bop = TFC_UP; }
        }
        if (rem >= 3 && cur[i] == cur[i + 1] && cur[i] == cur[i + 2]) {
            size_t r = run_len(cur + i, rem);
            if (r > best) { best = r; bop = TFC_RUN; }
        }
        if (best) {
            if (end - o < 6) return 0;
            o = put_op(o, bop, best);
            if (bop == TFC_RUN) o = put_px(o, cur[i]);
            if (prev) memcpy(prev + i, cur + i, best * 2);
            i += best;
            continue;
        }
        /* literal: pixel i, then up to the next position where an op can start */
        size_t j = prev ? lit_end(cur, prev, i + 1, n, W, 1) : lit_end(cur, prev, i + 1, n, W, 0);
        if (!(o = flush_lit(o, end, cur, i, j))) return 0;
        if (prev) memcpy(prev + i, cur + i, (j - i) * 2);
        i = j;
    }
    return (size_t)(o - out);
}

int tfc_decode(const uint8_t *in, size_t len, const uint16_t *prev, uint16_t *out, int w, int h)
{
    if (w <= 0 || h <= 0) return -1;
    const size_t n = (size_t)w * (size_t)h, W = (size_t)w;
    const uint8_t *p = in, *end = in + len;
    size_t i = 0;
    while (i < n) {
        if (p >= end) return -2;
        unsigned b = *p++, op = b >> 5;
        size_t count = (b & 31u) + 1u;
        if ((b & 31u) == 31u) {
            size_t v = 0; unsigned sh = 0;
            for (;;) {
                if (p >= end || sh > 28) return -3;
                unsigned c = *p++;
                v |= (size_t)(c & 0x7f) << sh;
                sh += 7;
                if (!(c & 0x80)) break;
            }
            count = 32 + v;
        }
        size_t px = op == TFC_DLIT ? count * 2 : count;
        if (px > n - i) return -4;
        switch (op) {
        case TFC_SKIP:
            if (!prev) return -5;
            if (prev != out) memcpy(out + i, prev + i, count * 2);
            break;
        case TFC_UP:
            if (i < W) return -6;
            for (size_t k = 0; k < count;) {   /* non-overlapping chunks of <= W */
                size_t c = count - k < W ? count - k : W;
                memcpy(out + i + k, out + i + k - W, c * 2);
                k += c;
            }
            break;
        case TFC_RUN: {
            if (end - p < 2) return -7;
            uint16_t v = (uint16_t)(p[0] | (p[1] << 8)); p += 2;
            for (size_t k = 0; k < count; k++) out[i + k] = v;
            break;
        }
        case TFC_LIT:
            if ((size_t)(end - p) < count * 2) return -7;
            for (size_t k = 0; k < count; k++, p += 2) out[i + k] = (uint16_t)(p[0] | (p[1] << 8));
            break;
        case TFC_DLIT:
            if ((size_t)(end - p) < count * 2) return -7;
            for (size_t k = 0; k < count; k++, p += 2) {
                uint16_t v = (uint16_t)(p[0] | (p[1] << 8));
                out[i + 2 * k] = v; out[i + 2 * k + 1] = v;
            }
            break;
        default:
            return -8;
        }
        i += px;
    }
    return p == end ? 0 : -9;
}

void tfc_downscale2(const uint16_t *src, int w, int h, uint16_t *dst)
{
    const int ow = w / 2, oh = h / 2;
    for (int y = 0; y < oh; y++) {
        const uint16_t *r0 = src + (size_t)(2 * y) * (size_t)w, *r1 = r0 + w;
        uint16_t *d = dst + (size_t)y * (size_t)ow;
        for (int x = 0; x < ow; x++) {
            uint32_t a = r0[2 * x], b = r0[2 * x + 1], c = r1[2 * x], e = r1[2 * x + 1];
            /* R+B and G summed separately: every field has 2 bits of headroom
             * inside its own mask; +2 per channel rounds half up */
            uint32_t rb = (a & 0xF81Fu) + (b & 0xF81Fu) + (c & 0xF81Fu) + (e & 0xF81Fu) + 0x1002u;
            uint32_t g = (a & 0x07E0u) + (b & 0x07E0u) + (c & 0x07E0u) + (e & 0x07E0u) + 0x0040u;
            d[x] = (uint16_t)(((rb >> 2) & 0xF81Fu) | ((g >> 2) & 0x07E0u));
        }
    }
}
