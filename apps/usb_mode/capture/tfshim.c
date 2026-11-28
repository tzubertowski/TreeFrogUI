/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Pavel Kotek
 *
 * tfshim.so - transparent driver shim with frame/audio capture.
 *
 * Point TF_DRIVER at this library. It loads the real driver (TFSHIM_REAL env,
 * else the first line of /tmp/tfshim.real, else TFSHIM_DEFAULT_REAL) and
 * re-exports every symbol of it:
 *   - functions: generated assembly trampolines (tfshim_tramp.S) that
 *     tail-jump to the real function, registers and stack untouched;
 *   - video_driver_disp_frame, sound_driver_playframe, sound_driver_init:
 *     C wrappers that forward a0..a3 unchanged and copy the frame / audio
 *     chunk into the tfcap shared memory while a recorder is attached;
 *   - data objects (g_render, hdl, ...): our .dynsym entries are re-pointed
 *     at the real driver's objects at load, so dlsym(shim, "g_render") returns
 *     the real address (on failure dlsym returns zero-filled placeholders).
 *
 * Cost while no recorder runs: one load + branch per hooked call, plus one
 * failed open() of TFCAP_PATH every TFSHIM_POLL_CALLS hooked calls.
 *
 * Signatures (TreeFrogUI_picoarch plat_sdl.c / hwdisp.c):
 *   int video_driver_disp_frame(void *src, int w, int h, int pitch_bytes)
 *   int sound_driver_init(void *device_name, int sample_rate, int channels)
 *   int sound_driver_playframe(const void *buf, int frames)   (bytes = frames*4)
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <elf.h>
#include <errno.h>
#include <fcntl.h>
#include <link.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include "tfcap.h"
#include "tfshim_syms.h"

#ifndef TFSHIM_DEFAULT_REAL
#define TFSHIM_DEFAULT_REAL "/mnt/sdcard/cubegm/driver_sf3500.so"
#endif
#define TFSHIM_REAL_FILE   "/tmp/tfshim.real"
#define TFSHIM_POLL_CALLS  16u
#define TFSHIM_EXPORT      __attribute__((visibility("default")))
#define TFSHIM_LOCAL       __attribute__((visibility("hidden")))

_Static_assert(sizeof(struct tfcap_hdr) == 256, "tfcap_hdr layout");
_Static_assert(sizeof(struct tfcap_vslot) == 64, "tfcap_vslot layout");
_Static_assert(sizeof(struct tfcap_adesc) == 32, "tfcap_adesc layout");

typedef long (*fn4_t)(long, long, long, long);

extern void *tfshim_slots[TFSHIM_NSLOTS];        /* tfshim_tramp.S */

static void *g_real;                             /* dlopen handle of the real driver */
/* Never NULL: until/unless the real driver resolves they return 0 / -1, so the
 * hot path needs no NULL check and ends in a plain tail jump. */
static long ret_zero(long a, long b, long c, long d) { (void)a; (void)b; (void)c; (void)d; return 0; }
static long ret_minus1(long a, long b, long c, long d) { (void)a; (void)b; (void)c; (void)d; return -1; }
static fn4_t g_real_disp = ret_zero, g_real_play = ret_zero, g_real_sinit = ret_minus1;
static char g_cap_path[128] = TFCAP_PATH;
static int g_quiet;

/* capture state */
static struct tfcap_hdr *volatile g_cap;         /* NULL while detached */
static uint32_t g_cap_size;
static dev_t g_cap_dev;
static ino_t g_cap_ino;
static int g_users;                              /* hooks currently inside g_cap */
static int g_busy;                               /* attach/detach in progress */
static unsigned g_poll;
static uint32_t g_last_hb, g_hb_ms;
static int g_have_stale;
static dev_t g_stale_dev;
static ino_t g_stale_ino;
static struct tfcap_wstate g_ws;
static volatile uint32_t g_rate, g_channels;     /* from sound_driver_init */

#define LOG(...)  do { fprintf(stderr, "tfshim: " __VA_ARGS__); fputc('\n', stderr); } while (0)
#define INFO(...) do { if (!g_quiet) LOG(__VA_ARGS__); } while (0)

