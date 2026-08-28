#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <dirent.h>
#include <linux/fb.h>
#include <setjmp.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <jpeglib.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/ioctl.h>
#include <sys/ipc.h>
#include <sys/mman.h>
#include <sys/msg.h>
#include <sys/shm.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include <ffplayer.h>
#include <hcuapi/dis.h>

extern unsigned char fontdata8x8[64 * 16];

#define THEME_FILE "/mnt/sdcard/cubegm/skin/skin.txt"
#define DEVICE_FILE "/tmp/tfdevice.env"
#define KEYMAP_FILE "/mnt/sdcard/frogui/keymap.txt"
#define MAX_PATH_LEN 512

enum { BTN_LEFT, BTN_RIGHT, BTN_A, BTN_B, BTN_X, BTN_Y, BTN_L1, BTN_R1, BTN_START, BTN_SELECT, BTN_COUNT };
static int key_bits[BTN_COUNT] = { 7, 5, 13, 14, 12, 15, 10, 11, 3, 0 };
static const char *key_names[BTN_COUNT] = { "LEFT", "RIGHT", "A", "B", "X", "Y", "L1", "R1", "START", "SELECT" };

typedef struct {
    int fd;
    unsigned char *mem;
    size_t mem_len;
    int fb_w, fb_h, pitch, bytespp;
    struct fb_var_screeninfo vi;
    int logical_w, logical_h;
    int rotation;
    uint32_t *canvas;
} Overlay;

typedef struct {
    uint32_t text;
    uint32_t accent;
    uint32_t selected_text;
    uint32_t background;
    bool background_enabled;
} Theme;

typedef enum { PLAY_SEQUENTIAL, PLAY_REPEAT, PLAY_RANDOM } PlaybackMode;

typedef struct {
    unsigned char *rgb;
    int width;
    int height;
    char temp_path[MAX_PATH_LEN];
} CoverState;

static volatile sig_atomic_t quit_requested;
static bool is_audio_path(const char *path);
static bool is_media_path(const char *path);

static void log_step(const char *step) {
    FILE *probe = fopen("/mnt/sdcard/log.txt", "r");
    if (!probe) return;
    fclose(probe);
    FILE *f = fopen("/mnt/sdcard/log.txt", "a");
    if (!f) return;
    fprintf(f, "VIDEO_PLAYER: %s\n", step);
    fflush(f);
    fsync(fileno(f));
    fclose(f);
}

static void log_message(long type, int val) {
    char line[96];
    snprintf(line, sizeof(line), "message type=%ld val=%d", type, val);
    log_step(line);
}

static void configure_video_layer(void) {
    int fd = open("/dev/dis", O_RDWR);
    if (fd < 0) { log_step("cannot open /dev/dis"); return; }
    /* Exact blend order used by the stock R36SX hcprojector:
     * GMA-S (fb1 HUD) > MAIN (decoded video) > GMA-F (fb0 UI) > AUX. */
    struct dis_layer_blend_order order;
    memset(&order, 0, sizeof(order));
    order.distype = DIS_TYPE_HD;
    order.main_layer = 2;
    order.auxp_layer = 0;
    order.gmas_layer = 3;
    order.gmaf_layer = 1;
    int rc = ioctl(fd, DIS_SET_LAYER_ORDER, &order);
    close(fd);
    log_step(rc == 0 ? "video layer placed above fb0" : "video layer order ioctl failed");
}

static int64_t now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

static void on_signal(int sig) {
    (void)sig;
    quit_requested = 1;
}

static void read_device_geometry(int *w, int *h, int *rotation) {
    FILE *f = fopen(DEVICE_FILE, "r");
    char line[128], key[64], value[64];
    *w = 640;
    *h = 480;
    *rotation = 0;
    if (!f) return;
    while (fgets(line, sizeof(line), f)) {
        if (sscanf(line, "%63[^=]=%63s", key, value) != 2) continue;
        if (!strcmp(key, "TF_PANEL_W")) *w = atoi(value);
        else if (!strcmp(key, "TF_PANEL_H")) *h = atoi(value);
        else if (!strcmp(key, "TF_ROTATE")) *rotation = atoi(value);
    }
    fclose(f);
    if (*w < 320 || *w > 1920) *w = 640;
    if (*h < 240 || *h > 1080) *h = 480;
    if (*rotation != 90 && *rotation != 180 && *rotation != 270) *rotation = 0;
}

static uint32_t parse_rgb(const char *s, uint32_t fallback) {
    char *end = NULL;
    unsigned long v = strtoul(s, &end, 0);
    return end != s ? (uint32_t)(v & 0xFFFFFFu) : fallback;
}

static Theme load_theme(void) {
    Theme t = { 0xF4F4F4, 0xFFFFFF, 0x101010, 0x101010, true };
    FILE *f = fopen(THEME_FILE, "r");
    char line[128], key[64], value[64];
    if (!f) return t;
    while (fgets(line, sizeof(line), f)) {
        if (sscanf(line, "%63[^=]=%63s", key, value) != 2) continue;
        if (!strcmp(key, "text_color")) t.text = parse_rgb(value, t.text);
        else if (!strcmp(key, "selection_color")) t.accent = parse_rgb(value, t.accent);
        else if (!strcmp(key, "sel_text_color")) t.selected_text = parse_rgb(value, t.selected_text);
        else if (!strcmp(key, "background_color")) t.background = parse_rgb(value, t.background);
    }
    fclose(f);
    f = fopen("/mnt/sdcard/frogui/music_player.txt", "r");
    if (f) {
        while (fgets(line, sizeof(line), f)) {
            if (sscanf(line, "%63[^=]=%63s", key, value) != 2) continue;
            if (!strcmp(key, "background")) t.background_enabled = !strcasecmp(value, "on");
            else if (!strcmp(key, "background_color")) t.background = parse_rgb(value, t.background);
        }
        fclose(f);
    }
    return t;
}

