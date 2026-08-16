#define _GNU_SOURCE

#include <dirent.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/ioctl.h>
#include <sys/ipc.h>
#include <sys/mman.h>
#include <sys/msg.h>
#include <sys/shm.h>
#include <time.h>
#include <unistd.h>

#include <ffplayer.h>
#include <hcuapi/dis.h>

extern unsigned char fontdata8x8[64 * 16];

#define THEME_FILE "/mnt/sdcard/cubegm/skin/skin.txt"
#define DEVICE_FILE "/tmp/tfdevice.env"
#define KEYMAP_FILE "/mnt/sdcard/frogui/keymap.txt"

enum { BTN_LEFT, BTN_RIGHT, BTN_A, BTN_B, BTN_L1, BTN_R1, BTN_X, BTN_Y, BTN_SELECT, BTN_COUNT };
static int key_bits[BTN_COUNT] = { 7, 5, 13, 14, 10, 11, 12, 15, 0 };
static const char *key_names[BTN_COUNT] = { "LEFT", "RIGHT", "A", "B", "L1", "R1", "X", "Y", "SELECT" };

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

typedef struct { uint32_t text, accent, selected_text; } Theme;
typedef struct { char **path; int count, current; } ImageList;

static volatile sig_atomic_t quit_requested;

static int64_t now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

static void on_signal(int sig) { (void)sig; quit_requested = 1; }

static void configure_image_layer(void) {
    int fd = open("/dev/dis", O_RDWR);
    if (fd < 0) return;
    struct dis_layer_blend_order order;
    memset(&order, 0, sizeof(order));
    order.distype = DIS_TYPE_HD;
    order.main_layer = 2;
    order.auxp_layer = 0;
    order.gmas_layer = 3;
    order.gmaf_layer = 1;
    ioctl(fd, DIS_SET_LAYER_ORDER, &order);
    close(fd);
}

static void read_device_geometry(int *w, int *h, int *rotation) {
    FILE *f = fopen(DEVICE_FILE, "r");
    char line[128], key[64], value[64];
    *w = 640; *h = 480; *rotation = 0;
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
    unsigned long value = strtoul(s, &end, 0);
    return end != s ? (uint32_t)(value & 0xFFFFFFu) : fallback;
}

static Theme load_theme(void) {
    Theme theme = { 0xF4F4F4, 0xFFFFFF, 0x101010 };
    FILE *f = fopen(THEME_FILE, "r");
    char line[128], key[64], value[64];
    if (!f) return theme;
    while (fgets(line, sizeof(line), f)) {
        if (sscanf(line, "%63[^=]=%63s", key, value) != 2) continue;
        if (!strcmp(key, "text_color")) theme.text = parse_rgb(value, theme.text);
        else if (!strcmp(key, "selection_color")) theme.accent = parse_rgb(value, theme.accent);
        else if (!strcmp(key, "sel_text_color")) theme.selected_text = parse_rgb(value, theme.selected_text);
    }
    fclose(f);
    return theme;
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
    void *memory = shmat(id, NULL, 0);
    return memory == (void *)-1 ? NULL : (volatile uint32_t *)memory;
}

static uint32_t logical_keys(volatile uint32_t *raw) {
    uint32_t input = raw ? (*raw & 0xFFFFu) : 0, output = 0;
    for (int i = 0; i < BTN_COUNT; i++)
        if (input & (1u << key_bits[i])) output |= 1u << i;
    return output;
}

static bool supported(const char *path) {
    const char *dot = strrchr(path, '.');
    if (!dot) return false;
    return !strcasecmp(dot, ".jpg") || !strcasecmp(dot, ".jpe") ||
           !strcasecmp(dot, ".jpeg") || !strcasecmp(dot, ".bmp") ||
           !strcasecmp(dot, ".gif") || !strcasecmp(dot, ".png") ||
           !strcasecmp(dot, ".tga") || !strcasecmp(dot, ".targa") ||
           !strcasecmp(dot, ".ico") || !strcasecmp(dot, ".webp") ||
           !strcasecmp(dot, ".tif") || !strcasecmp(dot, ".tiff");
}

static int path_compare(const void *a, const void *b) {
    return strcasecmp(*(const char * const *)a, *(const char * const *)b);
}

static void image_list_free(ImageList *list) {
    for (int i = 0; i < list->count; i++) free(list->path[i]);
    free(list->path);
    memset(list, 0, sizeof(*list));
}

