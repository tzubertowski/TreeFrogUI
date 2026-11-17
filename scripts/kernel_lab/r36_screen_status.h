/* SPDX-License-Identifier: GPL-2.0
 * Minimal self-contained RGB565 framebuffer status screen (5x7 2x-scaled font
 * + progress bar) for on-console Check Disk / boot error reporting on R36S.
 */
#ifndef R36_SCREEN_STATUS_H
#define R36_SCREEN_STATUS_H

#include <stdint.h>
#include <string.h>

#ifndef R36_SCREEN_STATUS_MOCK
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#endif

#ifndef O_RDWR
#define O_RDWR 2
#endif
#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif
#ifndef PROT_READ
#define PROT_READ 1
#endif
#ifndef PROT_WRITE
#define PROT_WRITE 2
#endif
#ifndef MAP_SHARED
#define MAP_SHARED 1
#endif
#ifndef MAP_FAILED
#define MAP_FAILED ((void *)(-1))
#endif

#define R36_FB_WIDTH  640
#define R36_FB_HEIGHT 480

enum r36_screen_tone {
    R36_SCREEN_INFO = 0,
    R36_SCREEN_WARN = 1,
    R36_SCREEN_OK   = 2,
    R36_SCREEN_ERR  = 3
};

/* Compact 5x7 column-major bitmap font for space, punctuation, 0-9, A-Z */
static inline void r36_font_glyph5x7(char ch, uint8_t cols[5])
{
    static const uint8_t sp[5] = {0x00, 0x00, 0x00, 0x00, 0x00};
    static const uint8_t dash[5] = {0x08, 0x08, 0x08, 0x08, 0x08};
    static const uint8_t dot[5] = {0x00, 0x60, 0x60, 0x00, 0x00};
    static const uint8_t colon[5] = {0x00, 0x36, 0x36, 0x00, 0x00};
    static const uint8_t slash[5] = {0x20, 0x10, 0x08, 0x04, 0x02};
    static const uint8_t pct[5] = {0x23, 0x13, 0x08, 0x64, 0x62};
    static const uint8_t bang[5] = {0x00, 0x00, 0x5f, 0x00, 0x00};
    static const uint8_t lbr[5] = {0x00, 0x7f, 0x41, 0x41, 0x00};
    static const uint8_t rbr[5] = {0x00, 0x41, 0x41, 0x7f, 0x00};
    static const uint8_t digits[10][5] = {
        {0x3e, 0x51, 0x49, 0x45, 0x3e}, {0x00, 0x42, 0x7f, 0x40, 0x00},
        {0x42, 0x61, 0x51, 0x49, 0x46}, {0x21, 0x41, 0x45, 0x4b, 0x31},
        {0x18, 0x14, 0x12, 0x7f, 0x10}, {0x27, 0x45, 0x45, 0x45, 0x39},
        {0x3c, 0x4a, 0x49, 0x49, 0x30}, {0x01, 0x71, 0x09, 0x05, 0x03},
        {0x36, 0x49, 0x49, 0x49, 0x36}, {0x06, 0x49, 0x49, 0x29, 0x1e},
    };
    static const uint8_t alpha[26][5] = {
        {0x7e, 0x11, 0x11, 0x11, 0x7e}, {0x7f, 0x49, 0x49, 0x49, 0x36},
        {0x3e, 0x41, 0x41, 0x41, 0x22}, {0x7f, 0x41, 0x41, 0x22, 0x1c},
        {0x7f, 0x49, 0x49, 0x49, 0x41}, {0x7f, 0x09, 0x09, 0x09, 0x01},
        {0x3e, 0x41, 0x49, 0x49, 0x7a}, {0x7f, 0x08, 0x08, 0x08, 0x7f},
        {0x00, 0x41, 0x7f, 0x41, 0x00}, {0x20, 0x40, 0x41, 0x3f, 0x01},
        {0x7f, 0x08, 0x14, 0x22, 0x41}, {0x7f, 0x40, 0x40, 0x40, 0x40},
        {0x7f, 0x02, 0x0c, 0x02, 0x7f}, {0x7f, 0x04, 0x08, 0x10, 0x7f},
        {0x3e, 0x41, 0x41, 0x41, 0x3e}, {0x7f, 0x09, 0x09, 0x09, 0x06},
        {0x3e, 0x41, 0x51, 0x21, 0x5e}, {0x7f, 0x09, 0x19, 0x29, 0x46},
        {0x46, 0x49, 0x49, 0x49, 0x31}, {0x01, 0x01, 0x7f, 0x01, 0x01},
        {0x3f, 0x40, 0x40, 0x40, 0x3f}, {0x1f, 0x20, 0x40, 0x20, 0x1f},
        {0x3f, 0x40, 0x38, 0x40, 0x3f}, {0x63, 0x14, 0x08, 0x14, 0x63},
        {0x07, 0x08, 0x70, 0x08, 0x07}, {0x61, 0x51, 0x49, 0x45, 0x43},
    };
    const uint8_t *src = sp;
    if (ch >= 'a' && ch <= 'z') ch = (char)(ch - 'a' + 'A');
    if (ch >= '0' && ch <= '9') src = digits[ch - '0'];
    else if (ch >= 'A' && ch <= 'Z') src = alpha[ch - 'A'];
    else if (ch == '-') src = dash;
    else if (ch == '.') src = dot;
    else if (ch == ':') src = colon;
    else if (ch == '/') src = slash;
    else if (ch == '%') src = pct;
    else if (ch == '!') src = bang;
    else if (ch == '[') src = lbr;
    else if (ch == ']') src = rbr;
    memcpy(cols, src, 5);
}

