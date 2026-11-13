/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Pavel Kotek
 *
 * tfsynth - PC test harness for the capture pipeline.
 *
 *   tfsynth stream OUT.tfr REFPREFIX [--scale N] [--fps N] [--seconds S]
 *                  [--bw BYTES_PER_S] [--stall] [--hard]
 *       Simulates a game (60 Hz RGB565 frames, 48 kHz stereo audio in 10 ms
 *       chunks) writing through the shim writer (tfcap.h) into an in-memory
 *       tfcap segment, while the recorder core (tfrec_core.c, the same code
 *       tfrec runs) polls every 5 ms and its output drains at --bw bytes/s.
 *       Writes the stream plus REFPREFIX.vid (every frame the shim stored:
 *       u32 seq, u32 w, u32 h, pixels) and REFPREFIX.pcm (all audio).
 *       Every whole second the picture flashes white for 2 frames and the
 *       audio has a 10 ms click at the same instant (A/V sync markers).
 *       --stall starves the recorder for 250 ms every 2 s; --hard makes
 *       t >= 5 s a dithered 3D scene (incompressible: exercises backlog).
 *
 *   tfsynth bench [FRAMES]
 *       Encoder/decoder speed and ratio on synthetic scenes.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif

#include "../tfcap.h"
#include "../tfcodec.h"
#include "../tfrec_core.h"

static double now_s(void)
{
#ifdef _WIN32
    LARGE_INTEGER f, c;
    QueryPerformanceFrequency(&f); QueryPerformanceCounter(&c);
    return (double)c.QuadPart / (double)f.QuadPart;
#else
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9;
#endif
}

static uint32_t rng = 12345;
static uint32_t xr(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }

static inline uint16_t rgb(int r, int g, int b) { return (uint16_t)(((r & 31) << 11) | ((g & 63) << 5) | (b & 31)); }

/* ---- scenes ---------------------------------------------------------- */
/* 2D platformer at 320x240: HUD, sky, parallax clouds, tiled ground, sprites */
static void scene_platformer(uint16_t *p, int w, int h, int f)
{
    for (int y = 0; y < h; y++) {
        uint16_t *row = p + y * w;
        for (int x = 0; x < w; x++) {
            uint16_t c;
            if (y < 16) {                                    /* HUD */
                c = rgb(2, 4, 6);
                if (y > 3 && y < 12 && (x % 8) < 6 && x < 120 && ((x / 8 * 7 + y) % 3)) c = rgb(31, 63, 31);
                if (y > 3 && y < 12 && x >= 240 && x < 240 + 48 && (((f / 6 + x / 8) * 5 + y) % 4) == 0) c = rgb(31, 50, 0);
            } else if (y < 150) {                            /* sky + clouds (scroll 1/2) */
                c = rgb(12, 40 + y / 8, 31);
                int cx = (x + f / 2) % 160, cy = y - 50;
                if (cy > 0 && cy < 24 && cx > 20 && cx < 80 && ((cx - 50) * (cx - 50) / 9 + (cy - 12) * (cy - 12)) < 120)
                    c = rgb(31, 63, 31);
            } else {                                         /* ground tiles (scroll 1) */
                int gx = x + f, tx = gx / 16, ty = (y - 150) / 16, ix = gx & 15, iy = (y - 150) & 15;
                int kind = ((tx * 7 + ty * 3) ^ (tx >> 2)) % 3;
                if (ty == 0) c = (iy < 4) ? rgb(4, 50, 4) : rgb(18, 30, 8);
                else if (kind == 0) c = (ix == 0 || iy == 0) ? rgb(10, 12, 6) : rgb(22, 26, 10);
                else if (kind == 1) c = ((ix + iy) & 4) ? rgb(20, 28, 9) : rgb(16, 22, 7);
                else c = rgb(18 + (ix & 1), 30, 8);
            }
            row[x] = c;
        }
    }
    for (int s = 0; s < 5; s++) {                            /* sprites */
        int sx = (int)(w / 2 + (w / 3) * sin(f * 0.03 + s * 1.3)) - 12;
        int sy = 120 + (int)(20 * sin(f * 0.11 + s)) - 12;
        for (int y = 0; y < 24; y++)
            for (int x = 0; x < 24; x++) {
                int X = sx + x, Y = sy + y;
                if (X < 0 || Y < 0 || X >= w || Y >= h) continue;
                int dx = x - 12, dy = y - 12;
                if (dx * dx + dy * dy < 120) p[Y * w + X] = (dx * dx + dy * dy < 30) ? rgb(31, 63, 0) : rgb(31, 10 * s, 4 * s);
            }
    }
}

