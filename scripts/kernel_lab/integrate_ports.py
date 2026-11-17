"""Install this workspace's private driver overlay into the pinned kernel tree."""
from pathlib import Path
import os
import shutil
import sys

src = Path(sys.argv[1])
lab = Path(__file__).resolve().parent
dest = src / "drivers/soc/r36-lab"
dest.mkdir(exist_ok=True)
for path in (lab / "ports").iterdir():
    if path.is_file():
        shutil.copy2(path, dest / path.name)
makefile = src / "drivers/soc/Makefile"
line = "obj-$(CONFIG_MACH_HICHIP) += r36-lab/"
text = makefile.read_text()
if line not in text:
    makefile.write_text(text.rstrip() + "\n" + line + "\n")

# Default isolated builds use gadget/PIO only; OTG+Wi-Fi/BT builds opt into dual-role.
kconfig = src / "drivers/usb/musb/Kconfig"
text = kconfig.read_text()
before, block = text.split("config USB_MUSB_HC16XX\n", 1)
middle, after = block.split('comment "MUSB DMA mode"', 1)
otg_mode = os.environ.get("R36_OTG_WIFI_BT") == "1"
if otg_mode:
    if "\tselect USB_MUSB_GADGET\n" in middle:
        middle = middle.replace("\tselect USB_MUSB_GADGET\n", "\tselect USB_MUSB_DUAL_ROLE\n")
    elif "\tselect USB_MUSB_DUAL_ROLE\n" not in middle:
        raise ValueError("unexpected HC16xx Kconfig block")
else:
    if "\tselect USB_MUSB_DUAL_ROLE\n" in middle:
        middle = middle.replace("\tselect USB_MUSB_DUAL_ROLE\n", "\tselect USB_MUSB_GADGET\n")
    elif "\tselect USB_MUSB_GADGET\n" not in middle:
        raise ValueError("unexpected HC16xx Kconfig block")
kconfig.write_text(before + "config USB_MUSB_HC16XX\n" + middle + 'comment "MUSB DMA mode"' + after)

# Core start/stop own controller IRQ masks; also fix UTMI 8-bit width,
# DEVCTL.SESSION and per-device dr_mode propagation for host/OTG operation.
from usb_overlay import patch_musb_host_otg_support, patch_musb_irq_lifecycle
usb_glue = src / "drivers/usb/musb/hc16xx.c"
patched_usb = patch_musb_irq_lifecycle(usb_glue.read_text())
usb_glue.write_text(patch_musb_host_otg_support(patched_usb))

# The external timer driver gates the same counter used by its clocksource.
# Use the CPU Count/Compare path used by this board's stock Linux instead.
arch_config = src / "arch/mips/Kconfig"
text = arch_config.read_text()
before, block = text.split("config MACH_HICHIP\n", 1)
middle, after = block.split("config MACH_INGENIC\n", 1)
if "\tselect MIPS_EXTERNAL_TIMER\n" in middle:
    middle = middle.replace("\tselect MIPS_EXTERNAL_TIMER\n",
                            "\tselect CEVT_R4K\n\tselect CSRC_R4K\n")
elif "\tselect CEVT_R4K\n" not in middle or "\tselect CSRC_R4K\n" not in middle:
    raise ValueError("unexpected HC16xx clockevent Kconfig block")
arch_config.write_text(before + "config MACH_HICHIP\n" + middle + "config MACH_INGENIC\n" + after)

# Preserve watchdog across clock cleanup, including diagnostic boot failures.
clock_file = src / "drivers/clk/clk-hc16xx.c"
text = clock_file.read_text()
needle = "hc16xx_parent_name(g->parent, hosc_name),\n\t\t\t\tCLK_SET_RATE_PARENT,"
replacement = ("hc16xx_parent_name(g->parent, hosc_name),\n"
               "\t\t\t\tCLK_SET_RATE_PARENT |\n"
               "\t\t\t\t(g->id == HC16XX_CLK_WATCHDOG ? CLK_IS_CRITICAL : 0),")
if needle in text:
    text = text.replace(needle, replacement, 1)
elif replacement not in text:
    raise ValueError("unexpected clock gate registration")
clock_file.write_text(text)

# Peripheral lines are shared SoC interrupts, not CPU-local per-CPU IRQs.
# Linux 7 prints zero device counts when handle_percpu_irq leaves tot_count=0.
# Simple flow serializes actions and counts normal IRQs; devices retain their
# own acknowledgement, as in the original demultiplexed interrupt controller.
irq_file = src / "drivers/irqchip/irq-hc16xx-intc.c"
text = irq_file.read_text()
irq_old = "irq_set_chip_and_handler(irq, &hc16xx_irq_chip, handle_percpu_irq);"
irq_new = "irq_set_chip_and_handler(irq, &hc16xx_irq_chip, handle_simple_irq);"
if text.count(irq_old) == 1:
    text = text.replace(irq_old, irq_new, 1)
elif text.count(irq_new) != 1:
    raise ValueError("unexpected HC16xx IRQ flow handler")
irq_file.write_text(text)