static PlaybackMode load_playback_mode(void) {
    FILE *f = fopen("/mnt/sdcard/frogui/music_player.txt", "r");
    char line[128], key[64], value[64];
    PlaybackMode mode = PLAY_SEQUENTIAL;
    if (!f) return mode;
    while (fgets(line, sizeof(line), f)) {
        if (sscanf(line, "%63[^=]=%63s", key, value) != 2) continue;
        if (!strcmp(key, "playback")) {
            if (!strcasecmp(value, "repeat") || !strcasecmp(value, "loop")) mode = PLAY_REPEAT;
            else if (!strcasecmp(value, "random") || !strcasecmp(value, "shuffle")) mode = PLAY_RANDOM;
        }
    }
    fclose(f);
    return mode;
}

static void save_playback_mode(PlaybackMode mode) {
    FILE *f = fopen("/mnt/sdcard/frogui/music_player.txt", "a");
    if (!f) return;
    fprintf(f, "playback=%s\n", mode == PLAY_REPEAT ? "loop" : mode == PLAY_RANDOM ? "random" : "sequential");
    fclose(f);
}

static void load_keymap(void) {
    FILE *f = fopen(KEYMAP_FILE, "r");
    char line[64], name[32];
    int bit;
    if (!f) return;
    while (fgets(line, sizeof(line), f)) {
        if (sscanf(line, "%31[^=]=%d", name, &bit) != 2) continue;
        for (int i = 0; i < BTN_COUNT; i++)
            if (!strcmp(name, key_names[i]) && bit >= 0 && bit < 32) key_bits[i] = bit;
    }
    fclose(f);
}

static volatile uint32_t *open_keys(void) {
    key_t key = ftok("/tmp/joy_key", 'a');
    if (key == (key_t)-1) return NULL;
    int id = shmget(key, 4, 0666);
    if (id < 0) return NULL;
    void *p = shmat(id, NULL, 0);
    return p == (void *)-1 ? NULL : (volatile uint32_t *)p;
}

static uint32_t logical_keys(volatile uint32_t *raw) {
    uint32_t in = raw ? (*raw & 0xFFFFu) : 0;
    uint32_t out = 0;
    for (int i = 0; i < BTN_COUNT; i++)
        if (in & (1u << key_bits[i])) out |= 1u << i;
    return out;
}

static int overlay_open(Overlay *o) {
    memset(o, 0, sizeof(*o));
    o->fd = -1;
    read_device_geometry(&o->logical_w, &o->logical_h, &o->rotation);
    o->fd = open("/dev/fb1", O_RDWR);
    if (o->fd < 0) return -1;
    struct fb_fix_screeninfo fi;
    if (ioctl(o->fd, FBIOGET_VSCREENINFO, &o->vi) < 0 ||
        ioctl(o->fd, FBIOGET_FSCREENINFO, &fi) < 0 || fi.smem_len == 0) goto fail;
    o->fb_w = o->vi.xres;
    o->fb_h = o->vi.yres;
    o->pitch = fi.line_length;
    o->bytespp = o->vi.bits_per_pixel / 8;
    o->mem_len = fi.smem_len;
    if (o->bytespp != 4 && o->bytespp != 2) goto fail;
    o->mem = mmap(NULL, o->mem_len, PROT_READ | PROT_WRITE, MAP_SHARED, o->fd, 0);
    if (o->mem == MAP_FAILED) { o->mem = NULL; goto fail; }
    o->canvas = calloc((size_t)o->logical_w * o->logical_h, sizeof(*o->canvas));
    if (!o->canvas) goto fail;
    /* fb1 is portrait-shaped on the portrait-mounted SF panels. Its memory
     * must receive the same clockwise transform as the decoded MAIN layer.
     * Trust the boot profile, but only rotate when the fb geometry agrees. */
    if (!(o->fb_w < o->fb_h && o->logical_w > o->logical_h)) o->rotation = 0;
    return 0;
fail:
    if (o->mem) munmap(o->mem, o->mem_len);
    if (o->fd >= 0) close(o->fd);
    free(o->canvas);
    memset(o, 0, sizeof(*o));
    o->fd = -1;
    return -1;
}

static void overlay_clear(Overlay *o) {
    if (o->mem) memset(o->mem, 0, o->mem_len);
    if (o->canvas) memset(o->canvas, 0, (size_t)o->logical_w * o->logical_h * 4);
}

static void overlay_close(Overlay *o) {
    overlay_clear(o);
    if (o->mem) munmap(o->mem, o->mem_len);
    if (o->fd >= 0) close(o->fd);
    free(o->canvas);
    memset(o, 0, sizeof(*o));
    o->fd = -1;
}

static uint32_t scale_channel(uint32_t c, const struct fb_bitfield *b) {
    if (!b->length) return 0;
    uint32_t max = (1u << b->length) - 1u;
    return ((c * max + 127u) / 255u) << b->offset;
}

static uint32_t pack_fb(const Overlay *o, uint32_t argb) {
    uint32_t a = argb >> 24, r = (argb >> 16) & 255, g = (argb >> 8) & 255, b = argb & 255;
    return scale_channel(r, &o->vi.red) | scale_channel(g, &o->vi.green) |
           scale_channel(b, &o->vi.blue) | scale_channel(a, &o->vi.transp);
}