/* menu: static gradient + text + blinking cursor */
static void scene_menu(uint16_t *p, int w, int h, int f)
{
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            uint16_t c = rgb(2, (y * 40) / h, 8 + (y * 20) / h);
            int line = (y - 60) / 24, ly = (y - 60) % 24;
            if (y >= 60 && line < 8 && ly > 4 && ly < 18 && x > 80 && x < 80 + 40 * (line + 3) && ((x * 3 + ly) % 7) < 4)
                c = rgb(28, 60, 28);
            if (y >= 60 && line == (f / 60) % 8 && x > 60 && x < 74 && ly > 6 && ly < 16 && ((f / 15) & 1)) c = rgb(31, 63, 0);
            p[y * w + x] = c;
        }
}

/* "3D": textured plane rotating, every pixel changes every frame */
static void scene_3d(uint16_t *p, int w, int h, int f)
{
    double a = f * 0.01, ca = cos(a), sa = sin(a);
    for (int y = 0; y < h; y++) {
        double z = 1.0 + (double)y / h * 3.0;
        for (int x = 0; x < w; x++) {
            double u = ((x - w / 2) * ca - 120 * sa) * z / w * 8, v = ((x - w / 2) * sa + 120 * ca) * z / w * 8 + f * 0.05;
            int iu = (int)floor(u), iv = (int)floor(v);
            int chk = (iu + iv) & 1;
            int shade = 8 + (int)(z * 5);
            p[y * w + x] = chk ? rgb(shade, shade * 2, 31 - shade / 2) : rgb(31 - shade / 2, shade, shade / 2);
        }
    }
}

/* PS1-like: textured, gouraud-shaded, ordered-dithered 3D (hard case) */
static void scene_3d_dither(uint16_t *p, int w, int h, int f)
{
    static const int bayer[4][4] = { { 0, 8, 2, 10 }, { 12, 4, 14, 6 }, { 3, 11, 1, 9 }, { 15, 7, 13, 5 } };
    double a = f * 0.01, ca = cos(a), sa = sin(a);
    for (int y = 0; y < h; y++) {
        double z = 1.0 + (double)y / h * 3.0;
        for (int x = 0; x < w; x++) {
            double u = ((x - w / 2) * ca - 120 * sa) * z / w * 8, v = ((x - w / 2) * sa + 120 * ca) * z / w * 8 + f * 0.05;
            double tex = 0.5 + 0.25 * sin(u * 3.1) * cos(v * 2.7) + 0.25 * sin((u + v) * 7.3);
            double lit = 0.35 + 0.65 * (1.0 - (double)y / h) * (0.8 + 0.2 * sin(x * 0.01 + f * 0.02));
            int d = bayer[y & 3][x & 3];
            int r = (int)(tex * lit * 31 * 16 + d) / 16, g = (int)(tex * lit * 0.8 * 63 * 16 + d) / 16, b = (int)((1 - tex) * lit * 31 * 16 + d) / 16;
            p[y * w + x] = rgb(r > 31 ? 31 : r, g > 63 ? 63 : g, b > 31 ? 31 : b);
        }
    }
}

static void scene_noise(uint16_t *p, int w, int h, int f)
{
    (void)f;
    for (int i = 0; i < w * h; i++) p[i] = (uint16_t)xr();
}

static void upscale2(const uint16_t *s, int w, int h, uint16_t *d)
{
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            uint16_t v = s[y * w + x];
            uint16_t *o = d + (2 * y) * (2 * w) + 2 * x;
            o[0] = o[1] = o[2 * w] = o[2 * w + 1] = v;
        }
}

