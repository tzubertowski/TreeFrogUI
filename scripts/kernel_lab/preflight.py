"""Validate a frozen candidate completely offline, before any device connection."""
import argparse
import hashlib
import json
import gzip
import os
from pathlib import Path
import struct
import zlib

from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

from trace_format import PHYSICAL, SIZE

ROOT = Path(os.environ.get("R36_PROJECT_ROOT", Path(__file__).resolve().parents[2]))
REQUIRED = ["vmlinux.elf", "vmlinux.bin", "r36-lab.dtb", "kernel.config", "System.map",
            "r36boot.ko", "r36bootctl", "r36-wdt-diag", "r36hello.ko", "init.elf", "initramfs.cpio.gz"]


def cpio_files(raw):
    pos, result = 0, {}
    while pos + 110 <= len(raw):
        header = raw[pos:pos + 110]
        if header[:6] not in (b"070701", b"070702"):
            raise ValueError("invalid initramfs cpio header")
        numbers = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        size, namesize = numbers[6], numbers[11]
        pos += 110
        if namesize < 1 or pos + namesize > len(raw):
            raise ValueError("invalid cpio name length")
        name = raw[pos:pos + namesize - 1].decode("ascii")
        pos = (pos + namesize + 3) & ~3
        if name == "TRAILER!!!":
            return result
        if pos + size > len(raw):
            raise ValueError("truncated cpio data")
        result[name.lstrip("./")] = raw[pos:pos + size]
        pos = (pos + size + 3) & ~3
    raise ValueError("cpio trailer missing")


def check_elf(path, kind):
    with path.open("rb") as handle:
        elf = ELFFile(handle)
        if elf.elfclass != 32 or not elf.little_endian or elf["e_machine"] != "EM_MIPS" or elf["e_type"] != kind:
            raise ValueError(f"wrong ELF architecture/type: {path.name}")
        if kind == "ET_EXEC" and path.name != "vmlinux.elf":
            if any(s["p_type"] == "PT_INTERP" for s in elf.iter_segments()):
                raise ValueError(f"helper is dynamically linked: {path.name}")


def properties(data):
    magic, total, pos, strings = struct.unpack_from(">4I", data)
    if magic != 0xD00DFEED or total != len(data):
        raise ValueError("invalid DTB header/size")
    stack, result = [], {}
    while pos + 4 <= total:
        token = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        if token == 1:
            end = data.index(b"\0", pos, total)
            stack.append(data[pos:end].decode())
            result.setdefault("/" + "/".join(stack[1:]), {})
            pos = (end + 4) & ~3
        elif token == 2:
            stack.pop()
        elif token == 3:
            size, offset = struct.unpack_from(">2I", data, pos)
            pos += 8
            begin = strings + offset
            if pos + size > total or begin >= total:
                raise ValueError("DTB property out of bounds")
            end = data.index(b"\0", begin, total)
            result["/" + "/".join(stack[1:])][data[begin:end].decode()] = data[pos:pos + size]
            pos = (pos + size + 3) & ~3
        elif token == 4:
            continue
        elif token == 9:
            return result
        else:
            raise ValueError(f"bad DTB token {token}")
    raise ValueError("DTB lacks end token")


