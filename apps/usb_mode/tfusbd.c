// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Pavel Kotek
/*
 * tfusbd - background USB manager for TreeFrogUI on HiChip HC16xx handhelds.
 *
 * The OTG port (MUSB controller 0) is the only USB port with data lines, so
 * it has to serve both directions:
 *   IDLE : alternate HOST (OTG mouse / flash drive / pad) and PERIPHERAL
 *          (MTP gadget bound, waiting for a PC)
 *   PC   : a PC is sending SOFs -> stay in peripheral role (MTP)
 *   DEV  : a device enumerated in host role -> stay host until it is removed
 * PC presence = the MUSB FRAME register is counting.  VBUS always reads valid
 * on this board (the console powers the port) and the UDC state stays
 * "configured" after an unplug, so neither can be used.
 *
 * The MTP responder (tfmtp) runs the whole time at nice 19, so a running game
 * keeps almost all of the CPU.  The SD card stays mounted.
 *
 *   tfusbd            run in the foreground (normally started by tfusbd.sh)
 *   tfusbd -d         daemonize
 *
 * Build: zig cc -target mipsel-linux-musleabi -mcpu=mips32 -static -Os -s -o tfusbd tfusbd.c
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <time.h>
#include <dirent.h>
#include <signal.h>
#include <sched.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/resource.h>
#include <sys/syscall.h>

#define ROOT        "/mnt/sdcard"
#define CG          ROOT "/cubegm"
#define GADGET      "/sys/kernel/config/usb_gadget/treefrog_storage"
#define MODE0       "/sys/devices/platform/soc/18844000.usb/musb-hdrc.0.auto/mode"
#define UDC_NAME    "musb-hdrc.0.auto"
#define UDC_STATE   "/sys/class/udc/" UDC_NAME "/state"
#define MUSB0_BASE  0x18844000u
#define REG_FRAME   0x0C
#define LOGF        "/tmp/tfusbd.log"
#define STATEF      "/tmp/tfusbd.state"
#define PIDF        "/tmp/tfusbd.pid"
#define MTP_EXIT    "/tmp/treefrog_mtp_exit"

static int g_host_slice_ms = 2000, g_peri_slice_ms = 2000;
static volatile uint16_t *g_frame;           /* mmap'ed MUSB FRAME register */
static pid_t g_responder;
static volatile sig_atomic_t g_stop;

/* ------------------------------------------------------------------ */
static double uptime(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec / 1e9; }
static void msleep(int ms) { struct timespec t = { ms / 1000, (ms % 1000) * 1000000L }; while (nanosleep(&t, &t) && errno == EINTR && !g_stop) ; }

static void L(const char *fmt, ...) {
    struct stat st;
    if (stat(LOGF, &st) == 0 && st.st_size > 256 * 1024) rename(LOGF, LOGF ".1");
    FILE *f = fopen(LOGF, "a");
    if (!f) return;
    va_list ap; va_start(ap, fmt);
    fprintf(f, "%.2f ", uptime()); vfprintf(f, fmt, ap); fputc('\n', f);
    va_end(ap); fclose(f);
}
static int wr(const char *path, const char *val) {
    int fd = open(path, O_WRONLY | O_TRUNC);
    if (fd < 0) return -1;
    ssize_t n = write(fd, val, strlen(val));
    close(fd);
    return n < 0 ? -1 : 0;
}
static int rd(const char *path, char *buf, size_t n) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) { buf[0] = 0; return -1; }
    ssize_t r = read(fd, buf, n - 1);
    close(fd);
    if (r < 0) r = 0;
    buf[r] = 0;
    while (r > 0 && (buf[r - 1] == '\n' || buf[r - 1] == ' ')) buf[--r] = 0;
    return 0;
}
static void put_file(const char *path, const char *val) {
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return;
    if (write(fd, val, strlen(val)) < 0) { /* best effort */ }
    close(fd);
}
static void set_state(const char *s) {
    char b[96]; snprintf(b, sizeof b, "%s %.0f\n", s, uptime());
    put_file(STATEF, b);
}

