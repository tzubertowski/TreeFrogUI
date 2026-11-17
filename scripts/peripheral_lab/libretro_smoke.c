/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include "libretro.h"
#include "legacy_joypad.h"
#include "libretro_video.h"

/* Headless test of the real unchanged libretro core. No display/audio hardware,
 * no saves, no commercial content. A synthetic ROM tests callbacks and CPU code;
 * this is not a performance test or a complete game-compatibility acceptance.
 */
static unsigned frames, polls, nonzero_pixels, audio_nonzero, format;
static size_t samples;
static uint32_t video_hash = 2166136261u, sound_hash = 2166136261u;
static int failed;
static const char *directory = ".";
static int16_t buttons;
static unsigned input_reads;
static int (*backend_submit)(void *, int, int, int);
static void *converted_pixels;
static size_t converted_capacity;
static unsigned backend_frames;

static void log_message(enum retro_log_level level, const char *message, ...)
{
    va_list args; (void)level;
    va_start(args, message); vfprintf(stderr, message, args); va_end(args);
}
static bool environment(unsigned command, void *data)
{
    switch (command) {
    case RETRO_ENVIRONMENT_GET_CAN_DUPE: *(bool *)data = true; return true;
    case RETRO_ENVIRONMENT_GET_OVERSCAN: *(bool *)data = false; return true;
    case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT:
        format = *(unsigned *)data;
        return format <= RETRO_PIXEL_FORMAT_RGB565;
    case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY:
    case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY:
    case RETRO_ENVIRONMENT_GET_CORE_ASSETS_DIRECTORY:
        *(const char **)data = directory; return true;
    case RETRO_ENVIRONMENT_GET_LOG_INTERFACE:
        ((struct retro_log_callback *)data)->log = log_message; return true;
    case RETRO_ENVIRONMENT_GET_VARIABLE:
        ((struct retro_variable *)data)->value = NULL; return false;
    case RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE: *(bool *)data = false; return true;
    case RETRO_ENVIRONMENT_SET_VARIABLES:
    case RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS:
    case RETRO_ENVIRONMENT_SET_CONTROLLER_INFO:
    case RETRO_ENVIRONMENT_SET_SUPPORT_NO_GAME:
    case RETRO_ENVIRONMENT_SET_PERFORMANCE_LEVEL:
    case RETRO_ENVIRONMENT_SET_MEMORY_MAPS:
    case RETRO_ENVIRONMENT_SET_GEOMETRY:
        return true;
    case RETRO_ENVIRONMENT_GET_INPUT_BITMASKS: return true;
    case RETRO_ENVIRONMENT_GET_LANGUAGE: *(unsigned *)data = RETRO_LANGUAGE_ENGLISH; return true;
    case RETRO_ENVIRONMENT_SHUTDOWN: failed = 1; return true;
    default: return false;
    }
}
static void video(const void *pixels, unsigned width, unsigned height, size_t pitch)
{
    unsigned y, x, bpp = format == RETRO_PIXEL_FORMAT_XRGB8888 ? 4 : 2;
    frames++;
    if (!pixels) return; /* legitimate repeated frame */
    if (pixels == RETRO_HW_FRAME_BUFFER_VALID || !width || !height || width > 4096 ||
        height > 4096 || pitch < (size_t)width * bpp || pitch > 1048576) { failed = 1; return; }
    if (backend_submit) {
        size_t needed = (size_t)width * height * 2;
        if (needed > converted_capacity) {
            void *p = realloc(converted_pixels, needed);
            if (!p) { failed = 1; return; }
            converted_pixels = p; converted_capacity = needed;
        }
        if (r36_libretro_to565(converted_pixels, converted_capacity, pixels, width, height, pitch, format) ||
            backend_submit(converted_pixels, width, height, width * 2) < 0) { failed = 1; return; }
        backend_frames++;
    }
    for (y = 0; y < height; y++) {
        const unsigned char *row = (const unsigned char *)pixels + y * pitch;
        for (x = 0; x < width * bpp; x++) {
            video_hash = (video_hash ^ row[x]) * 16777619u;
            nonzero_pixels |= row[x] != 0;
        }
    }
}
static void audio(int16_t left, int16_t right)
{
    samples++;
    audio_nonzero |= left != 0 || right != 0;
    sound_hash = (sound_hash ^ (uint16_t)left) * 16777619u;
    sound_hash = (sound_hash ^ (uint16_t)right) * 16777619u;
}
static size_t audio_batch(const int16_t *data, size_t count)
{
    size_t i;
    if (!data || count > 1048576) { failed = 1; return 0; }
    for (i = 0; i < count; i++) audio(data[i * 2], data[i * 2 + 1]);
    return count;
}
static void input_poll(void) { polls++; }
static int16_t input_state(unsigned port, unsigned device, unsigned index, unsigned id)
{
    (void)index;
    input_reads++;
    if (port || device != RETRO_DEVICE_JOYPAD) return 0;
    if (id == RETRO_DEVICE_ID_JOYPAD_MASK) return buttons;
    if (id < 16) return (buttons >> id) & 1;
    return 0;
}
#define RESOLVE(name) do { *(void **)(&name) = dlsym(library, #name); if (!name) { fprintf(stderr, "missing %s\n", #name); goto finish; } } while (0)