static void overlay_present(Overlay *o) {
    if (!o->mem || !o->canvas) return;
    for (int fy = 0; fy < o->fb_h; fy++) {
        unsigned char *row = o->mem + (size_t)(fy + o->vi.yoffset) * o->pitch;
        for (int fx = 0; fx < o->fb_w; fx++) {
            int lx, ly;
            if (o->rotation == 90) {
                lx = fy * o->logical_w / o->fb_h;
                ly = o->logical_h - 1 - fx * o->logical_h / o->fb_w;
            } else if (o->rotation == 180) {
                lx = o->logical_w - 1 - fx * o->logical_w / o->fb_w;
                ly = o->logical_h - 1 - fy * o->logical_h / o->fb_h;
            } else if (o->rotation == 270) {
                lx = o->logical_w - 1 - fy * o->logical_w / o->fb_h;
                ly = fx * o->logical_h / o->fb_w;
            } else {
                lx = fx * o->logical_w / o->fb_w;
                ly = fy * o->logical_h / o->fb_h;
            }
            uint32_t p = pack_fb(o, o->canvas[(size_t)ly * o->logical_w + lx]);
            if (o->bytespp == 4) ((uint32_t *)row)[fx + o->vi.xoffset] = p;
            else ((uint16_t *)row)[fx + o->vi.xoffset] = (uint16_t)p;
        }
    }
}

static uint32_t argb(unsigned a, uint32_t rgb) { return (a << 24) | (rgb & 0xFFFFFFu); }

static void rect(Overlay *o, int x, int y, int w, int h, uint32_t color) {
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > o->logical_w) w = o->logical_w - x;
    if (y + h > o->logical_h) h = o->logical_h - y;
    if (w <= 0 || h <= 0) return;
    for (int yy = y; yy < y + h; yy++)
        for (int xx = x; xx < x + w; xx++) o->canvas[(size_t)yy * o->logical_w + xx] = color;
}

static void round_rect(Overlay *o, int x, int y, int w, int h, int r, uint32_t color) {
    rect(o, x + r, y, w - 2 * r, h, color);
    rect(o, x, y + r, w, h - 2 * r, color);
    for (int yy = 0; yy < r; yy++) for (int xx = 0; xx < r; xx++) {
        int dx = r - xx, dy = r - yy;
        if (dx * dx + dy * dy <= r * r) {
            rect(o, x + xx, y + yy, 1, 1, color);
            rect(o, x + w - 1 - xx, y + yy, 1, 1, color);
            rect(o, x + xx, y + h - 1 - yy, 1, 1, color);
            rect(o, x + w - 1 - xx, y + h - 1 - yy, 1, 1, color);
        }
    }
}

static int text_width(const char *s, int scale) { return (int)strlen(s) * 8 * scale; }

static void text_draw(Overlay *o, int x, int y, const char *s, int scale, uint32_t color, int max_w) {
    int start = x;
    for (; *s && x + 8 * scale <= start + max_w; s++, x += 8 * scale) {
        unsigned char c = (unsigned char)*s;
        if (c >= 128) c = '?';
        for (int row = 0; row < 8; row++) {
            unsigned char bits = fontdata8x8[c * 8 + row];
            for (int col = 0; col < 8; col++)
                if (bits & (0x80u >> col)) rect(o, x + col * scale, y + row * scale, scale, scale, color);
        }
    }
}

static void format_time(int64_t ms, char *out, size_t n) {
    if (ms < 0) ms = 0;
    long sec = (long)(ms / 1000);
    if (sec >= 3600) snprintf(out, n, "%ld:%02ld:%02ld", sec / 3600, (sec / 60) % 60, sec % 60);
    else snprintf(out, n, "%ld:%02ld", sec / 60, sec % 60);
}

static const char *display_name(const char *path, char *out, size_t n) {
    const char *base = strrchr(path, '/');
    base = base ? base + 1 : path;
    snprintf(out, n, "%s", base);
    char *dot = strrchr(out, '.');
    if (dot) *dot = '\0';
    return out;
}

static void folder_name(const char *path, char *out, size_t n) {
    char parent[MAX_PATH_LEN];
    snprintf(parent, sizeof(parent), "%s", path);
    char *slash = strrchr(parent, '/');
    if (!slash || slash == parent) { snprintf(out, n, "Music"); return; }
    *slash = '\0';
    slash = strrchr(parent, '/');
    snprintf(out, n, "%s", slash ? slash + 1 : parent);
}

typedef struct {
    char title[128];
    char artist[128];
    char album[128];
} TrackInfo;

static uint32_t id3_be32(const unsigned char *p);
static uint32_t id3_syncsafe(const unsigned char *p);

static void trim_field(char *s, size_t n) {
    s[n - 1] = '\0';
    size_t len = strlen(s);
    while (len && (s[len - 1] == ' ' || s[len - 1] == '\0')) s[--len] = '\0';
}

static void decode_id3_text(const unsigned char *data, size_t size, char *out, size_t out_size) {
    if (!size || out_size < 2) return;
    unsigned encoding = data[0];
    data++; size--;
    size_t used = 0;
    if (encoding == 1 || encoding == 2) {
        bool little_endian = encoding == 1 && size >= 2 && data[0] == 0xFF && data[1] == 0xFE;
        if (encoding == 1 && size >= 2 && ((data[0] == 0xFF && data[1] == 0xFE) ||
                                           (data[0] == 0xFE && data[1] == 0xFF))) {
            data += 2; size -= 2;
        }
        for (size_t i = 0; i + 1 < size && used + 1 < out_size; i += 2) {
            unsigned value = little_endian ? (unsigned)data[i] | ((unsigned)data[i + 1] << 8)
                                           : ((unsigned)data[i] << 8) | data[i + 1];
            if (!value) break;
            out[used++] = value >= 32 && value < 127 ? (char)value : '?';
        }
    } else {
        while (used < size && used + 1 < out_size && data[used]) {
            unsigned char value = data[used];
            out[used] = value >= 32 || value >= 0x80 ? (char)value : ' ';
            used++;
        }
    }
    out[used] = '\0';
    trim_field(out, out_size);
}