/* timeline for the stream test: returns w,h and fills buf (pitch = *pitch bytes) */
static int g_hard;

static void render_timeline(double t, int f, uint16_t *buf, uint16_t *tmp, int *w, int *h, int *pitch)
{
    int sec = (int)t;
    if (g_hard && t >= 5.0) {
        scene_3d_dither(buf, 640, 480, f);
        *w = 640; *h = 480; *pitch = 1280;
    } else if (t < 4.0 || t >= 6.0) {                 /* 320x240 game upscaled 2x -> 640x480 */
        scene_platformer(tmp, 320, 240, f);
        upscale2(tmp, 320, 240, buf);
        *w = 640; *h = 480; *pitch = 1280;
    } else if (t < 5.0) {                      /* native 320x240 output, padded pitch */
        scene_menu(tmp, 320, 240, f);
        for (int y = 0; y < 240; y++) memcpy((uint8_t *)buf + y * 704, tmp + y * 320, 640);
        *w = 320; *h = 240; *pitch = 704;
    } else {                                   /* 640x480 "3D" */
        scene_3d(buf, 640, 480, f);
        *w = 640; *h = 480; *pitch = 1280;
    }
    /* sync marker: white for the first 2 frames of every second (t >= 1) */
    double frac = t - sec;
    if (sec >= 1 && frac < 2.0 / 60.0 - 1e-9)
        for (int y = 0; y < *h; y++)
            for (int x = 0; x < *w; x++) ((uint16_t *)((uint8_t *)buf + y * *pitch))[x] = 0xFFFF;
}

