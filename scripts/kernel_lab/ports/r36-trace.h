/* Private HC16E310 diagnostic ABI. The last partial RAM page is unmanaged. */
#ifndef R36_TRACE_H
#define R36_TRACE_H
#define R36_TRACE_PHYS 0x02f91000
#define R36_TRACE_KSEG1 0xa2f91000
#define R36_TRACE_BYTES 0x00000e00
#define R36_TRACE_HEADER 64
#define R36_TRACE_CAPACITY (R36_TRACE_BYTES - R36_TRACE_HEADER)
#define R36_TRACE_MAGIC 0x5233364c
#define R36_TRACE_VERSION 2
#define R36_STAGE_BOOT 1
#define R36_STAGE_RELOC 2
#define R36_STAGE_COPIED 3
#define R36_STAGE_KERNEL 4
#define R36_STAGE_CONSOLE 5
#define R36_STAGE_USERSPACE 6
#define R36_STAGE_STOCK_WDT 16
#if defined(CONFIG_MACH_HICHIP) && !defined(__ASSEMBLY__)
#define R36_TRACE_VALUE(slot, value) do { \
    ((volatile unsigned int *)R36_TRACE_KSEG1)[slot] = (unsigned int)(value); \
    __asm__ volatile("sync" : : : "memory"); \
} while (0)
#define R36_BOOT_MARK(value) R36_TRACE_VALUE(4, value)
#else
#define R36_BOOT_MARK(value) do { } while (0)
#define R36_TRACE_VALUE(slot, value) do { } while (0)
#endif
#endif
