/* RAM-only warm loader for the measured stock 4.4.186 ABI (GPL-2.0). */
typedef unsigned int u32;
typedef unsigned long size_t;
typedef long ssize_t;
typedef long long loff_t;

/* These interfaces and layouts are checked against stock dsc.ko DWARF. */
extern unsigned long __get_free_pages(unsigned int, unsigned int);
extern void free_pages(unsigned long, unsigned int);
extern void *vmalloc(unsigned long);
extern void vfree(const void *);
extern void *memset(void *, int, size_t);
extern void *memcpy(void *, const void *, size_t);
extern int memcmp(const void *, const void *, size_t);
extern int printk(const char *, ...);
extern void *filp_open(const char *, int, unsigned int);
extern int filp_close(void *, void *);
extern int kernel_read(void *, loff_t, char *, unsigned long);
extern void *proc_create_data(const char *, unsigned int, void *, const void *, void *);
extern ssize_t simple_read_from_buffer(void *, size_t, loff_t *, const void *, size_t);
extern char __this_module[];
extern char r36_reloc_start[], r36_reloc_end[];
extern void r36_handoff(u32 flush, u32 control, u32 trampoline);

#include "image_bounds.h"
#include "ports/r36-trace.h"

#define PAGE 4096u
#define GFP 0x024000c0u
#define PHYS(v) ((u32)(v) & 0x1fffffffu)
#define UNCACHED(v) (PHYS(v) | 0xa0000000u)
#define MAX_PAGES 12288u
#define PREPARE 0x52360001u
#define BOOT 0x52360002u
#define CANCEL 0x52360003u
#define PROBE 0x52360004u

static const struct { u32 words[16]; unsigned char guard[16]; } r36_binding
__attribute__((used, section(".r36.binding"))) = {
    {0x52333642, 1, IMAGE_LOAD, IMAGE_ENTRY, IMAGE_FILESZ, IMAGE_MEMSZ,
     DTB_LOAD, DTB_SIZE, STAGED_CRC32, WATCHDOG_RATE, WATCHDOG_SECONDS,
     R36_TRACE_PHYS, R36_TRACE_BYTES, CACHE_FLUSH_ADDRESS, 320, 108},
    CACHE_FLUSH_BYTES
};

struct pair { u32 source, destination; };
struct page_list { u32 next, count; struct pair entries[511]; };
struct control { u32 list, entry, dtb, expected_crc; u32 crc_table[256]; };
struct held_page { u32 address, usable; };
static struct held_page *held;
static u32 num_held, num_copied, num_blocked, control_page, trampoline_page;
static struct page_list *tail;
static u32 first_list, ready;
static volatile u32 busy;
static const char *state = "idle\n";

static int is_error(const void *p) { return (u32)p >= 0xfffff001u; }

static int in_destination(u32 p)
{
    u32 end = (IMAGE_LOAD + IMAGE_MEMSZ + PAGE - 1) & ~(PAGE - 1);
    return (p >= PHYS(IMAGE_LOAD) && p < PHYS(end)) ||
           (p >= PHYS(DTB_LOAD) && p < PHYS(DTB_LOAD) + DTB_PAGES * PAGE);
}

static u32 safe_page(void)
{
    while (num_held < MAX_PAGES) {
        u32 p = __get_free_pages(GFP, 0);
        if (!p) return 0;
        held[num_held].address = p;
        held[num_held].usable = !in_destination(PHYS(p));
        num_held++;
        if (!in_destination(PHYS(p))) {
            memset((void *)p, 0, PAGE);
            return p;
        }
        num_blocked++;
    }
    return 0;
}

static void clear_stage(void)
{
    u32 i;
    if (held) {
        for (i = 0; i < num_held; i++)
            if (held[i].address) free_pages(held[i].address, 0);
        vfree(held);
    }
    held = 0;
    num_held = num_copied = num_blocked = control_page = trampoline_page = 0;
    first_list = ready = 0;
    tail = 0;
    state = "idle\n";
}

