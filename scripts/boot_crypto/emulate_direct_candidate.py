"""Cold-entry verification with no stock Linux bytes in emulated RAM."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct

from elftools.elf.elffile import ELFFile
import unicorn as un
from unicorn import mips_const as mr

from codec import decrypt, parse_uimage, recover_key

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "payload/kernel_direct_candidate")
    args = parser.parse_args()
    manifest = json.loads((args.out / "manifest.json").read_text())
    encrypted = (args.out / "vmlinux.uImage.encrypted.NOT_DEPLOYED").read_bytes()
    assert hashlib.sha256(encrypted).hexdigest() == manifest["image_sha256"]
    key = recover_key((ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes())
    image = decrypt(encrypted, key)
    header = parse_uimage(image)
    raw = gzip.decompress(image[64:])
    assert raw == (args.out / "cold_payload.raw").read_bytes()
    source = ROOT / "payload/kernel_ready/boot"
    with (source / "vmlinux.elf").open("rb") as handle:
        elf = ELFFile(handle)
        symbols = {s.name: int(s["st_value"]) & 0xFFFFFFFF
                   for s in elf.get_section_by_name(".symtab").iter_symbols() if s.name}
    cpu = un.Uc(un.UC_ARCH_MIPS, un.UC_MODE_MIPS32 | un.UC_MODE_LITTLE_ENDIAN)
    cpu.ctl_set_cpu_model(mr.UC_CPU_MIPS32_74KF)
    cpu.mem_map(0, 64 * 1024 * 1024)
    cpu.mem_map(0x18800000, 4096)
    cpu.mem_map(0x18818000, 4096)
    cpu.mem_write(int(header["load"], 0) & 0x1FFFFFFF, raw)
    cpu.mem_write(0x18800060, struct.pack("<I", 0x0E400F8C))  # watchdog initially gated
    cpu.reg_write(mr.UC_MIPS_REG_CP0_STATUS, 0x10000001)
    reached = []
    entry = int(manifest["kernel_entry"], 0)
    dtb = int(manifest["dtb_address"], 0)

    def kernel_entry(uc, address, size, user):
        assert uc.reg_read(mr.UC_MIPS_REG_A0) == 0xFFFFFFFE
        assert uc.reg_read(mr.UC_MIPS_REG_A1) == dtb
        assert uc.reg_read(mr.UC_MIPS_REG_A2) == uc.reg_read(mr.UC_MIPS_REG_A3) == 0
        assert not uc.reg_read(mr.UC_MIPS_REG_CP0_STATUS) & 1
        reached.append("kernel_entry")

    def start_kernel(uc, address, size, user):
        assert struct.unpack("<I", uc.mem_read(symbols["fw_arg1"] & 0x1FFFFFFF, 4))[0] == dtb
        reached.append("start_kernel")
        uc.emu_stop()

    cpu.hook_add(un.UC_HOOK_CODE, kernel_entry, begin=entry, end=entry)
    cpu.hook_add(un.UC_HOOK_CODE, start_kernel, begin=symbols["start_kernel"], end=symbols["start_kernel"])
    cpu.emu_start(int(header["entry"], 0), 0, count=10_000_000)
    assert reached == ["kernel_entry", "start_kernel"]
    assert struct.unpack("<I", cpu.mem_read(0x18800060, 4))[0] == 0x0E000F8C
    counter, control = struct.unpack("<II", cpu.mem_read(0x18818500, 8))
    assert counter == (-187500 * 30) & 0xFFFFFFFF and control == 0x26
    source_dtb = (args.out / "inline.dtb").read_bytes() if (args.out / "inline.dtb").exists() else (source / "r36-lab.dtb").read_bytes()
    assert bytes(cpu.mem_read(dtb & 0x1FFFFFFF, len(source_dtb))) == source_dtb
    result = {"passed": True, "reached": reached, "stock_kernel_loaded_in_emulator": False,
              "inline_dtb_verified": True, "watchdog_registers_verified": True,
              "image_sha256": manifest["image_sha256"],
              "scope": "cold shim + real kernel head, not NOR/SoC boot emulation",
              "hardware_cold_boot_verified": False}
    (args.out / "cold_emulation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
