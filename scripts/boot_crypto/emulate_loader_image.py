"""Exercise original bootm image/header validation, not the SoC or SD hardware."""
import argparse
import hashlib
import gzip
import json
from pathlib import Path
import struct

import unicorn as un
from unicorn import mips_const as mr

from codec import decrypt, recover_key, unpack_loader

ROOT = Path(__file__).resolve().parents[2]
IMAGES = 0x89E81C68
INPUT = 0x81000000
STACK = 0x81C00000
RETURN = 0x83F00000


def validate(loader, image, inflate=False):
    cpu = un.Uc(un.UC_ARCH_MIPS, un.UC_MODE_MIPS32 | un.UC_MODE_LITTLE_ENDIAN)
    cpu.ctl_set_cpu_model(mr.UC_CPU_MIPS32_74KF)
    cpu.mem_map(0, 64 * 1024 * 1024)
    cpu.mem_map(0x09D00000, 0x300000)
    cpu.mem_write(0x09DA0000, loader)
    cpu.mem_write(INPUT & 0x1FFFFFFF, image)
    cpu.mem_write(0x09E665D4, struct.pack("<I", INPUT))
    cpu.mem_write((STACK & 0x1FFFFFFF) + 16, struct.pack("<II", 3, IMAGES))
    def invalid_memory(uc, access, address, size, value, user):
        raise RuntimeError(f"unmapped access: pc={uc.reg_read(mr.UC_MIPS_REG_PC):08x}, address={address:08x}, size={size}")

    cpu.hook_add(un.UC_HOOK_MEM_INVALID, invalid_memory)
    for reg, value in [(mr.UC_MIPS_REG_SP, STACK), (mr.UC_MIPS_REG_RA, RETURN),
                       (mr.UC_MIPS_REG_GP, 0x89E6E1A0),
                       (mr.UC_MIPS_REG_CP0_STATUS, 0x10000000)]:
        cpu.reg_write(reg, value)
    messages = []

    def print_stub(uc, address, size, user):
        ptr = uc.reg_read(mr.UC_MIPS_REG_A0) & 0x1FFFFFFF
        messages.append(bytes(uc.mem_read(ptr, 256)).split(b"\0", 1)[0].decode("ascii", "replace"))
        uc.reg_write(mr.UC_MIPS_REG_V0, 0)
        uc.reg_write(mr.UC_MIPS_REG_PC, uc.reg_read(mr.UC_MIPS_REG_RA))

    def skip_display(uc, address, size, user):
        uc.reg_write(mr.UC_MIPS_REG_PC, uc.reg_read(mr.UC_MIPS_REG_RA))

    for address in (0x89DAF204, 0x89DAF304):
        cpu.hook_add(un.UC_HOOK_CODE, print_stub, begin=address, end=address)
    cpu.hook_add(un.UC_HOOK_CODE, skip_display, begin=0x89DAD6BC, end=0x89DAD6BC)
    cpu.emu_start(0x89DACDFC, RETURN, timeout=30_000_000, count=150_000_000)
    if cpu.reg_read(mr.UC_MIPS_REG_PC) != RETURN:
        raise RuntimeError(f"validation did not return: pc={cpu.reg_read(mr.UC_MIPS_REG_PC):08x}")
    state = bytes(cpu.mem_read(IMAGES & 0x1FFFFFFF, 0x8C))
    word = lambda offset: struct.unpack_from("<I", state, offset)[0]
    result = {"return_code": cpu.reg_read(mr.UC_MIPS_REG_V0), "messages": messages,
            "load": hex(word(0x58)), "entry": hex(word(0x60)),
            "compression": state[0x5C], "type": state[0x5D], "os": state[0x5E],
            "data_bytes": word(0x54)}
    if inflate and result["return_code"] == 0:
        heap = 0x82200000

        def calloc_stub(uc, address, size, user):
            nonlocal heap
            count = uc.reg_read(mr.UC_MIPS_REG_A0)
            item_size = uc.reg_read(mr.UC_MIPS_REG_A1)
            length = count if address == 0x89DDBF10 else count * item_size
            assert 0 < length < 0x100000 and heap + length < 0x82300000
            pointer = heap
            heap = (heap + length + 31) & ~31
            uc.mem_write(pointer & 0x1FFFFFFF, bytes(length))
            uc.reg_write(mr.UC_MIPS_REG_V0, pointer)
            uc.reg_write(mr.UC_MIPS_REG_PC, uc.reg_read(mr.UC_MIPS_REG_RA))

        cpu.hook_add(un.UC_HOOK_CODE, calloc_stub, begin=0x89DDC040, end=0x89DDC040)
        cpu.hook_add(un.UC_HOOK_CODE, calloc_stub, begin=0x89DDBF10, end=0x89DDBF10)
        cpu.hook_add(un.UC_HOOK_CODE, skip_display, begin=0x89DDB78C, end=0x89DDB78C)
        length_pointer = 0x81D00000
        cpu.mem_write(length_pointer & 0x1FFFFFFF, struct.pack("<I", len(image) - 64))
        for reg, value in [(mr.UC_MIPS_REG_SP, STACK), (mr.UC_MIPS_REG_RA, RETURN),
                           (mr.UC_MIPS_REG_A0, int(result["load"], 0)),
                           (mr.UC_MIPS_REG_A1, 64 * 1024 * 1024),
                           (mr.UC_MIPS_REG_A2, INPUT + 64), (mr.UC_MIPS_REG_A3, length_pointer)]:
            cpu.reg_write(reg, value)
        try:
            cpu.emu_start(0x89DDAAF8, RETURN, timeout=30_000_000, count=250_000_000)
        except un.UcError as error:
            raise RuntimeError(f"native gzip stopped at pc={cpu.reg_read(mr.UC_MIPS_REG_PC):08x}, ra={cpu.reg_read(mr.UC_MIPS_REG_RA):08x}, sp={cpu.reg_read(mr.UC_MIPS_REG_SP):08x}") from error
        assert cpu.reg_read(mr.UC_MIPS_REG_PC) == RETURN
        assert cpu.reg_read(mr.UC_MIPS_REG_V0) == 0, messages
        length = struct.unpack("<I", cpu.mem_read(length_pointer & 0x1FFFFFFF, 4))[0]
        raw = bytes(cpu.mem_read(int(result["load"], 0) & 0x1FFFFFFF, length))
        assert raw == gzip.decompress(image[64:])
        result["native_gzip"] = {"passed": True, "bytes": length,
                                 "sha256": hashlib.sha256(raw).hexdigest(),
                                 "stubs": ["malloc/calloc with zeroed emulated heap", "free", "printf/puts"]}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=ROOT / "payload/kernel_direct_advapi_oneshot/vmlinux.uImage.plain")
    parser.add_argument("--report", type=Path, default=ROOT / "analysis/boot_crypto/loader_image_emulation.json")
    args = parser.parse_args()
    if not args.report.parent.is_dir():
        parser.error("report parent must already exist")
    loader_source = (ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes()
    loader = unpack_loader(loader_source)
    key = recover_key(loader_source)
    stock = decrypt((ROOT / "analysis/boot_crypto/original_advapi32.dll").read_bytes(), key)
    candidate = args.candidate.read_bytes()
    bad_header = bytearray(candidate)
    bad_header[20] ^= 1
    bad_payload = bytearray(candidate)
    bad_payload[-1] ^= 1
    rows = []
    for name, image, accepted in [("stock", stock, True), ("candidate", candidate, True),
                                   ("corrupt_header", bad_header, False),
                                   ("corrupt_payload", bad_payload, False)]:
        result = validate(loader, bytes(image), inflate=accepted)
        result.update(name=name, expected_accepted=accepted, sha256=hashlib.sha256(image).hexdigest())
        print(json.dumps(result, indent=2), flush=True)
        assert (result["return_code"] == 0) == accepted, result
        if accepted:
            assert int(result["load"], 0) == struct.unpack_from(">I", image, 16)[0]
            assert int(result["entry"], 0) == struct.unpack_from(">I", image, 20)[0]
        rows.append(result)
    record = {"passed": True, "function": "0x89dacdfc", "states": "START | FINDOS",
              "candidate": str(args.candidate),
              "original_crc_machine_code_executed": True,
              "stubs": ["printf/puts", "image metadata display"],
              "scope": "decrypted uImage validation, load/entry extraction and original gzip machine code; no SD I/O or hardware boot",
              "rows": rows}
    args.report.write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