static int add_copy(u32 source, u32 destination)
{
    if (!tail || tail->count == 511) {
        u32 p = safe_page();
        if (!p) return -12;
        if (tail) tail->next = UNCACHED(p);
        else first_list = UNCACHED(p);
        tail = (struct page_list *)p;
    }
    tail->entries[tail->count].source = UNCACHED(source);
    tail->entries[tail->count].destination = UNCACHED(destination);
    tail->count++;
    num_copied++;
    return 0;
}

static int stage_file(const char *path, u32 destination, u32 filesize, u32 memsize)
{
    void *f = filp_open(path, 0, 0);
    u32 offset;
    int rc = 0;
    if (is_error(f)) return (int)f;
    for (offset = 0; offset < memsize; offset += PAGE) {
        u32 p = safe_page();
        u32 count = offset < filesize ? filesize - offset : 0;
        u32 got = 0;
        if (!p) { rc = -12; break; }
        if (count > PAGE) count = PAGE;
        while (got < count) {
            int n = kernel_read(f, (loff_t)offset + got, (char *)p + got, count - got);
            if (n <= 0) { rc = n ? n : -5; break; }
            got += n;
        }
        if (rc) break;
        rc = add_copy(p, destination + offset);
        if (rc) break;
    }
    if (!rc) {
        char extra;
        rc = kernel_read(f, (loff_t)filesize, &extra, 1) == 0 ? 0 : -22;
    }
    filp_close(f, 0);
    return rc;
}

static int prepare(void)
{
    struct control *c;
    u32 i;
    int rc;
    clear_stage();
    held = vmalloc(MAX_PAGES * sizeof(*held));
    if (!held) return -12;
    memset(held, 0, MAX_PAGES * sizeof(*held));
    control_page = safe_page();
    trampoline_page = safe_page();
    if (!control_page || !trampoline_page) { rc = -12; goto fail; }
    if ((size_t)(r36_reloc_end - r36_reloc_start) > PAGE - 16) { rc = -22; goto fail; }
    memcpy((void *)trampoline_page, r36_reloc_start, r36_reloc_end - r36_reloc_start);
    rc = stage_file("/mnt/sdcard/cubegm/r36-vmlinux.bin", IMAGE_LOAD, IMAGE_FILESZ, IMAGE_MEMSZ);
    if (rc) goto fail;
    rc = stage_file("/mnt/sdcard/cubegm/r36-lab.dtb", DTB_LOAD, DTB_SIZE, DTB_SIZE);
    if (rc) goto fail;
    c = (struct control *)control_page;
    c->list = first_list;
    c->entry = IMAGE_ENTRY;
    c->dtb = DTB_LOAD;
    c->expected_crc = STAGED_CRC32;
    for (i = 0; i < 256; i++) {
        u32 value = i, bit;
        for (bit = 0; bit < 8; bit++)
            value = (value >> 1) ^ ((value & 1) ? 0xedb88320u : 0);
        c->crc_table[i] = value;
    }
    for (i = 0; i < num_held; i++) {
        if (!held[i].usable) {
            free_pages(held[i].address, 0);
            held[i].address = 0;
        }
    }
    ready = 1;
    state = "prepared\n";
    printk("r36boot: prepared %u pages, %u excluded; entry=%08x dtb=%08x control=%08x trampoline=%08x\n",
           num_copied, num_blocked, IMAGE_ENTRY, DTB_LOAD, control_page, trampoline_page);
    return 0;
fail:
    clear_stage();
    state = "prepare failed; see ioctl error\n";
    return rc;
}

static ssize_t status_read(void *file, void *buffer, size_t count, loff_t *position)
{
    size_t n = 0;
    (void)file;
    while (state[n]) n++;
    return simple_read_from_buffer(buffer, count, position, state, n);
}