static int cmd_stream(int argc, char **argv)
{
    if (argc < 4) return 2;
    const char *out_path = argv[2], *ref = argv[3];
    struct tfrec_opts o = { .fps = 30, .scale = 1, .video = 1, .audio = 1, .keyint_s = 10 };
    double seconds = 8.0, bw = 6.0e6;
    int stall = 0;
    for (int i = 4; i < argc; i++) {
        if (!strcmp(argv[i], "--scale") && i + 1 < argc) o.scale = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--fps") && i + 1 < argc) o.fps = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--seconds") && i + 1 < argc) seconds = atof(argv[++i]);
        else if (!strcmp(argv[i], "--bw") && i + 1 < argc) bw = atof(argv[++i]);
        else if (!strcmp(argv[i], "--stall")) stall = 1;
        else if (!strcmp(argv[i], "--hard")) g_hard = 1;
        else return 2;
    }
    char p1[512], p2[512];
    snprintf(p1, sizeof p1, "%s.vid", ref); snprintf(p2, sizeof p2, "%s.pcm", ref);
    FILE *fo = fopen(out_path, "wb"), *fv = fopen(p1, "wb"), *fa = fopen(p2, "wb");
    if (!fo || !fv || !fa) { perror("fopen"); return 1; }

    uint32_t size = tfcap_layout_size();
    struct tfcap_hdr *h = calloc(1, size);
    tfcap_layout_init(h);
    static struct tfrec r;
    if (tfrec_init(&r, h, &o)) return 1;
    const uint64_t T0 = 1000000000000ull;               /* 1000 s, like a real monotonic clock */
    tfrec_stream_header(&r);
    tfrec_info(&r, TFS_INFO, T0 / 1000, "event=start harness=tfsynth");
    tfcap_publish(h, TFCAP_EN_VIDEO | TFCAP_EN_AUDIO, o.fps > 0 ? 1000000u / (uint32_t)o.fps : 0u);
    if (tfcap_validate(h, size) != 0) { fprintf(stderr, "validate failed\n"); return 1; }
    h->a_rate = 48000; h->a_channels = 2;            /* what the shim records from sound_driver_init */

    struct tfcap_wstate ws = { 0 };
    uint16_t *buf = malloc(704 * 480 * 2), *tmp = malloc(640 * 480 * 2);
    int16_t pcm[480 * 2];
    const uint64_t VP = 16666667ull, AP = 10000000ull, PP = 5000000ull;
    uint64_t end = T0 + (uint64_t)(seconds * 1e9), next_v = T0, next_a = T0, next_p = T0, next_info = T0 + 2000000000ull;
    uint64_t asample = 0;
    int frame = 0;
    double allowance = 0;
    uint32_t stored = 0;
    while (1) {
        uint64_t t = next_v < next_a ? next_v : next_a;
        if (next_p < t) t = next_p;
        if (t >= end) break;
        if (t == next_v) {
            int w, hh, pitch;
            render_timeline((double)(t - T0) / 1e9, frame, buf, tmp, &w, &hh, &pitch);
            if (tfcap_write_video(h, &ws, buf, w, hh, pitch, t)) {
                uint32_t hd[3] = { h->vseq, (uint32_t)w, (uint32_t)hh };
                fwrite(hd, 4, 3, fv);
                for (int y = 0; y < hh; y++) fwrite((uint8_t *)buf + y * pitch, 2, (size_t)w, fv);
                stored++;
            }
            frame++;
            next_v += VP;
        }
        if (t == next_a) {
            for (int i = 0; i < 480; i++, asample++) {
                double ts = (double)asample / 48000.0;
                int s = (int)ts;
                double l = 3000 * sin(2 * M_PI * 440 * ts), rr = 3000 * sin(2 * M_PI * 660 * ts);
                if (s >= 1 && ts - s < 0.010) l = rr = ((asample / 24) & 1) ? 28000 : -28000;  /* click */
                pcm[2 * i] = (int16_t)l; pcm[2 * i + 1] = (int16_t)rr;
            }
            tfcap_write_audio(h, pcm, sizeof pcm, t);
            fwrite(pcm, 1, sizeof pcm, fa);
            next_a += AP;
        }
        if (t == next_p) {
            double ts = (double)(t - T0) / 1e9;
            int stalled = stall && fmod(ts, 2.0) > 1.5 && fmod(ts, 2.0) < 1.75;   /* recorder starved 250 ms */
            if (!stalled) {
                h->heartbeat++;
                tfrec_poll(&r, t / 1000);
                if (t >= next_info) { tfrec_info(&r, TFS_INFO, t / 1000, NULL); next_info += 2000000000ull; }
                allowance += bw * (PP / 1e9);
                size_t n = tfrec_pending(&r);
                if ((double)n > allowance) n = (size_t)allowance;
                if (n) { fwrite(tfrec_out(&r), 1, n, fo); tfrec_consumed(&r, n); allowance -= (double)n; }
                if (!tfrec_pending(&r)) allowance = 0;           /* no credit while idle */
            }
            next_p += PP;
        }
    }
    h->enabled = 0;
    h->state = TFCAP_STATE_CLOSED;
    tfrec_poll(&r, end / 1000);
    tfrec_info(&r, TFS_END, end / 1000, "event=end reason=time");
    fwrite(tfrec_out(&r), 1, tfrec_pending(&r), fo);
    tfrec_consumed(&r, tfrec_pending(&r));
    fclose(fo); fclose(fv); fclose(fa);
    const struct tfrec_stats *s = &r.st;
    printf("stream: shim stored %u frames; sent %u (keys %u) lost %u backlog-skipped %u torn %u; "
           "audio chunks %u lost %u; video %.1f MB from %.1f MB raw (ratio %.2f); out %.2f MB\n",
           stored, s->v_sent, s->v_keys, s->v_lost, s->v_backlog, s->v_torn, s->a_sent, s->a_lost,
           s->v_bytes / 1e6, s->v_raw_bytes / 1e6, s->v_bytes ? (double)s->v_raw_bytes / s->v_bytes : 0,
           s->out_bytes / 1e6);
    tfrec_free(&r);
    free(h); free(buf); free(tmp);
    return 0;
}

typedef void (*scene_fn)(uint16_t *, int, int, int);

