// SPDX-License-Identifier: GPL-2.0
/* Diagnostic ring in the matching DTS no-map reserved-memory region. */
#include <linux/console.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/of_fdt.h>
#include <asm/addrspace.h>
#include "r36-trace.h"

#define LOG_PHYS R36_TRACE_PHYS
#define LOG_SIZE R36_TRACE_BYTES
#define LOG_MAGIC R36_TRACE_MAGIC
#define CAPACITY R36_TRACE_CAPACITY

static void ram_write(struct console *console, const char *text, unsigned int count)
{
    void __iomem *base = (void __iomem *)CKSEG1ADDR(LOG_PHYS);
    u32 position = readl(base + 4);
    unsigned int i;
    (void)console;
    for (i = 0; i < count; i++) {
        writeb(text[i], base + R36_TRACE_HEADER + position % CAPACITY);
        position++;
    }
    writel(position, base + 4);
}

static struct console ram_console = {
    .name = "r36ram", .write = ram_write,
    .flags = CON_PRINTBUFFER | CON_ENABLED, .index = -1,
};

static int __init find_reserved_log(unsigned long node, const char *name,
                                    int depth, void *unused)
{
    const __be32 *reg;
    int length;
    (void)name; (void)depth; (void)unused;
    if (!of_flat_dt_is_compatible(node, "r36lab,ramconsole")) return 0;
    reg = of_get_flat_dt_prop(node, "reg", &length);
    return reg && length == 8 && be32_to_cpu(reg[0]) == LOG_PHYS &&
           be32_to_cpu(reg[1]) == LOG_SIZE;
}

static int __init ram_console_init(void)
{
    void __iomem *base = (void __iomem *)CKSEG1ADDR(LOG_PHYS);
    if (!of_scan_flat_dt(find_reserved_log, NULL)) return 0;
    writel(LOG_MAGIC, base);
    writel(0, base + 4);
    writel(CAPACITY, base + 8);
    writel(R36_TRACE_VERSION, base + 12);
    writel(R36_STAGE_CONSOLE, base + 16);
    register_console(&ram_console);
    return 0;
}
console_initcall(ram_console_init);