static ssize_t pages_read(void *file, void *buffer, size_t count, loff_t *position)
{
    ssize_t result;
    (void)file;
    if (__sync_lock_test_and_set(&busy, 1)) return -16;
    if (!ready) result = -22;
    else result = simple_read_from_buffer(buffer, count, position, held,
                                         num_held * sizeof(*held));
    __sync_lock_release(&busy);
    return result;
}

static long control_ioctl(void *file, unsigned int cmd, unsigned long arg)
{
    int rc = 0;
    void (*flush)(void) = (void (*)(void))CACHE_FLUSH_ADDRESS;
    (void)file; (void)arg;
    if (__sync_lock_test_and_set(&busy, 1)) return -16;
    if (cmd == PREPARE) rc = prepare();
    else if (cmd == CANCEL) clear_stage();
    else if (cmd == PROBE) {
        u32 old_status;
        u32 (*fn)(void);
        u32 code[4] = {0x3c025236, 0x34420004, 0x03e00008, 0};
        if (!ready) { rc = -22; goto out; }
        memcpy((void *)(trampoline_page + PAGE - 16), code, sizeof(code));
        __asm__ volatile("mfc0 %0,$12\n\tdi\n\tehb" : "=r"(old_status) : : "memory");
        flush();
        fn = (void *)(UNCACHED(trampoline_page) + PAGE - 16);
        rc = fn() == PROBE ? 0 : -5;
        __asm__ volatile("mtc0 %0,$12\n\tehb" : : "r"(old_status) : "memory");
        printk("r36boot: uncached trampoline probe rc=%d\n", rc);
    } else if (cmd == BOOT) {
        u32 control, code;
        volatile u32 *trace = (volatile u32 *)R36_TRACE_KSEG1;
        volatile u32 *gate = (volatile u32 *)0xb8800060;
        volatile u32 *watchdog = (volatile u32 *)0xb8818500;
        u32 tag;
        if (!ready) { rc = -22; goto out; }
        printk("r36boot: RAM-only handoff to %08x\n", IMAGE_ENTRY);
        control = UNCACHED(control_page);
        code = UNCACHED(trampoline_page);
        __asm__ volatile("mfc0 %0,$9" : "=r"(tag));
        trace[0] = R36_TRACE_MAGIC;
        trace[1] = 0;
        trace[2] = R36_TRACE_CAPACITY;
        trace[3] = R36_TRACE_VERSION;
        trace[4] = R36_STAGE_BOOT;
        trace[5] = IMAGE_ENTRY;
        trace[6] = control;
        trace[7] = code;
        trace[8] = WATCHDOG_RATE;
        trace[9] = WATCHDOG_SECONDS;
        trace[10] = tag;
        trace[11] = num_copied;
        trace[12] = trace[13] = trace[14] = trace[15] = 0;
        *gate &= ~(1u << 22);
        __asm__ volatile("sync" : : : "memory");
        watchdog[0] = 0u - WATCHDOG_RATE * WATCHDOG_SECONDS;
        watchdog[1] = 0x26;
        __asm__ volatile("sync" : : : "memory");
        r36_handoff(CACHE_FLUSH_ADDRESS, control, code);
        for (;;) __asm__ volatile("wait");
    } else rc = -22;
out:
    __sync_lock_release(&busy);
    return rc;
}

static const unsigned long fops[27] = {
    [0] = (unsigned long)&__this_module,
    [2] = (unsigned long)status_read,
    [8] = (unsigned long)control_ioctl,
};

static const unsigned long pages_fops[27] = {
    [0] = (unsigned long)&__this_module,
    [2] = (unsigned long)pages_read,
};

int init_module(void)
{
    static const unsigned char expected[] = CACHE_FLUSH_BYTES;
    if (memcmp((void *)CACHE_FLUSH_ADDRESS, expected, sizeof(expected))) return -22;
    if (!proc_create_data("r36boot", 0600, 0, fops, 0)) return -12;
    if (!proc_create_data("r36boot_pages", 0400, 0, pages_fops, 0)) return -12;
    printk("r36boot: stock ABI verified; /proc/r36boot ready (idle)\n");
    return 0;
}