static int bench_one(const char *name, scene_fn fn, int base_w, int base_h, int up, int scale, int frames)
{
    int sw = base_w * (up ? 2 : 1), sh = base_h * (up ? 2 : 1);
    int ew = scale == 2 ? sw / 2 : sw, eh = scale == 2 ? sh / 2 : sh;
    size_t npix = (size_t)ew * eh, cap = TFC_MAX_BYTES(npix);
    uint16_t **src = malloc(sizeof(uint16_t *) * frames);
    uint16_t *tmp = malloc((size_t)base_w * base_h * 2), *prev = malloc(npix * 2), *dec = malloc(npix * 2), *scr = malloc(npix * 2);
    uint8_t *out = malloc(cap);
    for (int f = 0; f < frames; f++) {
        src[f] = malloc((size_t)sw * sh * 2);
        if (up) { fn(tmp, base_w, base_h, f * 2); upscale2(tmp, base_w, base_h, src[f]); }
        else fn(src[f], sw, sh, f * 2);           /* f*2: a 60 Hz game captured at 30 fps */
    }
    double te = 0, td = 0;
    uint64_t total = 0, keyb = 0;
    int ok = 1;
    for (int f = 0; f < frames; f++) {
        double t0 = now_s();
        const uint16_t *cur = src[f];
        if (scale == 2) { tfc_downscale2(src[f], sw, sh, scr); cur = scr; }
        size_t n = tfc_encode(cur, f ? prev : NULL, ew, eh, out, cap);
        if (!f) memcpy(prev, cur, npix * 2);
        double t1 = now_s();
        if (!n) { ok = 0; break; }
        if (tfc_decode(out, n, dec, dec, ew, eh) != 0 || memcmp(dec, cur, npix * 2)) { ok = 0; }
        double t2 = now_s();
        te += t1 - t0; td += t2 - t1;
        if (f) total += n; else keyb = n;
    }
    double raw = (double)npix * 2, avg = frames > 1 ? (double)total / (frames - 1) : 0;
    printf("%-22s %4dx%-4d key %6.1f KB (%.2fx)  delta avg %7.1f KB (%6.2fx)  %5.2f MB/s @30fps  "
           "enc %6.0f MB/s %5.2f ms/f  dec %6.0f MB/s  %s\n",
           name, ew, eh, keyb / 1024.0, raw / keyb, avg / 1024.0, avg > 0 ? raw / avg : 0, avg * 30 / 1e6,
           raw * frames / te / 1e6, te / frames * 1e3, raw * frames / td / 1e6, ok ? "bit-exact" : "MISMATCH");
    for (int f = 0; f < frames; f++) free(src[f]);
    free(src); free(tmp); free(prev); free(dec); free(scr); free(out);
    return ok ? 0 : 1;
}

static int cmd_bench(int argc, char **argv)
{
    int frames = argc > 2 ? atoi(argv[2]) : 60, bad = 0;
    for (int scale = 1; scale <= 2; scale++) {
        printf("--- scale %d (%d frames each, 60 Hz content sampled at 30 fps) ---\n", scale, frames);
        bad |= bench_one("2D platformer (2x up)", scene_platformer, 320, 240, 1, scale, frames);
        bad |= bench_one("menu (2x up)", scene_menu, 320, 240, 1, scale, frames);
        bad |= bench_one("2D platformer native", scene_platformer, 640, 480, 0, scale, frames);
        bad |= bench_one("3D plane 640x480", scene_3d, 640, 480, 0, scale, frames);
        bad |= bench_one("3D textured+dithered", scene_3d_dither, 640, 480, 0, scale, frames);
        bad |= bench_one("noise (worst case)", scene_noise, 640, 480, 0, scale, frames);
    }
    return bad;
}

int main(int argc, char **argv)
{
    if (argc >= 2 && !strcmp(argv[1], "stream")) return cmd_stream(argc, argv);
    if (argc >= 2 && !strcmp(argv[1], "bench")) return cmd_bench(argc, argv);
    fprintf(stderr, "usage: tfsynth stream OUT.tfr REFPREFIX [--scale N] [--fps N] [--seconds S] [--bw B/s] [--stall]\n"
                    "       tfsynth bench [FRAMES]\n");
    return 2;
}