static inline void r36_fb_fill_rect(uint16_t *fb, int x, int y, int w, int h, uint16_t color)
{
    int row, col;
    if (!fb) return;
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > R36_FB_WIDTH) w = R36_FB_WIDTH - x;
    if (y + h > R36_FB_HEIGHT) h = R36_FB_HEIGHT - y;
    for (row = y; row < y + h; row++) {
        uint16_t *line = fb + (size_t)row * R36_FB_WIDTH;
        for (col = x; col < x + w; col++)
            line[col] = color;
    }
}

static inline void r36_fb_draw_text(uint16_t *fb, int x, int y, const char *text,
                                    uint16_t fg, int scale)
{
    int cx = x;
    if (!fb || !text || scale < 1) return;
    for (; *text; text++) {
        uint8_t cols[5];
        int c, r;
        if (cx + 6 * scale > R36_FB_WIDTH) break;
        r36_font_glyph5x7(*text, cols);
        for (c = 0; c < 5; c++) {
            for (r = 0; r < 7; r++) {
                if (cols[c] & (1u << r))
                    r36_fb_fill_rect(fb, cx + c * scale, y + r * scale, scale, scale, fg);
            }
        }
        cx += 6 * scale;
    }
}

static inline void r36_screen_render_buffer(uint16_t *fb, enum r36_screen_tone tone,
                                            const char *title, const char *line1,
                                            const char *line2, int progress_pct)
{
    uint16_t bg = 0x0842u;
    uint16_t bar_fg = 0x07E0u;
    uint16_t border = 0xBDF7u;

    if (!fb) return;
    if (tone == R36_SCREEN_INFO) { bg = 0x0010u; bar_fg = 0x05BFu; }
    else if (tone == R36_SCREEN_WARN) { bg = 0x3180u; bar_fg = 0xFFE0u; }
    else if (tone == R36_SCREEN_OK) { bg = 0x0260u; bar_fg = 0x07E0u; }
    else if (tone == R36_SCREEN_ERR) { bg = 0x6000u; bar_fg = 0xF800u; }

    if (progress_pct < 0) progress_pct = 0;
    if (progress_pct > 100) progress_pct = 100;

    r36_fb_fill_rect(fb, 0, 0, R36_FB_WIDTH, R36_FB_HEIGHT, bg);
    r36_fb_fill_rect(fb, 32, 48, R36_FB_WIDTH - 64, 4, border);
    r36_fb_fill_rect(fb, 32, R36_FB_HEIGHT - 52, R36_FB_WIDTH - 64, 4, border);

    r36_fb_draw_text(fb, 48, 84, title ? title : "[R36S CHKDSK]", 0xFFFFu, 3);
    if (line1) r36_fb_draw_text(fb, 48, 168, line1, 0xFFFFu, 2);
    if (line2) r36_fb_draw_text(fb, 48, 212, line2, 0xDEFBu, 2);

    /* Progress bar track and fill */
    r36_fb_fill_rect(fb, 48, 300, R36_FB_WIDTH - 96, 32, 0x2104u);
    if (progress_pct > 0) {
        int fill_w = ((R36_FB_WIDTH - 104) * progress_pct) / 100;
        r36_fb_fill_rect(fb, 52, 304, fill_w, 24, bar_fg);
    }
}

static inline int r36_screen_status_show(const char *fb_path, enum r36_screen_tone tone,
                                         const char *title, const char *line1,
                                         const char *line2, int progress_pct)
{
    size_t fb_bytes = (size_t)R36_FB_WIDTH * (size_t)R36_FB_HEIGHT * sizeof(uint16_t);
    int fd;
    void *map;

    if (!fb_path) return -1;
    fd = open(fb_path, O_RDWR | O_CLOEXEC);
    if (fd < 0) return -1;
    map = mmap(NULL, fb_bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) {
        close(fd);
        return -1;
    }
    r36_screen_render_buffer((uint16_t *)map, tone, title, line1, line2, progress_pct);
    munmap(map, fb_bytes);
    close(fd);
    return 0;
}

#endif
