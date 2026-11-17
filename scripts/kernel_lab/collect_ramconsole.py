"""Read the diagnostic RAM ring after returning to stock, if DDR retained it."""
from pathlib import Path
import json
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "release/upstream-TreeFrogUI/apps/usb_mode/pc"))
import r36

device = r36.R36()
try:
    code, raw = device.run("/mnt/sdcard/cubegm/mdump 2f91000 3584")
finally:
    device.close()
out = ROOT / "analysis/driver_port"
(out / "postboot_ramconsole.bin").write_bytes(raw)
if code or len(raw) != 3584:
    raise SystemExit(f"short RAM capture: rc={code}, bytes={len(raw)}")
magic, count, capacity, version = struct.unpack_from("<4I", raw)
if magic != 0x5233364C or capacity != 3520 or version != 2 or count > 16 * 1024 * 1024:
    raise SystemExit("No valid R36 RAM console header; DDR was reset or reused")
words = struct.unpack_from("<16I", raw)
stages = {1: "loader armed watchdog", 2: "uncached relocation entered",
          3: "copy completed; jumping to kernel", 4: "kernel_entry reached",
          5: "kernel RAM console initialized", 6: "PID1 userspace reached",
          16: "stock watchdog reset trial"}
stages.update({33: "BSS cleared", 34: "initial stack prepared", 35: "start_kernel entered",
               36: "calling setup_arch", 40: "calling cpu_probe", 41: "cpu_probe returned",
               42: "mips_cm_probe returned", 43: "prom_init calling plat_get_fdt",
               44: "plat_get_fdt returned", 45: "calling cpu_report",
               46: "calling arch_mem_init", 47: "arch_mem_init returned",
               48: "calling cpu_cache_init", 49: "cpu_cache_init returned",
               50: "pagetable_init returned", 51: "setup_arch returned",
               52: "calling trap_init", 53: "mm_core_init returned",
               54: "calling init_IRQ", 55: "init_IRQ returned",
               56: "calling time_init", 57: "time_init returned",
               58: "calling console_init", 59: "console_init returned"})
metadata = {"stage": words[4], "stage_description": stages.get(words[4], "unknown"),
            "entry": hex(words[5]), "control": hex(words[6]), "trampoline": hex(words[7]),
            "watchdog_hz": words[8], "watchdog_seconds": words[9],
            "session_tag": hex(words[10]), "copy_pages": words[11], "log_bytes": count,
            "fw_arg0": hex(words[12]), "fw_arg1": hex(words[13]), "fdt": hex(words[14])}
(out / "postboot_ramconsole.json").write_text(json.dumps(metadata, indent=2) + "\n")
print(json.dumps(metadata, indent=2))
data = raw[64:]
if count <= capacity:
    text = data[:count]
else:
    index = count % capacity
    text = data[index:] + data[:index]
(out / "postboot_ramconsole.txt").write_bytes(text)
history = out / "runs" / metadata["session_tag"]
history.mkdir(parents=True, exist_ok=True)
(history / "trace.bin").write_bytes(raw)
(history / "trace.json").write_text(json.dumps(metadata, indent=2) + "\n")
(history / "kernel.log").write_bytes(text)
print(text.decode("utf-8", "replace"))