/* ------------------------------------------------------------------ */
/* unresolved functions                                                */
/* ------------------------------------------------------------------ */
TFSHIM_LOCAL long tfshim_missing(long idx)
{
    static unsigned char warned[TFSHIM_NSLOTS];
    if (idx >= 0 && idx < TFSHIM_NSLOTS) {
        if (!warned[idx]) {
            warned[idx] = 1;
            LOG("call to unresolved driver function %s (returning 0)", tfshim_slot_names[idx]);
        }
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* loading the real driver                                             */
/* ------------------------------------------------------------------ */
static int is_self(const void *p)
{
    Dl_info a, b;
    if (!p || !dladdr(p, &a) || !dladdr((const void *)&is_self, &b)) return 0;
    return a.dli_fbase == b.dli_fbase;
}

static const char *real_path(char *buf, size_t n)
{
    const char *e = getenv("TFSHIM_REAL");
    if (e && *e) return e;
    FILE *f = fopen(TFSHIM_REAL_FILE, "r");
    if (f) {
        char *r = fgets(buf, (int)n, f);
        fclose(f);
        if (r) {
            size_t l = strlen(buf);
            while (l && (buf[l - 1] == '\n' || buf[l - 1] == '\r' || buf[l - 1] == ' ' || buf[l - 1] == '\t'))
                buf[--l] = 0;
            if (l) return buf;
        }
    }
    return TFSHIM_DEFAULT_REAL;
}

static int same_file_as_self(const char *path)
{
    Dl_info me;
    struct stat a, b;
    if (!dladdr((const void *)&same_file_as_self, &me) || !me.dli_fname) return 0;
    if (stat(path, &a) != 0 || stat(me.dli_fname, &b) != 0) return 0;
    return a.st_dev == b.st_dev && a.st_ino == b.st_ino;
}

static void *resolve(const char *name)
{
    void *p = dlsym(g_real, name);
    if (p && is_self(p)) p = NULL;               /* never jump back into ourselves */
    return p;
}

/* Our own load base and program headers (found by address, no dlopen). */
struct self_query { uintptr_t addr; ElfW(Addr) base; const ElfW(Phdr) *phdr; int phnum; };

static int self_cb(struct dl_phdr_info *info, size_t size, void *data)
{
    struct self_query *q = data;
    (void)size;
    for (int i = 0; i < info->dlpi_phnum; i++) {
        const ElfW(Phdr) *ph = &info->dlpi_phdr[i];
        if (ph->p_type == PT_LOAD && q->addr >= info->dlpi_addr + ph->p_vaddr &&
            q->addr < info->dlpi_addr + ph->p_vaddr + ph->p_memsz) {
            q->base = info->dlpi_addr; q->phdr = info->dlpi_phdr; q->phnum = info->dlpi_phnum;
            return 1;
        }
    }
    return 0;
}

/* Re-point our exported data objects at the real driver's objects by
 * rewriting st_value in our own .dynsym (dlsym returns l_addr + st_value). */
static int alias_objects(void)
{
#if TFSHIM_NOBJS > 0
    struct self_query q = { (uintptr_t)&alias_objects, 0, NULL, 0 };
    if (!dl_iterate_phdr(self_cb, &q) || !q.phdr) return -1;
    ElfW(Addr) base = q.base, symtab = 0, strtab = 0;
    const ElfW(Dyn) *dyn = NULL;
    for (int p = 0; p < q.phnum; p++)
        if (q.phdr[p].p_type == PT_DYNAMIC) dyn = (const ElfW(Dyn) *)(base + q.phdr[p].p_vaddr);
    if (!dyn) return -1;

    unsigned long nsyms = 0;
    for (const ElfW(Dyn) *d = dyn; d->d_tag != DT_NULL; d++) {
        if (d->d_tag == DT_SYMTAB) symtab = d->d_un.d_ptr;
        else if (d->d_tag == DT_STRTAB) strtab = d->d_un.d_ptr;
#ifdef DT_MIPS_SYMTABNO
        else if (d->d_tag == DT_MIPS_SYMTABNO) nsyms = d->d_un.d_val;
#endif
        else if (d->d_tag == DT_HASH && !nsyms) {
            ElfW(Addr) hp = d->d_un.d_ptr < base ? d->d_un.d_ptr + base : d->d_un.d_ptr;
            nsyms = ((const uint32_t *)hp)[1];
        }
    }
    if (!symtab || !strtab || !nsyms) return -1;
    /* MIPS keeps .dynamic read-only and unrelocated; other ports relocate it */
    if (symtab < base) symtab += base;
    if (strtab < base) strtab += base;
    long ps = sysconf(_SC_PAGESIZE);
    if (ps <= 0) ps = 4096;

    int done = 0;
    ElfW(Sym) *syms = (ElfW(Sym) *)symtab;
    for (unsigned long i = 1; i < nsyms; i++) {
        const char *nm = (const char *)strtab + syms[i].st_name;
        if (ELF32_ST_TYPE(syms[i].st_info) != STT_OBJECT || syms[i].st_shndx == SHN_UNDEF) continue;
        for (int k = 0; k < TFSHIM_NOBJS; k++) {
            if (strcmp(nm, tfshim_objs[k].name) != 0) continue;
            void *real = resolve(nm);
            if (!real) { LOG("data symbol %s not found in real driver", nm); break; }
            /* original protection of the page holding this entry */
            int prot = PROT_READ;
            ElfW(Addr) ea = (ElfW(Addr))&syms[i];
            for (int p = 0; p < q.phnum; p++) {
                const ElfW(Phdr) *ph = &q.phdr[p];
                if (ph->p_type == PT_LOAD && ea >= base + ph->p_vaddr && ea < base + ph->p_vaddr + ph->p_memsz)
                    prot = ((ph->p_flags & PF_R) ? PROT_READ : 0) | ((ph->p_flags & PF_W) ? PROT_WRITE : 0) |
                           ((ph->p_flags & PF_X) ? PROT_EXEC : 0);
            }
            uintptr_t pg = (uintptr_t)ea & ~((uintptr_t)ps - 1);
            uintptr_t pe = ((uintptr_t)ea + sizeof(ElfW(Sym)) + (uintptr_t)ps - 1) & ~((uintptr_t)ps - 1);
            if (!(prot & PROT_WRITE) && mprotect((void *)pg, pe - pg, prot | PROT_WRITE) != 0) {
                LOG("mprotect(.dynsym) failed: %s; %s stays a placeholder", strerror(errno), nm);
                break;
            }
            syms[i].st_value = (ElfW(Addr))((uintptr_t)real - (uintptr_t)base);
            if (!(prot & PROT_WRITE)) mprotect((void *)pg, pe - pg, prot);
            done++;
            break;
        }
    }
    return done;
#else
    return 0;
#endif
}

__attribute__((constructor)) static void tfshim_init(void)
{
    char buf[512];
    const char *e;
    g_quiet = (e = getenv("TFSHIM_QUIET")) && *e && *e != '0';
    if ((e = getenv("TFCAP_PATH")) && *e && strlen(e) < sizeof g_cap_path)
        strcpy(g_cap_path, e);

    const char *path = real_path(buf, sizeof buf);
    if (same_file_as_self(path)) {
        LOG("real driver path %s is this shim itself; refusing to load it", path);
        return;
    }
    g_real = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    if (!g_real) {
        LOG("dlopen(%s, RTLD_NOW) failed: %s; retrying lazily", path, dlerror());
        g_real = dlopen(path, RTLD_LAZY | RTLD_LOCAL);
    }
    if (!g_real) {
        LOG("cannot load real driver %s: %s (all driver calls will return 0)", path, dlerror());
        return;
    }
    int ok = 0;
    for (int i = 0; i < TFSHIM_NSLOTS; i++) {
        void *p = resolve(tfshim_slot_names[i]);
        if (p) { tfshim_slots[i] = p; ok++; }
        else LOG("real driver lacks %s", tfshim_slot_names[i]);
    }
    static const char *const wn[3] = { "video_driver_disp_frame", "sound_driver_playframe", "sound_driver_init" };
    fn4_t *const wp[3] = { &g_real_disp, &g_real_play, &g_real_sinit };
    for (int i = 0; i < 3; i++) {
        void *p = resolve(wn[i]);
        if (p) { *wp[i] = (fn4_t)p; ok++; }
        else LOG("real driver lacks %s", wn[i]);
    }
    int objs = alias_objects();
    INFO("real driver %s: %d/%d functions, %d/%d data objects aliased, capture file %s",
         path, ok, TFSHIM_NEXPORT_FUNCS, objs, TFSHIM_NOBJS, g_cap_path);
}

/* ------------------------------------------------------------------ */
/* capture                                                             */
/* ------------------------------------------------------------------ */
/* No 64-bit division anywhere in the shim: zig's compiler-rt leaves such
 * helpers as unresolved imports in MIPS shared objects. */
struct tnow { uint64_t ns; uint32_t ms; };

static inline struct tnow now(void)
{
    struct timespec t;
    struct tnow r;
    clock_gettime(CLOCK_MONOTONIC, &t);
    r.ns = (uint64_t)(uint32_t)t.tv_sec * 1000000000ull + (uint32_t)t.tv_nsec;
    r.ms = (uint32_t)t.tv_sec * 1000u + (uint32_t)t.tv_nsec / 1000000u;
    return r;
}

static void cap_detach(int stale)
{
    if (__atomic_exchange_n(&g_busy, 1, __ATOMIC_ACQUIRE)) return;
    struct tfcap_hdr *h = __atomic_exchange_n(&g_cap, NULL, __ATOMIC_SEQ_CST);
    if (h) {
        while (__atomic_load_n(&g_users, __ATOMIC_SEQ_CST))
            sched_yield();
        munmap((void *)h, g_cap_size);
        if (stale) { g_have_stale = 1; g_stale_dev = g_cap_dev; g_stale_ino = g_cap_ino; }
        INFO("capture detached (%s)", stale ? "recorder stopped responding" : "recorder closed");
    }
    __atomic_store_n(&g_busy, 0, __ATOMIC_RELEASE);
}

static __attribute__((noinline)) void poll_attach(void)
{
    g_poll = 0;
    if (__atomic_exchange_n(&g_busy, 1, __ATOMIC_ACQUIRE)) return;
    if (g_cap) goto out;
    int fd = open(g_cap_path, O_RDWR | O_CLOEXEC);
    if (fd < 0) goto out;
    struct stat st;
    if (fstat(fd, &st) != 0 || st.st_size < (off_t)TFCAP_HDR_BYTES || st.st_size > (off_t)(64 << 20) ||
        (g_have_stale && st.st_dev == g_stale_dev && st.st_ino == g_stale_ino)) {
        close(fd);
        goto out;
    }
    void *p = mmap(NULL, (size_t)st.st_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);
    if (p == MAP_FAILED) goto out;
    struct tfcap_hdr *h = p;
    if (tfcap_validate(h, (uint32_t)st.st_size) != 0 || h->state != TFCAP_STATE_RUNNING) {
        munmap(p, (size_t)st.st_size);
        goto out;
    }
    g_cap_size = (uint32_t)st.st_size;
    g_cap_dev = st.st_dev; g_cap_ino = st.st_ino;
    g_last_hb = h->heartbeat;
    g_hb_ms = now().ms;
    memset(&g_ws, 0, sizeof g_ws);
    h->shim_pid = (uint32_t)getpid();
    h->shim_attaches++;
    if (g_rate) { h->a_rate = g_rate; h->a_channels = g_channels; }
    __atomic_store_n(&g_cap, h, __ATOMIC_SEQ_CST);
    INFO("capture attached to %s", g_cap_path);
out:
    __atomic_store_n(&g_busy, 0, __ATOMIC_RELEASE);
}

/* Enter the capture section; NULL if detached. Pair with cap_leave(). */
static inline struct tfcap_hdr *cap_enter(void)
{
    __atomic_add_fetch(&g_users, 1, __ATOMIC_SEQ_CST);
    struct tfcap_hdr *h = __atomic_load_n(&g_cap, __ATOMIC_SEQ_CST);
    if (!h) __atomic_sub_fetch(&g_users, 1, __ATOMIC_SEQ_CST);
    return h;
}
static inline void cap_leave(void) { __atomic_sub_fetch(&g_users, 1, __ATOMIC_SEQ_CST); }

/* 0 = alive, 1 = closed by the recorder, 2 = heartbeat stale */
static int cap_check(struct tfcap_hdr *h, uint32_t ms)
{
    if (h->state != TFCAP_STATE_RUNNING) return 1;
    uint32_t hb = h->heartbeat;
    if (hb != g_last_hb) { g_last_hb = hb; g_hb_ms = ms; return 0; }
    return (uint32_t)(ms - g_hb_ms) > TFCAP_STALE_MS ? 2 : 0;
}

static __attribute__((noinline)) void cap_video(const void *src, int w, int h, int pitch)
{
    struct tfcap_hdr *c = cap_enter();
    if (!c) return;
    struct tnow t = now();
    int st = cap_check(c, t.ms);
    if (!st && (c->enabled & TFCAP_EN_VIDEO)) {
        c->v_calls++;
        tfcap_write_video(c, &g_ws, src, w, h, pitch, t.ns);
    }
    cap_leave();
    if (st) cap_detach(st == 2);
}

static __attribute__((noinline)) void cap_audio(const void *buf, long frames)
{
    struct tfcap_hdr *c = cap_enter();
    if (!c) return;
    struct tnow t = now();
    int st = cap_check(c, t.ms);
    if (!st && (c->enabled & TFCAP_EN_AUDIO)) {
        c->a_calls++;
        if (g_rate) { c->a_rate = g_rate; c->a_channels = g_channels; }
        if (frames > 0 && frames <= (long)(TFCAP_AMAX_CHUNK / 4u))
            tfcap_write_audio(c, buf, (uint32_t)frames * 4u, t.ns);
        else
            c->a_bad_len++;
    }
    cap_leave();
    if (st) cap_detach(st == 2);
}

/* ------------------------------------------------------------------ */
/* intercepted exports                                                 */
/* ------------------------------------------------------------------ */
/* Hot path: one load + branch (plus the poll counter while detached), then a
 * tail jump to the real function: no stack frame, a0-a3, stack arguments and
 * ra reach the driver untouched (needs -mllvm -mips-tail-calls=1, checked by
 * tests/emu_shim.py). Capture and attach polling live in noinline slow paths. */
static __attribute__((noinline)) long slow_disp(long src, long w, long h, long pitch)
{
    if (g_cap) cap_video((const void *)src, (int)w, (int)h, (int)pitch);
    else poll_attach();
    __attribute__((musttail)) return g_real_disp(src, w, h, pitch);
}

static __attribute__((noinline)) long slow_play(long buf, long frames, long a2, long a3)
{
    if (g_cap) cap_audio((const void *)buf, frames);
    else poll_attach();
    __attribute__((musttail)) return g_real_play(buf, frames, a2, a3);
}

TFSHIM_EXPORT long video_driver_disp_frame(long src, long w, long h, long pitch)
{
    if (__builtin_expect(g_cap != NULL || ++g_poll >= TFSHIM_POLL_CALLS, 0))
        __attribute__((musttail)) return slow_disp(src, w, h, pitch);
    __attribute__((musttail)) return g_real_disp(src, w, h, pitch);
}

TFSHIM_EXPORT long sound_driver_playframe(long buf, long frames, long a2, long a3)
{
    if (__builtin_expect(g_cap != NULL || ++g_poll >= TFSHIM_POLL_CALLS, 0))
        __attribute__((musttail)) return slow_play(buf, frames, a2, a3);
    __attribute__((musttail)) return g_real_play(buf, frames, a2, a3);
}

TFSHIM_EXPORT long sound_driver_init(long dev, long rate, long channels, long a3)
{
    if (rate >= 8000 && rate <= 192000 && (channels == 1 || channels == 2)) {
        g_rate = (uint32_t)rate; g_channels = (uint32_t)channels;
    } else {
        g_rate = 0; g_channels = 0;              /* caller passed no/odd arguments */
    }
    __attribute__((musttail)) return g_real_sinit(dev, rate, channels, a3);
}
