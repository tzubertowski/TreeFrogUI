"""Build against measured stock ABI without depending on another kernel build."""
import json
import hashlib
import os
import zlib
from pathlib import Path
import struct
import subprocess
import sys
from elftools.elf.elffile import ELFFile

root = Path(__file__).resolve().parents[2]
lab = root / "scripts/kernel_lab"
out = Path(os.environ.get("R36_KERNEL_OUT", root / "payload/kernel_lab"))
manifest = json.loads((out / "manifest.json").read_text())
watchdog_seconds = int(os.environ.get("R36_BOOT_TIMEOUT", "30"))
if not 5 <= watchdog_seconds <= 300:
    raise ValueError("R36_BOOT_TIMEOUT must be 5..300 seconds")
stock = root / "analysis/rootfs_card2/lib/modules/4.4.186-release/extra/dsc.ko"
with stock.open("rb") as f:
    elf = ELFFile(f)
    assert elf.get_section_by_name(".gnu.linkonce.this_module")["sh_size"] == 320
    reloc = elf.get_section_by_name(".rel.gnu.linkonce.this_module")
    assert [r["r_offset"] for r in reloc.iter_relocations()] == [208]

address = 0x8001BCEC
dump = (root / "analysis/kmem/kernel_80000000.bin").read_bytes()
signature = dump[address - 0x80000000:address - 0x80000000 + 16]
image = (out / "vmlinux.bin").read_bytes()
dtb = (out / "r36-lab.dtb").read_bytes()
rounded_memory = (manifest["memsz"] + 4095) & ~4095
staged = image + bytes(rounded_memory - len(image)) + dtb + bytes((-len(dtb)) % 4096)
staged_crc = zlib.crc32(staged)
defs = {"IMAGE_LOAD": manifest["load"], "IMAGE_ENTRY": manifest["entry"],
        "IMAGE_FILESZ": manifest["filesz"], "IMAGE_MEMSZ": manifest["memsz"],
        "DTB_LOAD": manifest["dtb"], "DTB_SIZE": (out / "r36-lab.dtb").stat().st_size,
        "DTB_PAGES": ((out / "r36-lab.dtb").stat().st_size + 4095) // 4096,
        "CACHE_FLUSH_ADDRESS": hex(address), "WATCHDOG_RATE": 187500,
        "WATCHDOG_SECONDS": watchdog_seconds, "STAGED_CRC32": hex(staged_crc)}
(out / "image_bounds.h").write_text("".join(f"#define {k} {v}u\n" for k, v in defs.items()) +
    "#define CACHE_FLUSH_BYTES {" + ",".join(hex(b) for b in signature) + "}\n")
(out / "module_abi.S").write_text('''
    .section .modinfo,"a"
    .asciz "license=GPL"
    .asciz "description=R36 RAM-only diagnostic kernel warm loader"
    .asciz "depends="
    .asciz "vermagic=4.4.186-release preempt MIPS32_R2 32BIT "
    .section .gnu.linkonce.this_module,"aw"
    .align 6
    .globl __this_module
    .type __this_module,@object
__this_module:
    .zero 12
    .asciz "r36boot"
    .zero 188
    .word init_module
    .zero 108
    .size __this_module, .-__this_module
''')
assert 12 + len(b"r36boot\0") + 188 == 208


def wslpath(p):
    return "/mnt/" + p.drive[0].lower() + str(p)[2:].replace("\\", "/")


def run(*args):
    if args[0] == "mipsel-linux-gnu-gcc":
        args = (args[0], "-wrapper", "/usr/bin/env", *args[1:])
    subprocess.run(["wsl", "-d", "ubmips", "--", *args], check=True)


cc = "mipsel-linux-gnu-gcc"
common = ["-mips32r2", "-EL", "-mabi=32", "-mno-abicalls", "-fno-pic", "-G0", "-msoft-float", "-mlong-calls"]
run(cc, *common, "-Os", "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
    "-Wall", "-Wextra", "-Werror", "-I" + wslpath(out), "-c", wslpath(lab / "r36boot.c"), "-o", wslpath(out / "r36boot.o"))
for src, target in [(lab / "r36boot-reloc.S", "reloc.o"), (out / "module_abi.S", "abi.o")]:
    run(cc, *common, "-c", wslpath(src), "-o", wslpath(out / target))
run("mipsel-linux-gnu-ld", "-r", "-EL", "-o", wslpath(out / "r36boot.ko"),
    *(wslpath(out / name) for name in ["r36boot.o", "reloc.o", "abi.o"]))
run(cc, "-static", "-Os", "-Wall", "-Wextra", "-Werror", "-I" + wslpath(out),
    wslpath(lab / "r36bootctl.c"), "-o", wslpath(out / "r36bootctl"))
run(cc, "-static", "-Os", "-Wall", "-Wextra", "-Werror", wslpath(lab / "wdt_diag.c"),
    "-o", wslpath(out / "r36-wdt-diag"))
run("mipsel-linux-gnu-readelf", "-p", ".modinfo", wslpath(out / "r36boot.ko"))
run("mipsel-linux-gnu-nm", "-u", wslpath(out / "r36boot.ko"))
manifest["loader_sha256"] = {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                             for name in ["r36boot.ko", "r36bootctl", "r36-wdt-diag"]}
manifest["diagnostic_watchdog"] = {"rate_hz": 187500, "timeout_seconds": watchdog_seconds,
                                    "armed_by_loader_before_handoff": True}
manifest["relocation_crc32"] = f"{staged_crc:08x}"
manifest["loader_binding"] = {"image_sha256": manifest["sha256"]["vmlinux.bin"],
                               "dtb_sha256": manifest["sha256"]["r36-lab.dtb"],
                               "source_abi": "stock-4.4.186-release-23",
                               "trace_version": 2}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("Built loader for", manifest["entry"], "with measured 320-byte stock module descriptor")