static int image_list_build(ImageList *list, const char *selected) {
    memset(list, 0, sizeof(*list));
    char directory[1024];
    snprintf(directory, sizeof(directory), "%s", selected);
    char *slash = strrchr(directory, '/');
    if (slash) *slash = '\0'; else snprintf(directory, sizeof(directory), ".");
    DIR *dir = opendir(directory);
    if (!dir) return -1;
    struct dirent *entry;
    while ((entry = readdir(dir))) {
        if (entry->d_name[0] == '.' || !supported(entry->d_name)) continue;
        size_t length = strlen(directory) + strlen(entry->d_name) + 2;
        char *path = malloc(length);
        if (!path) break;
        snprintf(path, length, "%s/%s", directory, entry->d_name);
        char **grown = realloc(list->path, (size_t)(list->count + 1) * sizeof(*list->path));
        if (!grown) { free(path); break; }
        list->path = grown;
        list->path[list->count++] = path;
    }
    closedir(dir);
    if (!list->count) return -1;
    qsort(list->path, (size_t)list->count, sizeof(*list->path), path_compare);
    for (int i = 0; i < list->count; i++)
        if (!strcmp(list->path[i], selected)) { list->current = i; break; }
    return 0;
}

static int overlay_open(Overlay *overlay) {
    memset(overlay, 0, sizeof(*overlay)); overlay->fd = -1;
    read_device_geometry(&overlay->logical_w, &overlay->logical_h, &overlay->rotation);
    overlay->fd = open("/dev/fb1", O_RDWR);
    if (overlay->fd < 0) return -1;
    struct fb_fix_screeninfo fixed;
    if (ioctl(overlay->fd, FBIOGET_VSCREENINFO, &overlay->vi) < 0 ||
        ioctl(overlay->fd, FBIOGET_FSCREENINFO, &fixed) < 0 || !fixed.smem_len) goto fail;
    overlay->fb_w = overlay->vi.xres; overlay->fb_h = overlay->vi.yres;
    overlay->pitch = fixed.line_length; overlay->bytespp = overlay->vi.bits_per_pixel / 8;
    overlay->mem_len = fixed.smem_len;
    if (overlay->bytespp != 2 && overlay->bytespp != 4) goto fail;
    overlay->mem = mmap(NULL, overlay->mem_len, PROT_READ | PROT_WRITE, MAP_SHARED, overlay->fd, 0);
    if (overlay->mem == MAP_FAILED) { overlay->mem = NULL; goto fail; }
    overlay->canvas = calloc((size_t)overlay->logical_w * overlay->logical_h, 4);
    if (!overlay->canvas) goto fail;
    /* Match the video player's device-profile transform exactly. Geometry
     * alone cannot distinguish clockwise from counter-clockwise mounting, and
     * guessed rotation made the SF3000HD HUD appear upside down. */
    if (!(overlay->fb_w < overlay->fb_h && overlay->logical_w > overlay->logical_h))
        overlay->rotation = 0;
    return 0;
fail:
    if (overlay->mem) munmap(overlay->mem, overlay->mem_len);
    if (overlay->fd >= 0) close(overlay->fd);
    free(overlay->canvas); memset(overlay, 0, sizeof(*overlay)); overlay->fd = -1;
    return -1;
}

static void overlay_clear(Overlay *overlay) {
    if (overlay->mem) memset(overlay->mem, 0, overlay->mem_len);
    if (overlay->canvas) memset(overlay->canvas, 0, (size_t)overlay->logical_w * overlay->logical_h * 4);
}

static void overlay_close(Overlay *overlay) {
    overlay_clear(overlay);
    if (overlay->mem) munmap(overlay->mem, overlay->mem_len);
    if (overlay->fd >= 0) close(overlay->fd);
    free(overlay->canvas);
}

static uint32_t scale_channel(uint32_t channel, const struct fb_bitfield *field) {
    if (!field->length) return 0;
    uint32_t maximum = (1u << field->length) - 1u;
    return ((channel * maximum + 127u) / 255u) << field->offset;
}

static uint32_t pack_fb(const Overlay *overlay, uint32_t argb) {
    return scale_channel((argb >> 16) & 255, &overlay->vi.red) |
           scale_channel((argb >> 8) & 255, &overlay->vi.green) |
           scale_channel(argb & 255, &overlay->vi.blue) |
           scale_channel(argb >> 24, &overlay->vi.transp);
}

static void overlay_present(Overlay *overlay) {
    for (int fy = 0; fy < overlay->fb_h; fy++) {
        unsigned char *row = overlay->mem + (size_t)(fy + overlay->vi.yoffset) * overlay->pitch;
        for (int fx = 0; fx < overlay->fb_w; fx++) {
            int lx, ly;
            if (overlay->rotation == 90) {
                lx = fy * overlay->logical_w / overlay->fb_h;
                ly = overlay->logical_h - 1 - fx * overlay->logical_h / overlay->fb_w;
            } else if (overlay->rotation == 180) {
                lx = overlay->logical_w - 1 - fx * overlay->logical_w / overlay->fb_w;
                ly = overlay->logical_h - 1 - fy * overlay->logical_h / overlay->fb_h;
            } else if (overlay->rotation == 270) {
                lx = overlay->logical_w - 1 - fy * overlay->logical_w / overlay->fb_h;
                ly = fx * overlay->logical_h / overlay->fb_w;
            } else {
                lx = fx * overlay->logical_w / overlay->fb_w;
                ly = fy * overlay->logical_h / overlay->fb_h;
            }
            uint32_t pixel = pack_fb(overlay, overlay->canvas[(size_t)ly * overlay->logical_w + lx]);
            if (overlay->bytespp == 4) ((uint32_t *)row)[fx + overlay->vi.xoffset] = pixel;
            else ((uint16_t *)row)[fx + overlay->vi.xoffset] = (uint16_t)pixel;
        }
    }
}

