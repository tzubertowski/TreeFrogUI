"""Pure decoder for the private, retained diagnostic trace ABI."""
import struct

PHYSICAL = 0x02F91000
SIZE = 3584
HEADER = 64
CAPACITY = SIZE - HEADER
MAGIC = 0x5233364C
VERSION = 2
STAGES = {
    1: "loader armed watchdog", 2: "uncached relocation entered",
    3: "destination CRC verified; jumping to kernel", 4: "kernel_entry reached",
    5: "kernel RAM console initialized", 6: "PID1 userspace reached",
    16: "stock watchdog reset trial", 17: "copy complete; checking destination CRC",
    33: "BSS cleared", 34: "initial stack prepared", 35: "start_kernel entered",
    36: "calling setup_arch", 40: "calling cpu_probe", 41: "cpu_probe returned",
    42: "mips_cm_probe returned", 43: "prom_init calling plat_get_fdt",
    44: "plat_get_fdt returned", 45: "calling cpu_report", 46: "calling arch_mem_init",
    47: "arch_mem_init returned", 48: "calling cpu_cache_init", 49: "cpu_cache_init returned",
    50: "pagetable_init returned", 51: "setup_arch returned", 52: "calling trap_init",
    53: "mm_core_init returned", 54: "calling init_IRQ", 55: "init_IRQ returned",
    56: "calling time_init", 57: "time_init returned", 58: "calling console_init",
    59: "console_init returned", 192: "cold-entry shim reached",
    193: "stock bridge probe reached before original kernel entry",
    194: "loader filesystem probe pending with watchdog armed",
    195: "loader filesystem sandbox read verified",
    196: "loader filesystem sandbox probe returned an error",
    197: "pending loader probe skipped after retained-RAM reset",
    198: "runtime loader API signature mismatch; filesystem calls skipped",
    199: "unsupported loader critical-section context; filesystem calls skipped",
    200: "loader sandbox write, sync and read-back verified",
    202: "stock boot file restored and CRC-verified before Linux entry",
    203: "full stock-container sandbox copy and CRC read-back verified",
    206: "native stock fallback loading the backup",
    207: "native stock fallback failed; watchdog pending",
    208: "validated stock backup decrypted; entering native bootm",
    209: "native fallback bootm returned unexpectedly; watchdog pending",
    225: "destination CRC FAILED; watchdog recovery only",
}


def decode(raw):
    if len(raw) != SIZE:
        raise ValueError(f"trace length {len(raw)} != {SIZE}")
    words = struct.unpack_from("<16I", raw)
    if (words[0], words[2], words[3]) != (MAGIC, CAPACITY, VERSION):
        raise ValueError("invalid or overwritten trace header")
    count = words[1]
    if count > 16 * 1024 * 1024:
        raise ValueError("implausible log byte count")
    data = raw[HEADER:]
    text = data[:count] if count <= CAPACITY else data[count % CAPACITY:] + data[:count % CAPACITY]
    meta = {
        "stage": words[4], "stage_description": STAGES.get(words[4], "unknown"),
        "entry": hex(words[5]), "control": hex(words[6]), "trampoline": hex(words[7]),
        "watchdog_hz": words[8], "watchdog_seconds": words[9], "session_tag": hex(words[10]),
        "copy_pages": words[11], "log_bytes": count, "fw_arg0": hex(words[12]),
        "fw_arg1": hex(words[13]), "fdt": hex(words[14]), "destination_crc32": f"{words[15]:08x}",
    }
    return meta, text