/* ------------------------------------------------------------------ */
static int map_regs(void) {
    int fd = open("/dev/mem", O_RDONLY | O_SYNC);
    if (fd < 0) return -1;
    void *p = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, MUSB0_BASE);
    close(fd);
    if (p == MAP_FAILED) return -1;
    g_frame = (volatile uint16_t *)((volatile uint8_t *)p + REG_FRAME);
    return 0;
}
static int frame_running(void) {
    uint16_t a = *g_frame; msleep(3); return *g_frame != a;
}
static int host_devices(void) {          /* entries "1-..." besides the root hub interface */
    DIR *d = opendir("/sys/bus/usb/devices");
    int n = 0; struct dirent *e;
    if (!d) return 0;
    while ((e = readdir(d))) if (!strncmp(e->d_name, "1-", 2) && strcmp(e->d_name, "1-0:1.0")) n++;
    closedir(d);
    return n;
}
static void udc_state(char *b, size_t n) { if (rd(UDC_STATE, b, n) < 0) snprintf(b, n, "none"); }

static int bound(void) { char b[64]; rd(GADGET "/UDC", b, sizeof b); return b[0] != 0; }
static void role_host(void) {
    if (bound()) wr(GADGET "/UDC", "\n");
    wr(MODE0, "host\n");
}
static void role_peripheral(void) {
    wr(MODE0, "peripheral\n");
    if (!bound()) wr(GADGET "/UDC", UDC_NAME "\n");
}