static uint32_t argb(unsigned alpha, uint32_t rgb) { return (alpha << 24) | (rgb & 0xFFFFFFu); }

static void rect(Overlay *overlay, int x, int y, int w, int h, uint32_t color) {
    if (x < 0) { w += x; x = 0; } if (y < 0) { h += y; y = 0; }
    if (x + w > overlay->logical_w) w = overlay->logical_w - x;
    if (y + h > overlay->logical_h) h = overlay->logical_h - y;
    for (int yy = y; yy < y + h; yy++)
        for (int xx = x; xx < x + w; xx++) overlay->canvas[(size_t)yy * overlay->logical_w + xx] = color;
}

static void text_draw(Overlay *overlay, int x, int y, const char *text, int scale, uint32_t color, int max_width) {
    int start = x;
    for (; *text && x + 8 * scale <= start + max_width; text++, x += 8 * scale) {
        unsigned char c = (unsigned char)*text; if (c >= 128) c = '?';
        for (int row = 0; row < 8; row++) for (int col = 0; col < 8; col++)
            if (fontdata8x8[c * 8 + row] & (0x80u >> col))
                rect(overlay, x + col * scale, y + row * scale, scale, scale, color);
    }
}

static const char *base_name(const char *path) {
    const char *slash = strrchr(path, '/'); return slash ? slash + 1 : path;
}

static void draw_hud(Overlay *overlay, Theme theme, const char *path, int current, int count,
                     bool fill, int rotation, const char *status) {
    memset(overlay->canvas, 0, (size_t)overlay->logical_w * overlay->logical_h * 4);
    int scale = overlay->logical_w >= 800 ? 2 : 1;
    int margin = overlay->logical_w / 28, panel_h = scale == 2 ? 104 : 86;
    int panel_y = overlay->logical_h - panel_h - margin;
    rect(overlay, margin, panel_y, overlay->logical_w - margin * 2, panel_h, argb(226, 0x101010));
    char title[512], detail[160];
    snprintf(title, sizeof(title), "%s", base_name(path));
    snprintf(detail, sizeof(detail), "%d/%d  %s  %d DEG    LEFT/RIGHT IMAGE  A FIT/FILL  X ROTATE  B BACK",
             current + 1, count, fill ? "FILL" : "FIT", rotation * 90);
    text_draw(overlay, margin + 16, panel_y + 14, title, scale, argb(255, theme.text),
              overlay->logical_w - margin * 2 - 32);
    text_draw(overlay, margin + 16, panel_y + (scale == 2 ? 55 : 43), detail, scale,
              argb(255, theme.text), overlay->logical_w - margin * 2 - 32);
    if (status && *status) {
        int width = (int)strlen(status) * 8 * scale + 24;
        int x = (overlay->logical_w - width) / 2;
        rect(overlay, x, panel_y - 42, width, 30, argb(245, theme.accent));
        text_draw(overlay, x + 12, panel_y - 35, status, scale, argb(255, theme.selected_text), width - 24);
    }
    overlay_present(overlay);
}

static bool player_error(long type) {
    return type == HCPLAYER_MSG_OPEN_FILE_FAILED || type == HCPLAYER_MSG_UNSUPPORT_FORMAT ||
           type == HCPLAYER_MSG_UNSUPPORT_ALL_VIDEO || type == HCPLAYER_MSG_VIDEO_DECODE_ERR ||
           type == HCPLAYER_MSG_ERR_UNDEFINED || type == HCPLAYER_MSG_READ_TIMEOUT;
}

