/* libemu_tfhijack.so — TreeFrogUI boot hijack (libretro core for rkgame).
 *
 * Installed by OVERRIDING a stock core file (e.g. cubegm/cores/libemu_md.so).
 * rkgame autoboots via setting.xml:
 *   <autorun file="/mnt/sdcard/MD/dummy.md" driver="" />
 * driver="" -> rkgame resolves the core by the rom's extension (MD ->
 * libemu_md.so = THIS), dlopens it, calls retro_load_game() -> we execl
 * zhijack.sh, replacing rkgame with TreeFrogUI. NOTE: absolute autorun path is
 * mandatory (relative paths are silently ignored by rkgame).
 *
 * Normal libc-linked build: rkgame's process provides libc, so logging + execl
 * resolve fine (the earlier -nostdlib build crashed on PIC string relocs). */

#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

#define LAUNCHER "/mnt/sdcard/cubegm/zhijack.sh"

static void hlog(const char *msg) {
    int fd = open("/mnt/sdcard/tfhijack.log", O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) return;
    write(fd, msg, strlen(msg));
    fsync(fd);
    close(fd);
}

static void tf_launch(void) {
    hlog("launch: execl /bin/sh zhijack.sh\n");
    execl("/bin/sh", "sh", LAUNCHER, (char *)NULL);
    hlog("launch: execl FAILED\n");
}

/* libretro ABI (self-declared; no header needed) */
struct retro_system_info {
    const char *library_name, *library_version, *valid_extensions;
    unsigned char need_fullpath, block_extract;
};
struct retro_game_geometry { unsigned bw, bh, mw, mh; float aspect; };
struct retro_system_timing { double fps, sample_rate; };
struct retro_system_av_info { struct retro_game_geometry geometry; struct retro_system_timing timing; };

void retro_set_environment(void *cb)        { (void)cb; hlog("set_environment\n"); }
void retro_set_video_refresh(void *cb)      { (void)cb; }
void retro_set_audio_sample(void *cb)       { (void)cb; }
void retro_set_audio_sample_batch(void *cb) { (void)cb; }
void retro_set_input_poll(void *cb)         { (void)cb; }
void retro_set_input_state(void *cb)        { (void)cb; }

unsigned retro_api_version(void) { return 1; }

void retro_get_system_info(struct retro_system_info *info) {
    hlog("get_system_info\n");
    info->library_name     = "TreeFrogUI Loader";
    info->library_version  = "1.0";
    info->valid_extensions = "md|MD|bin|BIN|gen|GEN|smd|SMD|zip|ZIP";
    info->need_fullpath    = 1;
    info->block_extract    = 1;
}

void retro_get_system_av_info(struct retro_system_av_info *info) {
    info->geometry.bw = 640; info->geometry.bh = 480;
    info->geometry.mw = 640; info->geometry.mh = 480;
    info->geometry.aspect = 0.0f;
    info->timing.fps = 60.0; info->timing.sample_rate = 48000.0;
}

void retro_init(void)   { hlog("init\n"); }
void retro_deinit(void) {}

unsigned char retro_load_game(const void *game) { (void)game; hlog("load_game\n"); tf_launch(); return 0; }
unsigned char retro_load_game_special(unsigned t, const void *i, unsigned long n) { (void)t;(void)i;(void)n; return 0; }
void retro_run(void) { hlog("run\n"); tf_launch(); }

void retro_reset(void)       {}
void retro_unload_game(void) {}
unsigned retro_get_region(void) { return 0; }
unsigned long retro_serialize_size(void) { return 0; }
unsigned char retro_serialize(void *d, unsigned long s) { (void)d;(void)s; return 0; }
unsigned char retro_unserialize(const void *d, unsigned long s) { (void)d;(void)s; return 0; }
void retro_cheat_reset(void) {}
void retro_cheat_set(unsigned i, unsigned char e, const char *c) { (void)i;(void)e;(void)c; }
void *retro_get_memory_data(unsigned id) { (void)id; return 0; }
unsigned long retro_get_memory_size(unsigned id) { (void)id; return 0; }
void retro_set_controller_port_device(unsigned p, unsigned d) { (void)p;(void)d; }