static void load_id3v2_metadata(FILE *f, TrackInfo *info) {
    unsigned char header[10];
    rewind(f);
    if (fread(header, 1, sizeof(header), f) != sizeof(header) || memcmp(header, "ID3", 3)) return;
    int version = header[3];
    if (version < 3 || version > 4) return;
    uint32_t tag_size = id3_syncsafe(header + 6);
    unsigned char *tag = malloc(tag_size);
    if (!tag || fread(tag, 1, tag_size, f) != tag_size) { free(tag); return; }
    size_t pos = 0;
    while (pos + 10 <= tag_size) {
        unsigned char *frame = tag + pos;
        if (!frame[0] || !frame[1] || !frame[2] || !frame[3]) break;
        uint32_t frame_size = version == 4 ? id3_syncsafe(frame + 4) : id3_be32(frame + 4);
        pos += 10;
        if (!frame_size || frame_size > tag_size - pos) break;
        if (!memcmp(frame, "TIT2", 4)) decode_id3_text(tag + pos, frame_size, info->title, sizeof(info->title));
        else if (!memcmp(frame, "TPE1", 4)) decode_id3_text(tag + pos, frame_size, info->artist, sizeof(info->artist));
        else if (!memcmp(frame, "TALB", 4)) decode_id3_text(tag + pos, frame_size, info->album, sizeof(info->album));
        pos += frame_size;
    }
    free(tag);
}

static void load_track_info(const char *path, TrackInfo *info) {
    memset(info, 0, sizeof(*info));
    FILE *f = fopen(path, "rb");
    if (!f) { display_name(path, info->title, sizeof(info->title)); return; }
    load_id3v2_metadata(f, info);
    if (fseek(f, -128, SEEK_END) == 0) {
        unsigned char tag[128];
        if (fread(tag, 1, sizeof(tag), f) == sizeof(tag) && !memcmp(tag, "TAG", 3)) {
            if (!info->title[0]) { memcpy(info->title, tag + 3, 30); trim_field(info->title, sizeof(info->title)); }
            if (!info->artist[0]) { memcpy(info->artist, tag + 33, 30); trim_field(info->artist, sizeof(info->artist)); }
            if (!info->album[0]) { memcpy(info->album, tag + 63, 30); trim_field(info->album, sizeof(info->album)); }
        }
    }
    fclose(f);
    if (!info->title[0]) display_name(path, info->title, sizeof(info->title));
    if (!info->album[0]) folder_name(path, info->album, sizeof(info->album));
}

static bool is_audio_path(const char *path) {
    const char *ext = strrchr(path, '.');
    if (!ext) return false;
    return !strcasecmp(ext, ".mp3") || !strcasecmp(ext, ".m4a") ||
           !strcasecmp(ext, ".aac") || !strcasecmp(ext, ".wav") ||
           !strcasecmp(ext, ".flac") || !strcasecmp(ext, ".ogg") ||
           !strcasecmp(ext, ".opus");
}

static bool is_media_path(const char *path) {
    const char *ext = strrchr(path, '.');
    if (!ext) return false;
    return is_audio_path(path) || !strcasecmp(ext, ".mp4") || !strcasecmp(ext, ".mkv") ||
           !strcasecmp(ext, ".avi") || !strcasecmp(ext, ".mov") || !strcasecmp(ext, ".m4v") ||
           !strcasecmp(ext, ".mpg") || !strcasecmp(ext, ".mpeg") || !strcasecmp(ext, ".ts") ||
           !strcasecmp(ext, ".webm") || !strcasecmp(ext, ".wmv");
}

static uint32_t id3_be32(const unsigned char *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}

static uint32_t id3_syncsafe(const unsigned char *p) {
    return ((uint32_t)(p[0] & 0x7F) << 21) | ((uint32_t)(p[1] & 0x7F) << 14) |
           ((uint32_t)(p[2] & 0x7F) << 7) | (p[3] & 0x7F);
}

/* Extract standard ID3v2 APIC artwork for the hardware image decoder. */
static bool extract_embedded_cover(const char *media_path, char *out, size_t out_size) {
    FILE *f = fopen(media_path, "rb");
    unsigned char header[10];
    if (!f || fread(header, 1, sizeof(header), f) != sizeof(header) || memcmp(header, "ID3", 3) != 0) {
        if (f) fclose(f);
        log_step("no ID3v2 tag for cover");
        return false;
    }
    int version = header[3];
    uint32_t tag_size = id3_syncsafe(header + 6);
    unsigned char *tag = malloc(tag_size);
    if (!tag || fread(tag, 1, tag_size, f) != tag_size) { free(tag); fclose(f); return false; }
    fclose(f);
    size_t pos = 0;
    while (pos + 10 <= tag_size) {
        unsigned char *frame = tag + pos;
        if (!frame[0] || !frame[1] || !frame[2] || !frame[3]) break;
        uint32_t frame_size = version >= 4 ? id3_syncsafe(frame + 4) : id3_be32(frame + 4);
        pos += 10;
        if (frame_size > tag_size - pos) break;
        if (!memcmp(frame, "APIC", 4) && frame_size > 5) {
            unsigned char *data = tag + pos;
            size_t i = 1;
            while (i < frame_size && data[i]) i++;
            if (i + 2 < frame_size) {
                i += 2; /* MIME terminator and picture type */
                /* APIC descriptions use the frame's declared text encoding.
                 * Latin-1 and UTF-8 have a one-byte terminator; UTF-16 and
                 * UTF-16BE have a two-byte terminator. */
                if (data[0] == 0 || data[0] == 3) {
                    while (i < frame_size && data[i]) i++;
                    if (i < frame_size) i++;
                } else {
                    while (i + 1 < frame_size && (data[i] || data[i + 1])) i += 2;
                    if (i + 1 < frame_size) i += 2;
                }
                if (i < frame_size) {
                    snprintf(out, out_size, "/tmp/treefrog-cover-%ld.jpg", (long)getpid());
                    FILE *cover = fopen(out, "wb");
                    if (cover) {
                        bool ok = fwrite(data + i, 1, frame_size - i, cover) == frame_size - i;
                        fclose(cover); free(tag);
                        log_step(ok ? "APIC cover extracted" : "APIC cover write failed");
                        return ok;
                    }
                }
            }
        }
        pos += frame_size;
    }
    free(tag);
    log_step("ID3v2 tag has no APIC frame");
    return false;
}