def validate(out, *, require_emulation=True):
    out = Path(out)
    manifest = json.loads((out / "manifest.json").read_text())
    groups = {**manifest["sha256"], **manifest["loader_sha256"]}
    for name in REQUIRED:
        if name not in groups:
            raise ValueError(f"required artifact has no digest: {name}")
    for name, expected in groups.items():
        if Path(name).name != name:
            raise ValueError("artifact path escapes candidate")
        if hashlib.sha256((out / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"artifact hash mismatch: {name}")
    image, dtb = (out / "vmlinux.bin").read_bytes(), (out / "r36-lab.dtb").read_bytes()
    for name in ["vmlinux.elf", "r36bootctl", "r36-wdt-diag", "init.elf"]:
        check_elf(out / name, "ET_EXEC")
    for name in ["r36boot.ko", "r36hello.ko"]:
        check_elf(out / name, "ET_REL")
    load, entry, tree = (int(manifest[k], 0) for k in ("load", "entry", "dtb"))
    memory = (manifest["memsz"] + 4095) & -4096
    if len(image) != manifest["filesz"] or not load <= entry < load + len(image):
        raise ValueError("image length/entry mismatch")
    if not (load & 0xFFF) == 0 or load + memory > 0x80000000 + PHYSICAL or tree != 0x82E00000:
        raise ValueError("unsafe load range")
    staged = image + bytes(memory - len(image)) + dtb + bytes((-len(dtb)) % 4096)
    crc = zlib.crc32(staged)
    if manifest["relocation_crc32"] != f"{crc:08x}":
        raise ValueError("staged CRC mismatch")
    wd = manifest["diagnostic_watchdog"]
    if wd["rate_hz"] != 187500 or not 5 <= wd["timeout_seconds"] <= 120 or not wd["armed_by_loader_before_handoff"]:
        raise ValueError("diagnostic watchdog missing/out of bounds")
    with (out / "vmlinux.elf").open("rb") as handle:
        elf = ELFFile(handle)
        loads = [s for s in elf.iter_segments() if s["p_type"] == "PT_LOAD"]
        if len(loads) != 1:
            raise ValueError("expected one load segment")
        segment = loads[0]
        if (segment["p_vaddr"], elf["e_entry"], segment["p_memsz"], segment.data()) != (load, entry, manifest["memsz"], image):
            raise ValueError("raw image differs from ELF")
    with (out / "r36boot.ko").open("rb") as handle:
        elf = ELFFile(handle)
        binary_binding = elf.get_section_by_name(".r36.binding").data()
        values = struct.unpack_from("<16I", binary_binding)
        expected = (0x52333642, 1, load, entry, len(image), manifest["memsz"], tree, len(dtb), crc,
                    187500, wd["timeout_seconds"], PHYSICAL, SIZE, 0x8001BCEC, 320, 108)
        if len(binary_binding) != 80 or values != expected:
            raise ValueError("compiled loader is bound to another image/DTB/ABI")
        stock = (ROOT / "analysis/kmem/kernel_80000000.bin").read_bytes()
        if binary_binding[64:] != stock[0x1BCEC:0x1BCFC]:
            raise ValueError("stock cache-flush fingerprint differs")
        descriptor = elf.get_section_by_name(".gnu.linkonce.this_module")
        if descriptor["sh_size"] != 320 or descriptor.data()[12:20] != b"r36boot\0":
            raise ValueError("wrong stock module descriptor")
        symtab = elf.get_section_by_name(".symtab")
        for section in elf.iter_sections():
            if isinstance(section, RelocationSection):
                for relocation in section.iter_relocations():
                    symbol = symtab.get_symbol(relocation["r_info_sym"])
                    if relocation["r_info_type"] == 4 and symbol["st_shndx"] == "SHN_UNDEF":
                        raise ValueError("external R_MIPS_26 call requires -mlong-calls")
        imports = {s.name for s in symtab.iter_symbols() if s.name and s["st_shndx"] == "SHN_UNDEF"}
        kallsyms = (ROOT / "analysis/card2_files/kdump/proc_kallsyms.txt").read_text()
        exports = {line.split()[-1][len("__ksymtab_"):] for line in kallsyms.splitlines()
                   if line.split()[-1].startswith("__ksymtab_")}
        if imports - exports:
            raise ValueError(f"unexported imports: {sorted(imports - exports)}")
    config = (out / "kernel.config").read_text()
    for option in ["CPU_LITTLE_ENDIAN", "CEVT_R4K", "CSRC_R4K", "MODULES", "MODULE_UNLOAD", "DEVTMPFS", "MMC_BLOCK", "VFAT_FS"]:
        if f"CONFIG_{option}=y\n" not in config:
            raise ValueError(f"required config disabled: {option}")
    nodes = properties(dtb)
    if nodes["/memory@0"]["reg"] != struct.pack(">II", 0, 0x02F91E50):
        raise ValueError("wrong Linux RAM partition")
    if not any(p.get("reg") == struct.pack(">II", PHYSICAL, SIZE) and
               p.get("compatible") == b"r36lab,ramconsole\0" for p in nodes.values()):
        raise ValueError("retained trace region absent")
    cmdline = nodes["/chosen"]["bootargs"].decode().rstrip("\0")
    if "rdinit=/init" not in cmdline or "clk_ignore_unused" not in cmdline:
        raise ValueError("unsafe/missing diagnostic command line")
    if manifest["profile"] in ("boot", "driver"):
        if "CONFIG_USB_GADGET=y\n" in config or "ttyS" in cmdline or "earlycon" in cmdline:
            raise ValueError("minimal acceptance profile unexpectedly touches USB/UART")
        with (out / "init.elf").open("rb") as handle:
            mode = ELFFile(handle).get_section_by_name(".r36.init").data().rstrip(b"\0")
            if mode.decode() != "R36_MINIMAL_INIT_V1:" + manifest["profile"]:
                raise ValueError("PID1 mode does not match candidate profile")
    compressed = (out / "initramfs.cpio.gz").read_bytes()
    if compressed not in image or cpio_files(gzip.decompress(compressed)).get("init") != (out / "init.elf").read_bytes():
        raise ValueError("embedded initramfs differs from the verified PID1 executable")
    release = manifest.get("release", "")
    if not release or ("Linux version " + release + " ").encode() not in image or manifest["build_version"].encode() not in image:
        raise ValueError("kernel version metadata does not match image")
    with (out / "r36hello.ko").open("rb") as handle:
        info = ELFFile(handle).get_section_by_name(".modinfo").data()
        if ("vermagic=" + release + " ").encode() not in info:
            raise ValueError("test module belongs to another kernel")
    if require_emulation:
        emulation = json.loads((out / "emulation.json").read_text())
        cases = emulation.get("cases", [])
        if not emulation.get("passed") or emulation.get("loader_sha256") != groups["r36boot.ko"] or len(cases) != 3 or any(c["image_sha256"] != groups["vmlinux.bin"] or not c["passed"] for c in cases):
            raise ValueError("full matching emulation report required")
    return {"passed": True, "profile": manifest["profile"], "release": release,
            "image_sha256": groups["vmlinux.bin"], "crc32": f"{crc:08x}",
            "watchdog_seconds": wd["timeout_seconds"], "hardware_boot_verified": manifest.get("hardware_boot_verified", False),
            "scope": "offline consistency/ABI/layout checks; physical drivers remain hardware acceptance"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--without-emulation", action="store_true")
    args = parser.parse_args()
    report = validate(args.out, require_emulation=not args.without_emulation)
    (args.out / "preflight.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