/* ------------------------------------------------------------------ */
static int run_cmd(const char *const argv[]) {
    pid_t p = fork();
    if (p == 0) { int fd = open("/dev/null", O_RDWR); dup2(fd, 0); dup2(fd, 1); dup2(fd, 2); execv(argv[0], (char *const *)argv); _exit(127); }
    int st = 0; if (p > 0) waitpid(p, &st, 0);
    return p > 0 && WIFEXITED(st) ? WEXITSTATUS(st) : -1;
}
static int module_loaded(const char *name) {
    FILE *f = fopen("/proc/modules", "r"); char line[256]; size_t n = strlen(name); int ok = 0;
    if (!f) return 0;
    while (fgets(line, sizeof line, f)) if (!strncmp(line, name, n) && line[n] == ' ') { ok = 1; break; }
    fclose(f); return ok;
}
static void mkd(const char *p) { mkdir(p, 0755); }
static int setup_gadget(void) {
    struct stat st;
    if (stat("/sys/kernel/config/usb_gadget", &st) != 0) {
        const char *a[] = { "/bin/mount", "-t", "configfs", "none", "/sys/kernel/config", NULL }; run_cmd(a);
    }
    if (!module_loaded("usb_f_mtp")) {
        char ms[256], mtp[256], rel[64];
        { FILE *f = fopen("/proc/sys/kernel/osrelease", "r"); if (!f || !fgets(rel, sizeof rel, f)) strcpy(rel, "4.4.186-release"); if (f) fclose(f); rel[strcspn(rel, "\n")] = 0; }
        snprintf(ms, sizeof ms, CG "/modules/%s/usb_f_mass_storage.ko", rel);
        snprintf(mtp, sizeof mtp, CG "/modules/%s/usb_f_mtp.ko", rel);
        const char *a1[] = { "/sbin/modprobe", "libcomposite", NULL }; run_cmd(a1);
        if (!module_loaded("usb_f_mass_storage")) { const char *a2[] = { "/sbin/insmod", ms, NULL }; run_cmd(a2); }
        const char *a3[] = { "/sbin/insmod", mtp, NULL }; run_cmd(a3);
        L("modules: mtp=%d mass_storage=%d", module_loaded("usb_f_mtp"), module_loaded("usb_f_mass_storage"));
        if (!module_loaded("usb_f_mtp")) return -1;
    }
    if (stat(GADGET "/configs/c.1/mtp.usb0", &st) == 0) return 0;      /* already complete */
    char serial[64] = "TreeFrogUI-SF3000", mid[64];
    if (rd("/etc/machine-id", mid, sizeof mid) == 0 && mid[0]) { mid[16] = 0; snprintf(serial, sizeof serial, "TreeFrogUI-%s", mid); }
    mkd(GADGET);
    wr(GADGET "/idVendor", "0x18d1\n"); wr(GADGET "/idProduct", "0x4e22\n");
    wr(GADGET "/bcdDevice", "0x0100\n"); wr(GADGET "/bcdUSB", "0x0200\n");
    mkd(GADGET "/strings/0x409"); mkd(GADGET "/configs/c.1"); mkd(GADGET "/configs/c.1/strings/0x409");
    wr(GADGET "/strings/0x409/serialnumber", serial);
    wr(GADGET "/strings/0x409/manufacturer", "TreeFrogUI\n");
    wr(GADGET "/strings/0x409/product", "TreeFrogUI MTP\n");
    wr(GADGET "/configs/c.1/strings/0x409/configuration", "MTP file access\n");
    wr(GADGET "/configs/c.1/MaxPower", "120\n");
    mkd(GADGET "/functions/mtp.usb0");
    if (stat(GADGET "/os_desc", &st) == 0) {
        wr(GADGET "/os_desc/b_vendor_code", "1\n"); wr(GADGET "/os_desc/qw_sign", "MSFT100\n");
        mkd(GADGET "/functions/mtp.usb0/os_desc/interface.MTP");
        wr(GADGET "/functions/mtp.usb0/os_desc/interface.MTP/compatible_id", "MTP\n");
        if (lstat(GADGET "/os_desc/c.1", &st) != 0) symlink(GADGET "/configs/c.1", GADGET "/os_desc/c.1");
        wr(GADGET "/os_desc/use", "1\n");
    }
    if (lstat(GADGET "/configs/c.1/mtp.usb0", &st) != 0) symlink(GADGET "/functions/mtp.usb0", GADGET "/configs/c.1/mtp.usb0");
    if (stat(GADGET "/configs/c.1/mtp.usb0", &st) != 0) { L("gadget setup failed: %s", strerror(errno)); return -1; }
    L("gadget created");
    return 0;
}

/* ------------------------------------------------------------------ */
/* find processes by a substring of their command line */
static int find_procs(const char *needle, pid_t *out, int max) {
    DIR *d = opendir("/proc"); struct dirent *e; int n = 0; char p[64], cl[512];
    if (!d) return 0;
    while ((e = readdir(d)) && n < max) {
        pid_t pid = (pid_t)atoi(e->d_name);
        if (pid <= 1 || pid == getpid()) continue;
        snprintf(p, sizeof p, "/proc/%d/cmdline", (int)pid);
        int fd = open(p, O_RDONLY); if (fd < 0) continue;
        ssize_t r = read(fd, cl, sizeof cl - 1); close(fd);
        if (r <= 0) continue;
        for (ssize_t i = 0; i < r; i++) if (!cl[i]) cl[i] = ' ';
        cl[r] = 0;
        if (strstr(cl, needle)) out[n++] = pid;
    }
    closedir(d);
    return n;
}
static int usb_mode_running(void) { pid_t p[4]; return find_procs("usb_mode.sh", p, 4) > 0; }