typedef struct { struct jpeg_error_mgr base; jmp_buf jump; } JpegError;

static void jpeg_fail(j_common_ptr cinfo) {
    JpegError *error = (JpegError *)cinfo->err;
    longjmp(error->jump, 1);
}

static bool cover_decode(CoverState *cover, const char *path, int target_side) {
    FILE *f = fopen(path, "rb");
    if (!f) return false;
    struct jpeg_decompress_struct decoder;
    JpegError error;
    memset(&decoder, 0, sizeof(decoder));
    decoder.err = jpeg_std_error(&error.base);
    error.base.error_exit = jpeg_fail;
    if (setjmp(error.jump)) {
        jpeg_destroy_decompress(&decoder);
        fclose(f);
        free(cover->rgb);
        cover->rgb = NULL;
        log_step("cover JPEG decode failed");
        return false;
    }
    jpeg_create_decompress(&decoder);
    jpeg_stdio_src(&decoder, f);
    jpeg_read_header(&decoder, TRUE);
    while (decoder.scale_denom < 8 &&
           (decoder.image_width / decoder.scale_denom > (unsigned)target_side * 2 ||
            decoder.image_height / decoder.scale_denom > (unsigned)target_side * 2))
        decoder.scale_denom *= 2;
    decoder.out_color_space = JCS_RGB;
    jpeg_start_decompress(&decoder);
    cover->width = (int)decoder.output_width;
    cover->height = (int)decoder.output_height;
    size_t stride = (size_t)cover->width * 3;
    cover->rgb = malloc(stride * (size_t)cover->height);
    if (!cover->rgb) longjmp(error.jump, 1);
    while (decoder.output_scanline < decoder.output_height) {
        JSAMPROW row = cover->rgb + (size_t)decoder.output_scanline * stride;
        jpeg_read_scanlines(&decoder, &row, 1);
    }
    jpeg_finish_decompress(&decoder);
    jpeg_destroy_decompress(&decoder);
    fclose(f);
    log_step("cover decoded into HUD framebuffer");
    return true;
}

static void cover_prepare(CoverState *cover, const char *media_path, int target_side) {
    memset(cover, 0, sizeof(*cover));
    if (extract_embedded_cover(media_path, cover->temp_path, sizeof(cover->temp_path)))
        cover_decode(cover, cover->temp_path, target_side);
}

static void cover_stop(CoverState *cover) {
    free(cover->rgb);
    if (cover->temp_path[0]) unlink(cover->temp_path);
    memset(cover, 0, sizeof(*cover));
}

static void draw_cover(Overlay *o, const CoverState *cover, int panel_y) {
    if (!cover || !cover->rgb || cover->width <= 0 || cover->height <= 0) return;
    int margin = o->logical_w / 28;
    int side = o->logical_w * 44 / 100;
    int available = panel_y - margin * 2;
    if (side > available) side = available;
    if (side <= 0) return;
    int x0 = (o->logical_w - side) / 2, y0 = margin;
    int radius = side / 18;
    for (int y = 0; y < side; y++) {
        for (int x = 0; x < side; x++) {
            int cx = x < radius ? radius - x : x >= side - radius ? x - (side - radius - 1) : 0;
            int cy = y < radius ? radius - y : y >= side - radius ? y - (side - radius - 1) : 0;
            if (cx && cy && cx * cx + cy * cy > radius * radius) continue;
            int sx = x * cover->width / side, sy = y * cover->height / side;
            const unsigned char *p = cover->rgb + ((size_t)sy * cover->width + sx) * 3;
            o->canvas[(size_t)(y0 + y) * o->logical_w + x0 + x] =
                0xFF000000u | ((uint32_t)p[0] << 16) | ((uint32_t)p[1] << 8) | p[2];
        }
    }
}

static int audio_path_compare(const void *a, const void *b) {
    return strcasecmp((const char *)a, (const char *)b);
}

static bool playlist_neighbor(const char *path, int delta, char *out, size_t out_size) {
    const char *slash = strrchr(path, '/');
    if (!slash) return false;
    char dir_path[MAX_PATH_LEN];
    size_t dir_len = (size_t)(slash - path);
    if (!dir_len || dir_len >= sizeof(dir_path)) return false;
    memcpy(dir_path, path, dir_len); dir_path[dir_len] = '\0';
    char tracks[256][MAX_PATH_LEN]; size_t count = 0;
    DIR *dp = opendir(dir_path); if (!dp) return false;
    struct dirent *e;
    while ((e = readdir(dp)) && count < 256) {
        if (e->d_name[0] == '.') continue;
        char candidate[MAX_PATH_LEN];
        snprintf(candidate, sizeof(candidate), "%s/%s", dir_path, e->d_name);
        struct stat st;
        if (is_media_path(candidate) && stat(candidate, &st) == 0 && S_ISREG(st.st_mode))
            snprintf(tracks[count++], sizeof(tracks[0]), "%s", candidate);
    }
    closedir(dp);
    if (count < 2) return false;
    qsort(tracks, count, sizeof(tracks[0]), audio_path_compare);
    size_t index = count;
    for (size_t i = 0; i < count; i++) if (!strcasecmp(tracks[i], path)) { index = i; break; }
    if (index == count) return false;
    size_t next = (size_t)((index + count + delta) % count);
    snprintf(out, out_size, "%s", tracks[next]);
    return true;
}