# A breadcrumb before any C code/console initialization in the new kernel.
shutil.copy2(lab / "ports/r36-trace.h", src / "arch/mips/include/asm/r36-trace.h")
head = src / "arch/mips/kernel/head.S"
text = head.read_text()
include = "#include <asm/r36-trace.h>"
if include not in text:
    text = text.replace("#include <kernel-entry-init.h>", "#include <kernel-entry-init.h>\n" + include, 1)
marker = "NESTED(kernel_entry, 16, sp)\t\t\t# kernel entry point"
breadcrumb = (marker + "\n\n#ifdef CONFIG_MACH_HICHIP\n"
              "\tli t0, R36_TRACE_KSEG1\n\tli t1, R36_STAGE_KERNEL\n"
              "\tsw t1, 16(t0)\n\tsync\n#endif")
if "li t1, R36_STAGE_KERNEL" not in text:
    if marker not in text:
        raise ValueError("unexpected kernel_entry assembly")
    text = text.replace(marker, breadcrumb, 1)
head.write_text(text)

def patch_c(path, anchors):
    text = path.read_text()
    include = "#include <asm/r36-trace.h>"
    if include not in text:
        index = text.index("#include ")
        text = text[:index] + "#ifdef CONFIG_MACH_HICHIP\n" + include + "\n#else\n" \
            "#define R36_BOOT_MARK(value) do { } while (0)\n" \
            "#define R36_TRACE_VALUE(slot, value) do { } while (0)\n#endif\n" + text[index:]
    for anchor, replacement in anchors:
        if replacement in text:
            continue
        if text.count(anchor) != 1:
            raise ValueError(f"unexpected breadcrumb anchor in {path}: {anchor!r}")
        text = text.replace(anchor, replacement, 1)
    path.write_text(text)

patch_c(src / "init/main.c", [
    ("\tset_task_stack_end_magic(&init_task);", "\tR36_BOOT_MARK(35);\n\tset_task_stack_end_magic(&init_task);"),
    ("\tsetup_arch(&command_line);", "\tR36_BOOT_MARK(36);\n\tsetup_arch(&command_line);\n\tR36_BOOT_MARK(51);"),
    ("\ttrap_init();", "\tR36_BOOT_MARK(52);\n\ttrap_init();"),
    ("\tmm_core_init();", "\tmm_core_init();\n\tR36_BOOT_MARK(53);"),
    ("\tinit_IRQ();", "\tR36_BOOT_MARK(54);\n\tinit_IRQ();\n\tR36_BOOT_MARK(55);"),
    ("\ttime_init();", "\tR36_BOOT_MARK(56);\n\ttime_init();\n\tR36_BOOT_MARK(57);"),
    ("\tconsole_init();", "\tR36_BOOT_MARK(58);\n\tconsole_init();\n\tR36_BOOT_MARK(59);"),
])
patch_c(src / "arch/mips/kernel/setup.c", [
    ("\tcpu_probe();", "\tR36_BOOT_MARK(40);\n\tcpu_probe();\n\tR36_BOOT_MARK(41);"),
    ("\tmips_cm_probe();", "\tmips_cm_probe();\n\tR36_BOOT_MARK(42);"),
    ("\tcpu_report();", "\tR36_BOOT_MARK(45);\n\tcpu_report();"),
    ("\tarch_mem_init(cmdline_p);", "\tR36_BOOT_MARK(46);\n\tarch_mem_init(cmdline_p);\n\tR36_BOOT_MARK(47);"),
    ("\tcpu_cache_init();", "\tR36_BOOT_MARK(48);\n\tcpu_cache_init();\n\tR36_BOOT_MARK(49);"),
    ("\tpagetable_init();", "\tpagetable_init();\n\tR36_BOOT_MARK(50);"),
])
patch_c(src / "arch/mips/generic/init.c", [
    ("\tplat_get_fdt();", "\tR36_BOOT_MARK(43);\n\tR36_TRACE_VALUE(12, fw_arg0);\n"
     "\tR36_TRACE_VALUE(13, fw_arg1);\n\tplat_get_fdt();\n"
     "\tR36_TRACE_VALUE(14, (unsigned long)fdt);\n\tR36_BOOT_MARK(44);"),
])

text = head.read_text()
for anchor, replacement in [
    ("\tLONG_S\t\ta0, fw_arg0", "#ifdef CONFIG_MACH_HICHIP\n\tli t7, R36_TRACE_KSEG1\n"
     "\tli t8, 33\n\tsw t8, 16(t7)\n\tsync\n#endif\n\tLONG_S\t\ta0, fw_arg0"),
    ("#ifdef CONFIG_RELOCATABLE\n\t/* Copy kernel", "#ifdef CONFIG_MACH_HICHIP\n\tli t7, R36_TRACE_KSEG1\n"
     "\tli t8, 34\n\tsw t8, 16(t7)\n\tsync\n#endif\n#ifdef CONFIG_RELOCATABLE\n\t/* Copy kernel"),
]:
    if replacement not in text:
        if text.count(anchor) != 1:
            raise ValueError("unexpected head.S breadcrumb anchor")
        text = text.replace(anchor, replacement, 1)
head.write_text(text)
print("Installed R36 overlay: gadget-only PIO, CPU Count/Compare timers")