static void takeover(void) {
    /* end a menu-started session the way the B button does, so usb_mode.sh
       runs its own teardown (SIGKILL leaves the display dead until reboot) */
    if (!usb_mode_running()) return;
    close(open(MTP_EXIT, O_CREAT | O_WRONLY, 0600));
    pid_t r[8]; int n = find_procs("tfmtp", r, 8); n += find_procs("mtp-server", r + n, 8 - n);
    for (int i = 0; i < n; i++) kill(r[i], SIGTERM);
    L("takeover: asked usb_mode.sh to exit (%d responder(s))", n);
    int w = 0; while (usb_mode_running() && w < 60) { msleep(500); w++; }
    L("takeover: usb_mode.sh %s after %.1fs", usb_mode_running() ? "STILL RUNNING" : "exited", w / 2.0);
    msleep(2000);
}

static void start_responder(void) {
    if (g_responder > 0) {
        int st; pid_t w = waitpid(g_responder, &st, WNOHANG);
        if (w == 0) return;                                /* still running */
        L("responder %d exited (status 0x%x)", (int)g_responder, st);
        g_responder = 0;
    }
    pid_t stray[8]; int n = find_procs(CG "/tfmtp", stray, 8);
    for (int i = 0; i < n; i++) kill(stray[i], SIGTERM);
    if (n) msleep(500);
    pid_t p = fork();
    if (p == 0) {
        /* nice 19: ~1.5 % of the CPU against a game at nice 0, so a busy game
           keeps almost everything, yet MTP never stalls completely. SCHED_IDLE
           (tried first) starved tfmtp under 100 % game load and Windows
           dropped the device with timeouts (0x802A0006). */
        setpriority(PRIO_PROCESS, 0, 19);
        /* per-request log only in debug mode (TreeFrog convention: an
           empty log.txt in the SD root); /tmp is RAM and must not grow */
        int fd = access(ROOT "/log.txt", F_OK) == 0
                 ? open(ROOT "/log.txt", O_WRONLY | O_APPEND)
                 : open("/dev/null", O_WRONLY);
        int nul = open("/dev/null", O_RDONLY);
        dup2(nul, 0); dup2(fd, 1); dup2(fd, 2);
        execl(CG "/tfmtp", "tfmtp", ROOT, (char *)NULL);
        _exit(127);
    }
    g_responder = p;
    L("responder started pid=%d (nice 19)", (int)p);
}

/* ------------------------------------------------------------------ */
/* RAM housekeeping: picoarch extracts zipped ROMs to /tmp/pa-<name>
 * (tmpfs = RAM) and never deletes them, so after a game or two the 43 MB
 * console has no memory left and the next game (e.g. pcsx4all) is killed
 * by the OOM killer. Delete such files once no game is running (only the
 * FrogUI menu, or nothing, runs in picoarch) and no process has them open. */
static int file_in_use(const char *path) {
    DIR *d = opendir("/proc"); struct dirent *e; char p[96], l[512];
    if (!d) return 1;
    int used = 0;
    while (!used && (e = readdir(d))) {
        if (e->d_name[0] < '1' || e->d_name[0] > '9') continue;
        snprintf(p, sizeof p, "/proc/%s/fd", e->d_name);
        DIR *fd = opendir(p); struct dirent *f;
        if (fd) {
            while ((f = readdir(fd))) {
                char q[160]; snprintf(q, sizeof q, "%s/%s", p, f->d_name);
                ssize_t n = readlink(q, l, sizeof l - 1);
                if (n > 0) { l[n] = 0; if (!strcmp(l, path)) { used = 1; break; } }
            }
            closedir(fd);
        }
        if (!used) {                                   /* mmapped without an open fd */
            snprintf(p, sizeof p, "/proc/%s/maps", e->d_name);
            FILE *m = fopen(p, "r");
            if (m) {
                while (fgets(l, sizeof l, m)) if (strstr(l, path)) { used = 1; break; }
                fclose(m);
            }
        }
    }
    closedir(d);
    return used;
}
static int game_running(void) {
    pid_t p[8]; int n = find_procs("picoarch", p, 8);
    for (int i = 0; i < n; i++) {
        char f[64], cl[512]; snprintf(f, sizeof f, "/proc/%d/cmdline", (int)p[i]);
        int fd = open(f, O_RDONLY); if (fd < 0) continue;
        ssize_t r = read(fd, cl, sizeof cl - 1); close(fd);
        if (r <= 0) continue;
        for (ssize_t k = 0; k < r; k++) if (!cl[k]) cl[k] = ' ';
        cl[r] = 0;
        if (!strstr(cl, "frogui_libretro")) return 1;      /* a core other than the menu */
    }
    return 0;
}
static void housekeeping(void) {
    static double last;
    double t = uptime();
    if (t - last < 10) return;
    last = t;
    if (game_running()) return;
    DIR *d = opendir("/tmp"); struct dirent *e; char path[300];
    if (!d) return;
    while ((e = readdir(d))) {
        if (strncmp(e->d_name, "pa-", 3)) continue;
        snprintf(path, sizeof path, "/tmp/%s", e->d_name);
        struct stat st;
        if (lstat(path, &st) != 0 || !S_ISREG(st.st_mode) || file_in_use(path)) continue;
        if (unlink(path) == 0) L("housekeeping: freed %ld KB of RAM: %s", (long)(st.st_size / 1024), path);
    }
    closedir(d);
}