static bool first_media_in_folder(const char *folder, char *out, size_t out_size) {
    char tracks[256][MAX_PATH_LEN]; size_t count = 0;
    DIR *dp = opendir(folder); if (!dp) return false;
    struct dirent *e;
    while ((e = readdir(dp)) && count < 256) {
        if (e->d_name[0] == '.') continue;
        char candidate[MAX_PATH_LEN];
        snprintf(candidate, sizeof(candidate), "%s/%s", folder, e->d_name);
        struct stat st;
        if (is_media_path(candidate) && stat(candidate, &st) == 0 && S_ISREG(st.st_mode))
            snprintf(tracks[count++], sizeof(tracks[0]), "%s", candidate);
    }
    closedir(dp);
    if (!count) return false;
    qsort(tracks, count, sizeof(tracks[0]), audio_path_compare);
    snprintf(out, out_size, "%s", tracks[0]);
    return true;
}

static bool random_media_neighbor(const char *path, char *out, size_t out_size) {
    const char *slash = strrchr(path, '/');
    if (!slash) return false;
    char dir_path[MAX_PATH_LEN];
    size_t dir_len = (size_t)(slash - path);
    if (!dir_len || dir_len >= sizeof(dir_path)) return false;
    memcpy(dir_path, path, dir_len); dir_path[dir_len] = '\0';
    char tracks[256][MAX_PATH_LEN]; size_t count = 0;
    DIR *dp = opendir(dir_path); if (!dp) return false;
    struct dirent *e;
    while ((e = readdir(dp)) && count < 256) {
        if (e->d_name[0] == '.') continue;
        char candidate[MAX_PATH_LEN];
        snprintf(candidate, sizeof(candidate), "%s/%s", dir_path, e->d_name);
        struct stat st;
        if (is_media_path(candidate) && stat(candidate, &st) == 0 && S_ISREG(st.st_mode) && strcasecmp(candidate, path))
            snprintf(tracks[count++], sizeof(tracks[0]), "%s", candidate);
    }
    closedir(dp);
    if (!count) return false;
    snprintf(out, out_size, "%s", tracks[(size_t)rand() % count]);
    return true;
}

static void draw_hud(Overlay *o, Theme t, const TrackInfo *info, int64_t pos, int64_t duration,
                     bool paused, PlaybackMode playback, const char *status,
                     const CoverState *cover, bool opaque_background) {
    if (!o->canvas) return;
    uint32_t clear = opaque_background ? argb(255, t.background) : 0;
    for (size_t i = 0; i < (size_t)o->logical_w * o->logical_h; i++) o->canvas[i] = clear;
    int scale = o->logical_w >= 800 ? 2 : 1;
    int margin = o->logical_w / 28;
    int panel_h = scale == 2 ? 136 : 112;
    int panel_y = o->logical_h - panel_h - margin;
    draw_cover(o, cover, panel_y);
    round_rect(o, margin, panel_y, o->logical_w - margin * 2, panel_h, 24, argb(232, 0x101010));

    char title[256], byline[256], times[64];
    snprintf(title, sizeof(title), "%s", info->title);
    if (info->artist[0] && info->album[0])
        snprintf(byline, sizeof(byline), "%s  |  %s", info->artist, info->album);
    else if (info->artist[0]) snprintf(byline, sizeof(byline), "%s", info->artist);
    else snprintf(byline, sizeof(byline), "%s", info->album);
    format_time(pos, times, sizeof(times));
    size_t used = strlen(times);
    snprintf(times + used, sizeof(times) - used, " / ");
    format_time(duration, times + strlen(times), sizeof(times) - strlen(times));

    int left = margin + 18;
    int right = o->logical_w - margin - 18;
    const char *mode_label = playback == PLAY_REPEAT ? "LOOP" : playback == PLAY_RANDOM ? "RANDOM" : "SEQUENTIAL";
    text_draw(o, left, panel_y - 20, mode_label, scale, argb(255, t.accent), right - left);
    text_draw(o, left, panel_y + 12, title, scale, argb(255, t.text), right - left);
    int tw = text_width(times, scale);
    text_draw(o, right - tw, panel_y + 10, times, scale, argb(255, t.text), tw);

    if (byline[0])
        text_draw(o, left, panel_y + (scale == 2 ? 38 : 30), byline, scale,
                  argb(255, t.accent), right - left);

    int bar_y = panel_y + (scale == 2 ? 68 : 54);
    round_rect(o, left, bar_y, right - left, 10, 5, argb(255, 0x3A3A3A));
    int fill = duration > 0 ? (int)((right - left) * pos / duration) : 0;
    if (fill > right - left) fill = right - left;
    if (fill > 0) round_rect(o, left, bar_y, fill, 10, 5, argb(255, t.accent));

    const char *help = "A PAUSE   X/Y TRACK   SELECT MODE   B BACK";
    text_draw(o, left, bar_y + 26, help, scale, argb(190, t.text), right - left);
    int mode_width = text_width(mode_label, scale) + 20;
    round_rect(o, left, panel_y - 38, mode_width, 26, 13, argb(235, t.accent));
    text_draw(o, left + 10, panel_y - 31, mode_label, scale, argb(255, t.selected_text), mode_width - 20);
    if (status && *status) {
        int sw = text_width(status, scale) + 24;
        round_rect(o, (o->logical_w - sw) / 2, panel_y - 46, sw, 34, 10, argb(245, t.accent));
        text_draw(o, (o->logical_w - text_width(status, scale)) / 2, panel_y - 38,
                  status, scale, argb(255, t.selected_text), sw);
    } else if (paused) {
        const char *label = "PAUSED";
        int sw = text_width(label, scale) + 24;
        round_rect(o, (o->logical_w - sw) / 2, panel_y - 46, sw, 34, 10, argb(245, t.accent));
        text_draw(o, (o->logical_w - text_width(label, scale)) / 2, panel_y - 38,
                  label, scale, argb(255, t.selected_text), sw);
    }
    overlay_present(o);
}