static void *open_picture(const char *path, int msg_id, bool fill, int rotation) {
    union { long double alignment; unsigned char raw[256]; } storage;
    memset(&storage, 0, sizeof(storage));
    HCPlayerInitArgs *args = (HCPlayerInitArgs *)storage.raw;
    args->uri = (char *)path;
    args->msg_id = msg_id;
    args->sync_type = HCPLAYER_VIDEO_MASTER;
    args->disable_audio = true;
    args->rotate_enable = true;
    args->rotate_type = (rotate_type_e)(rotation & 3);
    args->img_dis_mode = fill ? IMG_DIS_FULLSCREEN : IMG_DIS_SCALE;
    args->img_dis_hold_time = 24 * 60 * 60 * 1000;
    args->gif_dis_interval = 100;
    args->img_alpha_mode = ALPHA_BLEND_UNIFORM;
    /* IMG_DIS_SCALE uses the picture player's background surface for its
     * letterbox area. Disabling that surface makes some firmware builds expand
     * the picture plane anyway, so Fit becomes indistinguishable from Fill. */
    args->bg_disable = fill;
    void *player = hcplayer_create(args);
    if (player) hcplayer_play(player);
    return player;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    signal(SIGINT, on_signal); signal(SIGTERM, on_signal);
    load_keymap(); Theme theme = load_theme();
    volatile uint32_t *raw_keys = open_keys();
    ImageList list;
    if (image_list_build(&list, argv[1]) != 0) return 1;
    Overlay overlay; bool have_overlay = overlay_open(&overlay) == 0;
    if (have_overlay) overlay_clear(&overlay);
    int msg_id = msgget(IPC_PRIVATE, 0600 | IPC_CREAT);
    if (hcplayer_init(LOG_WARNING) != 0) goto done;

    bool fill = false, hud = true, reload = true, first_frame = false;
    int rotation = 0;
    int64_t started_at = 0, hud_until = now_ms() + 4500;
    int64_t last_hud_draw = 0;
    bool overlay_visible = false;
    const char *status = NULL;
    void *player = NULL;
    uint32_t previous = logical_keys(raw_keys);

    while (!quit_requested) {
        if (reload) {
            if (player) hcplayer_stop2(player, true, true);
            HCPlayerMsg discard;
            while (msg_id >= 0 && msgrcv(msg_id, &discard, sizeof(discard) - sizeof(long), 0, IPC_NOWAIT) >= 0) {}
            player = open_picture(list.path[list.current], msg_id, fill, rotation);
            configure_image_layer();
            first_frame = false; started_at = now_ms(); reload = false;
            status = player ? NULL : "CANNOT OPEN IMAGE";
            hud = true; hud_until = now_ms() + (player ? 4500 : 6000);
        }
        HCPlayerMsg message;
        if (msg_id >= 0) while (msgrcv(msg_id, &message, sizeof(message) - sizeof(long), 0, IPC_NOWAIT) >= 0) {
            if (message.type == HCPLAYER_MSG_FIRST_VIDEO_FRAME_DECODED ||
                message.type == HCPLAYER_MSG_FIRST_VIDEO_FRAME_SHOWED) first_frame = true;
            else if (player_error(message.type)) status = "UNSUPPORTED IMAGE";
        }
        int64_t now = now_ms();
        if (player && !first_frame && now - started_at > 10000) status = "IMAGE START FAILED";
        if (status && first_frame && now >= hud_until) status = NULL;
        uint32_t keys = logical_keys(raw_keys), pressed = keys & ~previous; previous = keys;
        if (pressed & ((1u << BTN_B) | (1u << BTN_SELECT))) break;
        int change = 0;
        if (pressed & ((1u << BTN_LEFT) | (1u << BTN_L1))) change = -1;
        if (pressed & ((1u << BTN_RIGHT) | (1u << BTN_R1))) change = 1;
        if (change) {
            list.current = (list.current + change + list.count) % list.count;
            rotation = 0; status = NULL; reload = true;
        }
        if (pressed & (1u << BTN_A)) { fill = !fill; status = fill ? "FILL" : "FIT"; reload = true; }
        if (pressed & (1u << BTN_X)) {
            rotation = (rotation + 1) & 3;
            if (player && hcplayer_change_rotate_type(player, (rotate_type_e)rotation) == 0) {
                status = "ROTATED"; hud = true; hud_until = now + 2500;
            } else reload = true;
        }
        if (pressed & (1u << BTN_Y)) { hud = !hud; hud_until = now + 4500; }
        if (have_overlay && (hud || status) && now - last_hud_draw >= 200) {
            draw_hud(&overlay, theme, list.path[list.current], list.current, list.count, fill, rotation, status);
            last_hud_draw = now; overlay_visible = true;
        }
        if (hud && !status && now >= hud_until) hud = false;
        if (have_overlay && !hud && !status && overlay_visible) {
            overlay_clear(&overlay); overlay_visible = false; last_hud_draw = 0;
        }
        usleep(20000);
    }
    if (player) hcplayer_stop2(player, true, true);
    hcplayer_deinit();
done:
    if (msg_id >= 0) msgctl(msg_id, IPC_RMID, NULL);
    if (raw_keys) shmdt((void *)raw_keys);
    if (have_overlay) overlay_close(&overlay);
    image_list_free(&list);
    return 0;
}