/* The stock root filesystem is an initramfs, i.e. RAM that can never be
 * swapped out ("Unevictable" in /proc/meminfo). TreeFrogUI bind-mounts the
 * SD card's copies over /bin /sbin /lib /usr /etc, so the RAM copies under
 * them can no longer be reached by any path, yet keep ~4 MB. hcdemo_files
 * holds two "game corrupted" bitmaps (2.8 MB) only the stock boot check
 * shows. Delete both through a private non-recursive bind of / (it shows
 * the initramfs without any submounts, so nothing on the SD is touched).
 * The initramfs is unpacked again from flash on every boot. */
static long unevictable_kb(void) {
    FILE *f = fopen("/proc/meminfo", "r"); char l[128]; long v = -1;
    if (!f) return -1;
    while (fgets(l, sizeof l, f)) if (sscanf(l, "Unevictable: %ld kB", &v) == 1) break;
    fclose(f);
    return v;
}
static void free_hidden_rootfs(void) {
    long before = unevictable_kb();
    const char *script =
        "set -u; V=/tmp/.tfroot; mkdir -p $V || exit 1\n"
        "mount -o bind / $V || { rmdir $V; exit 1; }\n"
        "for d in bin sbin lib usr etc; do\n"
        "  mountpoint -q /$d && [ -d $V/$d ] && ! mountpoint -q $V/$d && rm -rf $V/$d/* $V/$d/.[!.]* 2>/dev/null\n"
        "done\n"
        "[ -d $V/hcdemo_files ] && ! mountpoint -q $V/hcdemo_files && rm -f $V/hcdemo_files/*.bmp\n"
        "umount $V; rmdir $V\n";
    const char *a[] = { "/bin/sh", "-c", script, NULL };
    int rc = run_cmd(a);
    L("rootfs: freed hidden initramfs copies (rc=%d), Unevictable %ld -> %ld kB", rc, before, unevictable_kb());
}

static void on_signal(int s) { (void)s; g_stop = 1; }