static bool player_error(long type, bool audio_only) {
    return type == HCPLAYER_MSG_OPEN_FILE_FAILED || type == HCPLAYER_MSG_UNSUPPORT_FORMAT ||
           (!audio_only && (type == HCPLAYER_MSG_UNSUPPORT_ALL_VIDEO ||
                            type == HCPLAYER_MSG_VIDEO_DECODE_ERR)) ||
           type == HCPLAYER_MSG_ERR_UNDEFINED || type == HCPLAYER_MSG_READ_TIMEOUT;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    char folder_entry[MAX_PATH_LEN];
    struct stat launch_stat;
    if (stat(argv[1], &launch_stat) == 0 && S_ISDIR(launch_stat.st_mode)) {
        if (!first_media_in_folder(argv[1], folder_entry, sizeof(folder_entry))) return 2;
        argv[1] = folder_entry;
    }
    bool audio_only = is_audio_path(argv[1]);
    log_step("process started");
    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);
    load_keymap();
    Theme theme = load_theme();
    srand((unsigned)time(NULL) ^ (unsigned)getpid());
    PlaybackMode playback = load_playback_mode();
    TrackInfo track_info;
    load_track_info(argv[1], &track_info);
    bool restart_requested = false;
    char restart_path[MAX_PATH_LEN] = "";
    volatile uint32_t *raw_keys = open_keys();
    Overlay overlay;
    bool have_overlay = overlay_open(&overlay) == 0;
    int panel_rotation = 0, panel_w = 0, panel_h = 0;
    read_device_geometry(&panel_w, &panel_h, &panel_rotation);
    char geometry_log[128];
    snprintf(geometry_log, sizeof(geometry_log),
             "panel=%dx%d rotate=%d fb1=%dx%d",
             panel_w, panel_h, panel_rotation,
             have_overlay ? overlay.fb_w : 0, have_overlay ? overlay.fb_h : 0);
    log_step(geometry_log);
    log_step(have_overlay ? "fb1 overlay ready" : "fb1 overlay unavailable");
    if (have_overlay) overlay_clear(&overlay);

    int msg_id = msgget(IPC_PRIVATE, 0600 | IPC_CREAT);
    if (msg_id < 0) msg_id = -1;
    log_step("calling hcplayer_init");
    if (hcplayer_init(LOG_WARNING) != 0) {
        log_step("hcplayer_init failed");
        if (have_overlay) draw_hud(&overlay, theme, &track_info, 0, 0, true, playback,
                                   "PLAYER INIT FAILED", NULL,
                                   audio_only && theme.background_enabled);
        sleep(3);
        goto done;
    }
    log_step("hcplayer_init returned");

    /* The R36SX/SF3000 stock player passes a 248-byte init block, while the
     * public SDK header describes an older 224-byte prefix. The field offsets
     * in that prefix match, but passing only sizeof(HCPlayerInitArgs) leaves
     * the firmware's appended fields as random stack data. Keep the known
     * prefix typed and guarantee the complete firmware block is zeroed. */
    union {
        long double alignment;
        unsigned char raw[256];
    } args_storage;
    memset(&args_storage, 0, sizeof(args_storage));
    HCPlayerInitArgs *args = (HCPlayerInitArgs *)args_storage.raw;
    args->uri = argv[1];
    args->msg_id = msg_id;
    args->sync_type = HCPLAYER_AUDIO_MASTER;
    if (panel_rotation) {
        args->rotate_enable = true;
        args->rotate_type = (rotate_type_e)(panel_rotation / 90);
    }
    /* Match the stock hcprojector player setup. quick_mode and audsink are
     * intentionally left disabled; the firmware's audio-master path owns the
     * decoder/I2SO devices directly. */
    /* Audio must never own the decoded-video plane. Album art is decoded once
     * and composited into fb1 with the HUD, avoiding two hardware players
     * racing to display the attached picture. */
    args->bg_disable = true;
    args->play_attached_file = 0;
    args->snd_devs = AUDDEV_I2SO;

    log_step("calling hcplayer_create");
    void *player = hcplayer_create(args);
    if (!player) {
        if (have_overlay) draw_hud(&overlay, theme, &track_info, 0, 0, true, playback,
                                   audio_only ? "CANNOT OPEN AUDIO" : "CANNOT OPEN VIDEO", NULL,
                                   audio_only && theme.background_enabled);
        sleep(3);
        hcplayer_deinit();
        goto done;
    }
    log_step("hcplayer_create returned");
    configure_video_layer();
    hcplayer_play(player);
    CoverState cover = {0};
    if (audio_only && have_overlay)
        cover_prepare(&cover, argv[1], overlay.logical_w * 44 / 100);
    log_step("playback started");

    uint32_t previous = logical_keys(raw_keys);
    /* Seed edge detection with the launch button's current state. There is no
     * need to wait for every raw bit to clear: a stale cubevol bit could make
     * that guard permanent, whereas seeding prevents the A press leaking in. */
    log_step("entering playback loop");
    bool paused = false, eos = false;
    int64_t fatal_at = 0;
    int64_t playback_started_at = now_ms();
    int64_t hud_until = playback_started_at + 4500;
    int64_t last_draw = 0;
    bool first_frame = false;
    const char *status = NULL;

    while (!quit_requested && !eos) {
        HCPlayerMsg msg;
        if (msg_id >= 0) while (msgrcv(msg_id, &msg, sizeof(msg) - sizeof(long), 0, IPC_NOWAIT) >= 0) {
            log_message(msg.type, msg.val);
            if (msg.type == HCPLAYER_MSG_STATE_EOS) eos = true;
            else if (msg.type == HCPLAYER_MSG_FIRST_VIDEO_FRAME_DECODED ||
                     msg.type == HCPLAYER_MSG_FIRST_VIDEO_FRAME_SHOWED) first_frame = true;
            else if (player_error(msg.type, audio_only)) {
                status = audio_only ? "UNSUPPORTED AUDIO" : "UNSUPPORTED VIDEO";
                fatal_at = now_ms() + 3500;
                hud_until = fatal_at;
            }
        }

        uint32_t keys = logical_keys(raw_keys);
        uint32_t pressed = keys & ~previous;
        previous = keys;
        int64_t pos = hcplayer_get_position(player);
        int64_t duration = hcplayer_get_duration(player);
        int64_t now = now_ms();

        /* Never strand the user on a broken firmware decode path. Position
         * advancement is also accepted because some library builds omit the
         * first-frame messages. */
        if (pos > 250) first_frame = true;
        if (!first_frame && now - playback_started_at > 10000) {
            log_step(audio_only ? "startup watchdog: no audio progress" :
                                  "startup watchdog: no video frame");
            if (have_overlay)
                draw_hud(&overlay, theme, &track_info, pos, duration, true, playback,
                         audio_only ? "AUDIO START FAILED" : "VIDEO START FAILED", &cover,
                         audio_only && theme.background_enabled);
            sleep(2);
            break;
        }

        if (pressed & (1u << BTN_B)) break;
        if (pressed & (1u << BTN_SELECT)) {
            playback = (PlaybackMode)((playback + 1) % 3);
            save_playback_mode(playback);
            status = playback == PLAY_REPEAT ? "LOOP" : playback == PLAY_RANDOM ? "RANDOM" : "SEQUENTIAL";
            hud_until = now + 2500;
        }
        if ((pressed & (1u << BTN_X)) &&
            playlist_neighbor(argv[1], -1, restart_path, sizeof(restart_path))) {
            restart_requested = true;
            break;
        }
        if ((pressed & (1u << BTN_Y)) &&
            playlist_neighbor(argv[1], 1, restart_path, sizeof(restart_path))) {
            restart_requested = true;
            break;
        }
        if (pressed & ((1u << BTN_A) | (1u << BTN_START))) {
            paused = !paused;
            if (paused) hcplayer_pause(player); else hcplayer_resume(player);
            status = NULL;
            hud_until = now + 3500;
        }
        int64_t jump = 0;
        if (pressed & (1u << BTN_LEFT)) jump = -10000;
        if (pressed & (1u << BTN_RIGHT)) jump = 10000;
        if (pressed & (1u << BTN_L1)) jump = -60000;
        if (pressed & (1u << BTN_R1)) jump = 60000;
        if (jump) {
            int64_t target = pos + jump;
            if (target < 0) target = 0;
            if (duration > 0 && target > duration - 250) target = duration - 250;
            hcplayer_seek(player, target);
            if (paused) { hcplayer_pause(player); }
            status = jump > 0 ? "SEEK FORWARD" : "SEEK BACK";
            hud_until = now + 2500;
        }
        if (paused) hud_until = now + 1000;

        int64_t draw_interval = audio_only ? 1000 : 200;
        if (audio_only) hud_until = now + 1500;
        if (have_overlay && now < hud_until && now - last_draw >= draw_interval) {
            draw_hud(&overlay, theme, &track_info, pos, duration, paused, playback, status,
                     &cover, audio_only && theme.background_enabled);
            last_draw = now;
        } else if (have_overlay && last_draw && now >= hud_until) {
            overlay_clear(&overlay);
            last_draw = 0;
        }
        if (duration > 1000 && pos >= duration - 150 && !paused) {
            if (playback == PLAY_REPEAT) {
                snprintf(restart_path, sizeof(restart_path), "%s", argv[1]);
                restart_requested = true;
            } else if (playback == PLAY_RANDOM) {
                if (random_media_neighbor(argv[1], restart_path, sizeof(restart_path))) restart_requested = true;
            } else if (playlist_neighbor(argv[1], 1, restart_path, sizeof(restart_path))) {
                restart_requested = true;
            }
            eos = true;
        }
        if (fatal_at && now >= fatal_at) break;
        usleep(20000);
    }

    hcplayer_stop2(player, true, true);
    cover_stop(&cover);
    log_step("playback stopped");
    hcplayer_deinit();

done:
    if (msg_id >= 0) msgctl(msg_id, IPC_RMID, NULL);
    if (raw_keys) shmdt((void *)raw_keys);
    if (have_overlay) overlay_close(&overlay);
    if (restart_requested && restart_path[0]) {
        execl(argv[0], argv[0], restart_path, (char *)NULL);
        return 127;
    }
    return 0;
}
