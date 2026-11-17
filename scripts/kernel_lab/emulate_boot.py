"""Execute the actual relocation machine code and MIPS kernel head offline."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import struct
import zlib

from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
import unicorn as un
from unicorn import mips_const as mr

PAGE = 4096
TRACE = 0x02F91000


def symbols(elf):
    return {s.name: s for s in elf.get_section_by_name(".symtab").iter_symbols() if s.name}


def replay(out, *, scattered=False, corrupt=False):
    manifest = json.loads((out / "manifest.json").read_text())
    load, entry, dtb_address = (int(manifest[k], 0) for k in ("load", "entry", "dtb"))
    image = (out / "vmlinux.bin").read_bytes()
    dtb = (out / "r36-lab.dtb").read_bytes()
    memory_size = (manifest["memsz"] + PAGE - 1) & -PAGE
    payload = image + bytes(memory_size - len(image))
    tree = dtb + bytes((-len(dtb)) % PAGE)
    expected_crc = zlib.crc32(payload + tree)
    assert manifest["relocation_crc32"] == f"{expected_crc:08x}"
    with (out / "r36boot.ko").open("rb") as handle:
        elf = ELFFile(handle)
        syms = symbols(elf)
        first, last = (int(syms[n]["st_value"]) for n in ("r36_reloc_start", "r36_reloc_end"))
        section_index = syms["r36_reloc_start"]["st_shndx"]
        stub = elf.get_section(section_index).data()[first:last]
        failure_offset = syms["r36_crc_failed"]["st_value"] - first
        for section in elf.iter_sections():
            if isinstance(section, RelocationSection) and section["sh_info"] == section_index:
                assert not any(first <= r["r_offset"] < last for r in section.iter_relocations()), \
                    "copied stub contains unresolved relocations"
    assert 0 < len(stub) <= PAGE - 16
    with (out / "vmlinux.elf").open("rb") as handle:
        elf = ELFFile(handle)
        syms = symbols(elf)
        start_kernel = int(syms["start_kernel"]["st_value"]) & 0xFFFFFFFF
        fw0 = int(syms["fw_arg0"]["st_value"]) & 0x1FFFFFFF
        fw1 = int(syms["fw_arg1"]["st_value"]) & 0x1FFFFFFF
        stack_base = int(syms["init_thread_union"]["st_value"]) & 0xFFFFFFFF

    cpu = un.Uc(un.UC_ARCH_MIPS, un.UC_MODE_MIPS32 | un.UC_MODE_LITTLE_ENDIAN)
    cpu.ctl_set_cpu_model(mr.UC_CPU_MIPS32_74KF)
    cpu.mem_map(0, 64 * 1024 * 1024)
    cpu.reg_write(mr.UC_MIPS_REG_CP0_STATUS, 0x10000000)
    control, trampoline, first_list = 0x02800000, 0x02801000, 0x02802000
    pieces = [payload[i:i + PAGE] for i in range(0, len(payload), PAGE)]
    pieces += [tree[i:i + PAGE] for i in range(0, len(tree), PAGE)]
    destinations = list(range(load & 0x1FFFFFFF, (load & 0x1FFFFFFF) + len(payload), PAGE))
    destinations += list(range(dtb_address & 0x1FFFFFFF,
                               (dtb_address & 0x1FFFFFFF) + len(tree), PAGE))
    candidates = list(range(0x01000000, 0x02600000, PAGE))
    sources = random.Random(36).sample(candidates, len(pieces)) if scattered else candidates[:len(pieces)]
    for address, piece in zip(sources, pieces):
        cpu.mem_write(address, piece)
    if corrupt:
        cpu.mem_write(sources[7] + 19, bytes([pieces[7][19] ^ 1]))
    pairs = list(zip(sources, destinations))
    lists = (len(pairs) + 510) // 511
    for index in range(lists):
        subset = pairs[index * 511:(index + 1) * 511]
        next_list = 0xA0000000 + first_list + (index + 1) * PAGE if index + 1 < lists else 0
        encoded = struct.pack("<II", next_list, len(subset))
        encoded += b"".join(struct.pack("<II", source | 0xA0000000, dest | 0xA0000000)
                            for source, dest in subset)
        cpu.mem_write(first_list + index * PAGE, encoded)
    table = []
    for index in range(256):
        value = index
        for _ in range(8):
            value = (value >> 1) ^ (0xEDB88320 if value & 1 else 0)
        table.append(value)
    cpu.mem_write(control, struct.pack("<4I256I", first_list | 0xA0000000, entry,
                                      dtb_address, expected_crc, *table))
    cpu.mem_write(trampoline, stub)
    cpu.reg_write(mr.UC_MIPS_REG_A0, control | 0xA0000000)
    reached = {"kernel_entry": False, "start_kernel": False, "crc_failure": False}
    violations = []

    def writes(uc, access, address, size, value, user):
        physical = address & 0x1FFFFFFF
        allowed = ((load & 0x1FFFFFFF) <= physical and physical + size <= (load & 0x1FFFFFFF) + len(payload))
        allowed |= ((dtb_address & 0x1FFFFFFF) <= physical and physical + size <= (dtb_address & 0x1FFFFFFF) + len(tree))
        allowed |= TRACE <= physical and physical + size <= TRACE + 3584
        if not allowed:
            violations.append((hex(address), size))
            uc.emu_stop()

    def at_entry(uc, address, size, user):
        reached["kernel_entry"] = True
        assert not corrupt, "corrupted image was executed"
        assert uc.reg_read(mr.UC_MIPS_REG_A0) == 0xFFFFFFFE
        assert uc.reg_read(mr.UC_MIPS_REG_A1) == dtb_address
        assert uc.reg_read(mr.UC_MIPS_REG_A2) == uc.reg_read(mr.UC_MIPS_REG_A3) == 0
        assert bytes(uc.mem_read(load & 0x1FFFFFFF, len(payload))) == payload
        assert bytes(uc.mem_read(dtb_address & 0x1FFFFFFF, len(tree))) == tree

    def at_start(uc, address, size, user):
        reached["start_kernel"] = True
        assert struct.unpack("<I", uc.mem_read(fw0, 4))[0] == 0xFFFFFFFE
        assert struct.unpack("<I", uc.mem_read(fw1, 4))[0] == dtb_address
        assert uc.reg_read(mr.UC_MIPS_REG_GP) == stack_base
        assert load <= uc.reg_read(mr.UC_MIPS_REG_SP) < load + memory_size
        uc.emu_stop()

    def at_failure(uc, address, size, user):
        # Stop after the failure marker's store/sync, before its infinite loop.
        reached["crc_failure"] = True
        uc.emu_stop()

    cpu.hook_add(un.UC_HOOK_MEM_WRITE, writes)
    cpu.hook_add(un.UC_HOOK_CODE, at_entry, begin=entry, end=entry)
    cpu.hook_add(un.UC_HOOK_CODE, at_start, begin=start_kernel, end=start_kernel)
    failure_pc = 0xA0000000 + trampoline + failure_offset + 12
    cpu.hook_add(un.UC_HOOK_CODE, at_failure, begin=failure_pc, end=failure_pc)
    cpu.emu_start(trampoline | 0xA0000000, 0, count=200_000_000)
    actual_crc = struct.unpack("<I", cpu.mem_read(TRACE + 60, 4))[0]
    stage = struct.unpack("<I", cpu.mem_read(TRACE + 16, 4))[0]
    assert not violations, violations
    if corrupt:
        assert reached["crc_failure"] and not reached["kernel_entry"] and stage == 225
        assert actual_crc != expected_crc
    else:
        assert reached["kernel_entry"] and reached["start_kernel"]
        assert actual_crc == expected_crc
    return {"scattered_pages": scattered, "corrupted_source": corrupt, "passed": True,
            "stage": stage, "expected_crc32": f"{expected_crc:08x}",
            "actual_crc32": f"{actual_crc:08x}", "pages": len(pairs), "reached": reached,
            "stub_bytes": len(stub), "image_sha256": hashlib.sha256(image).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    cases = [(False, False)] if args.quick else [(False, False), (True, False), (True, True)]
    results = []
    for scattered, corrupt in cases:
        result = replay(args.out, scattered=scattered, corrupt=corrupt)
        results.append(result)
        print(json.dumps(result), flush=True)
    report = {"passed": True, "cases": results,
              "loader_sha256": hashlib.sha256((args.out / "r36boot.ko").read_bytes()).hexdigest(),
              "scope": "actual relocation bytes and kernel head, not SoC MMIO/DMA/cache emulation"}
    (args.out / "emulation.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