int main(int argc, char **argv)
{
    void *library = NULL, *rom = NULL, *snapshot = NULL, *backend = NULL;
    void (*backend_deinit)(void) = NULL;
    int backend_initialized = 0;
    const char *backend_path = getenv("R36_TEST_VIDEO_BACKEND");
    FILE *file = NULL;
    long length;
    unsigned i;
    int initialized = 0, loaded = 0, result = 1;
    int neutral = argc == 4 && !strcmp(argv[3], "--neutral");
    int shared_input = argc == 4 && !strcmp(argv[3], "--shared-input");
    const volatile uint32_t *shared_keys = NULL;
    struct retro_system_info info = {0};
    struct retro_system_av_info av = {0};
    struct retro_game_info game = {0};
    void (*retro_set_environment)(retro_environment_t);
    void (*retro_set_video_refresh)(retro_video_refresh_t);
    void (*retro_set_audio_sample)(retro_audio_sample_t);
    void (*retro_set_audio_sample_batch)(retro_audio_sample_batch_t);
    void (*retro_set_input_poll)(retro_input_poll_t);
    void (*retro_set_input_state)(retro_input_state_t);
    void (*retro_init)(void), (*retro_deinit)(void), (*retro_run)(void), (*retro_unload_game)(void);
    void (*retro_get_system_info)(struct retro_system_info *);
    void (*retro_get_system_av_info)(struct retro_system_av_info *);
    bool (*retro_load_game)(const struct retro_game_info *);
    unsigned (*retro_api_version)(void);
    void *(*retro_get_memory_data)(unsigned);
    size_t (*retro_get_memory_size)(unsigned);
    size_t (*retro_serialize_size)(void);
    bool (*retro_serialize)(void *, size_t);
    bool (*retro_unserialize)(const void *, size_t);
    if (argc != 3 && !neutral && !shared_input) { fputs("usage: libretro_smoke CORE SYNTHETIC_ROM [--neutral|--shared-input]\n", stderr); return 2; }
    if (shared_input) {
        key_t key = ftok("/tmp/joy_key", 'a');
        int id = key == (key_t)-1 ? -1 : shmget(key, 4, 0400);
        if (id < 0) return 2;
        shared_keys = shmat(id, NULL, SHM_RDONLY);
        if (shared_keys == (void *)-1) return 2;
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    if (backend_path) {
        int (*backend_init)(void);
        backend = dlopen(backend_path, RTLD_NOW | RTLD_LOCAL);
        if (!backend) { fprintf(stderr, "backend dlopen: %s\n", dlerror()); goto finish; }
        *(void **)(&backend_init) = dlsym(backend, "video_drivers_init");
        *(void **)(&backend_submit) = dlsym(backend, "video_driver_disp_frame");
        *(void **)(&backend_deinit) = dlsym(backend, "video_driver_deinit");
        if (!backend_init || !backend_submit || !backend_deinit || backend_init() <= 0) goto finish;
        backend_initialized = 1;
    }
    library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) { fprintf(stderr, "dlopen: %s\n", dlerror()); goto finish; }
    RESOLVE(retro_set_environment); RESOLVE(retro_set_video_refresh);
    RESOLVE(retro_set_audio_sample); RESOLVE(retro_set_audio_sample_batch);
    RESOLVE(retro_set_input_poll); RESOLVE(retro_set_input_state);
    RESOLVE(retro_init); RESOLVE(retro_deinit); RESOLVE(retro_run);
    RESOLVE(retro_get_system_info); RESOLVE(retro_get_system_av_info);
    RESOLVE(retro_load_game); RESOLVE(retro_unload_game); RESOLVE(retro_api_version);
    RESOLVE(retro_get_memory_data); RESOLVE(retro_get_memory_size);
    RESOLVE(retro_serialize_size); RESOLVE(retro_serialize); RESOLVE(retro_unserialize);
    if (retro_api_version() != RETRO_API_VERSION) goto finish;
    retro_set_environment(environment); retro_set_video_refresh(video);
    retro_set_audio_sample(audio); retro_set_audio_sample_batch(audio_batch);
    retro_set_input_poll(input_poll); retro_set_input_state(input_state);
    retro_get_system_info(&info);
    printf("core=%s version=%s fullpath=%d\n", info.library_name, info.library_version, info.need_fullpath);
    file = fopen(argv[2], "rb");
    if (!file || fseek(file, 0, SEEK_END) || (length = ftell(file)) < 1 || length > 16 * 1024 * 1024 || fseek(file, 0, SEEK_SET)) goto finish;
    rom = malloc((size_t)length);
    if (!rom || fread(rom, 1, length, file) != (size_t)length) goto finish;
    fclose(file); file = NULL;
    game.path = argv[2]; game.data = rom; game.size = length;
    retro_init(); initialized = 1;
    if (!retro_load_game(&game)) { fputs("load_game failed\n", stderr); goto finish; }
    loaded = 1;
    retro_get_system_av_info(&av);
    printf("geometry=%ux%u fps=%.6f samplerate=%.6f\n", av.geometry.base_width, av.geometry.base_height, av.timing.fps, av.timing.sample_rate);
    if (shared_input) puts("SHARED_INPUT_READY");
    for (i = 0; i < 120 && !failed; i++) {
        /* Synthetic mode drives deterministic legacy A; integration mode reads
         * the real publisher's 4-byte SysV word and never injects into it. */
        uint32_t word = shared_input ? *shared_keys :
            (!neutral && i >= 40 && i < 80 ? UINT32_C(1) << 13 : 0);
        buttons = r36_legacy_to_libretro(word);
        retro_run();
        if (shared_input) usleep(16000);
    }
    {
        const unsigned char *ram = retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
        size_t size = retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM);
        unsigned press = 0, release = 0, signature = 0;
        if (ram && size >= 4) { signature = ram[0]; press = ram[1]; release = ram[2]; }
        printf("frames=%u polls=%u input_reads=%u audio_frames=%zu video_hash=%08x audio_hash=%08x nonzero_pixels=%u audio_nonzero=%u\n",
               frames, polls, input_reads, samples, video_hash, sound_hash, nonzero_pixels, audio_nonzero);
        printf("ram_bytes=%zu test_signature=%u press_seen=%u release_seen=%u\n", size, signature, press, release);
        if (failed || frames < 100 || !polls || !input_reads || !samples || !nonzero_pixels || !audio_nonzero ||
            signature != 0x42 || press != (unsigned)!neutral || release != (unsigned)!neutral) goto finish;
    }
    {
        size_t size = retro_serialize_size(), ram_size = retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM);
        unsigned char *ram = retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
        unsigned char saved;
        if (!size || size > 16 * 1024 * 1024 || !ram || ram_size < 4) goto finish;
        snapshot = malloc(size);
        if (!snapshot || !retro_serialize(snapshot, size)) goto finish;
        saved = ram[3]; ram[3] ^= 0x5a;
        if (!retro_unserialize(snapshot, size)) goto finish;
        ram = retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
        if (!ram || ram[3] != saved) goto finish;
        printf("savestate_roundtrip=PASS bytes=%zu\n", size);
    }
    if (backend_path) {
        unsigned int (*count)(void), (*hash)(void);
        *(void **)(&count) = dlsym(backend, "r36_test_backend_frames");
        *(void **)(&hash) = dlsym(backend, "r36_test_backend_hash");
        if (!count || !hash || backend_frames < 100 || count() != backend_frames) goto finish;
        printf("actual_backend_frames=%u output_hash=%08x DRM_device=MOCKED\n", backend_frames, hash());
    }
    printf("input_mode=%s\n", shared_input ? "real_SysV_publisher" : neutral ? "neutral" : "A_press_release");
    puts("LIBRETRO_SYNTHETIC_EXECUTION=PASS\nhardware_or_real_game_verified=0");
    result = 0;
finish:
    if (loaded) retro_unload_game();
    if (initialized) retro_deinit();
    if (file) fclose(file);
    free(snapshot);
    free(rom);
    if (library) dlclose(library);
    if (shared_keys) shmdt((const void *)shared_keys);
    if (backend_initialized) backend_deinit();
    if (backend) dlclose(backend);
    free(converted_pixels);
    return result;
}