/* ------------------------------------------------------------------ */
int main(int argc, char **argv) {
    if (argc > 1 && !strcmp(argv[1], "-d")) {
        if (fork() > 0) return 0;
        setsid();
        if (fork() > 0) return 0;
        int nul = open("/dev/null", O_RDWR); dup2(nul, 0); dup2(nul, 1); dup2(nul, 2);
    }
    if (chdir("/") != 0) { /* ignore */ }
    const char *e;
    if ((e = getenv("TFUSBD_HOST_MS"))) g_host_slice_ms = atoi(e);
    if ((e = getenv("TFUSBD_PERI_MS"))) g_peri_slice_ms = atoi(e);
    { char b[32]; snprintf(b, sizeof b, "%d\n", (int)getpid()); put_file(PIDF, b); }
    signal(SIGTERM, on_signal); signal(SIGINT, on_signal); signal(SIGHUP, on_signal);
    signal(SIGPIPE, SIG_IGN);
    setpriority(PRIO_PROCESS, 0, 10);
    L("=== tfusbd (C) start pid=%d host=%dms peri=%dms ===", (int)getpid(), g_host_slice_ms, g_peri_slice_ms);
    if (map_regs() != 0) { L("FATAL cannot map MUSB registers: %s", strerror(errno)); return 1; }
    /* Let the menu come up first: tfusbd starts right before FrogUI, and its
       start-up work (initramfs cleanup, module loading, gadget) used to
       compete with the menu for the single CPU core. Wait until picoarch
       runs (max 8 s), then 2.5 s more. */
    for (int i = 0; i < 80 && !g_stop; i++) {
        pid_t pp[2];
        if (find_procs("picoarch", pp, 2) > 0) break;
        msleep(100);
    }
    msleep(2500);
    free_hidden_rootfs();
    takeover();
    if (setup_gadget() != 0) { L("FATAL gadget setup failed"); return 1; }
    start_responder();
    role_host(); msleep(300);

    enum { IDLE, PC, DEV } state = IDLE;
    char us[64];
    set_state("IDLE");
    while (!g_stop) {
        start_responder();
        if (state == PC) {
            int miss = 0;
            while (miss < 3 && !g_stop) {
                miss = frame_running() ? 0 : miss + 1;
                msleep(1000);
                start_responder();
                housekeeping();
            }
            udc_state(us, sizeof us);
            L("PC gone (udc=%s)", us);
            role_host(); state = IDLE; set_state("IDLE"); msleep(300);
            continue;
        }
        if (state == DEV) {
            while (host_devices() > 0 && !g_stop) { msleep(1000); housekeeping(); }
            L("USB device removed");
            state = IDLE; set_state("IDLE");
            continue;
        }
        housekeeping();
        /* IDLE: give way to a session started from the TreeFrog menu */
        if (usb_mode_running()) {
            L("usb_mode.sh is running - taking over");
            takeover(); setup_gadget(); start_responder();
        }
        /* host slice */
        char m[32]; rd(MODE0, m, sizeof m);
        if (!strcmp(m, "b_peripheral")) role_host();
        for (int t = 0; t < g_host_slice_ms && !g_stop; t += 250) {
            if (host_devices() > 0) {
                msleep(1000);
                char man[64], prod[64], vid[16], cls[8];
                rd("/sys/bus/usb/devices/1-1/manufacturer", man, sizeof man);
                rd("/sys/bus/usb/devices/1-1/product", prod, sizeof prod);
                rd("/sys/bus/usb/devices/1-1/idVendor", vid, sizeof vid);
                rd("/sys/bus/usb/devices/1-1:1.0/bInterfaceClass", cls, sizeof cls);
                L("USB device attached: %s %s (idVendor=%s class=%s)", man, prod, vid, cls);
                state = DEV; set_state("DEV");
                break;
            }
            msleep(250);
        }
        if (state == DEV || g_stop) continue;
        /* peripheral slice */
        role_peripheral();
        for (int t = 0; t < g_peri_slice_ms && !g_stop; t += 250) {
            udc_state(us, sizeof us);
            if (frame_running() || strcmp(us, "not attached")) {     /* fresh bind starts "not attached" */
                L("PC detected (udc=%s)", us);
                state = PC; set_state("PC");
                break;
            }
            msleep(250);
        }
        if (state != PC) role_host();
    }
    L("stopping");
    if (g_responder > 0) { kill(g_responder, SIGTERM); waitpid(g_responder, NULL, 0); }
    role_host();
    unlink(PIDF); set_state("STOPPED");
    return 0;
}
