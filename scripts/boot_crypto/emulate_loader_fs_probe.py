"""Verify probe control flow with native loader IRQ helpers and stubbed file APIs."""
import argparse
import gzip
import json
from pathlib import Path
import struct
import zlib
from elftools.elf.elffile import ELFFile

import unicorn as un
from unicorn import mips_const as mr

from codec import decrypt, recover_key, unpack_loader
from loader_fs_probe import CLOSE, OPEN, READ, RESOLVE, TRACE, WRITE, GET_FILE_POINTER, FAT_SYNC, make_probe, RESTORE_RECEIPT, RESTORE_MAGIC
from loader_fallback import DECRYPT, BOOTM, terminal_stub

ROOT = Path(__file__).resolve().parents[2]
MASKS = {0x89E7B864: 0x12345678, 0x89E7B868: 0x20304050, 0x89E7B86C: 4,
         0x89E7B854: 0x10101010, 0x89E7B858: 0x20202020,
         0x89E7B85C: 0x30303030, 0x89E7B860: 0x40404040}
TCB = 0x82500000


def execute(folder, case, full_copy=False, native_decrypt=False):
    manifest = json.loads((folder / "manifest.json").read_text())
    source = (ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes()
    image = decrypt((folder / "advapi32.dll.encrypted.NOT_DEPLOYED").read_bytes(), recover_key(source))
    raw = gzip.decompress(image[64:])
    content = (folder / "R36PROBE.BIN").read_bytes()
    source_data = (ROOT / "analysis/boot_crypto/original_advapi32.dll").read_bytes()
    copy_spec = manifest.get("copy_spec")
    fallback_spec = manifest.get("stock_fallback")
    handoff = manifest.get("kernel_handoff")
    if copy_spec:
        if not full_copy and not handoff:
            source_data = source_data[:65537]
        copy_spec = dict(copy_spec, bytes=len(source_data), crc32=zlib.crc32(source_data))
    cpu = un.Uc(un.UC_ARCH_MIPS, un.UC_MODE_MIPS32 | un.UC_MODE_LITTLE_ENDIAN)
    cpu.ctl_set_cpu_model(mr.UC_CPU_MIPS32_74KF)
    cpu.mem_map(0, 64 * 1024 * 1024)
    cpu.mem_map(0x09D00000, 0x300000)
    cpu.mem_map(0x18800000, 4096)
    cpu.mem_map(0x18818000, 4096)
    cpu.mem_write(0, raw)
    if copy_spec:
        probe = make_probe(int(manifest["probe_entry"], 0), int(manifest["original_entry"], 0),
                           int(manifest["session_tag"], 0), content, unpack_loader(source), copy_spec=copy_spec,
                           fallback_spec=fallback_spec, kernel_handoff=handoff,
                           watchdog_seconds=manifest.get('watchdog_seconds', 30))
        probe_offset = int(manifest["probe_entry"], 0) & 0x1FFFFFFF
        if full_copy or handoff:
            assert bytes(cpu.mem_read(probe_offset, len(probe))) == probe, "candidate code differs from current generator"
        else:
            cpu.mem_write(probe_offset, probe)
    cpu.mem_write(0x09DA0000, unpack_loader(source))

    def put(address, value):
        cpu.mem_write(address & 0x1FFFFFFF, struct.pack("<I", value & 0xFFFFFFFF))

    def get(address):
        return struct.unpack("<I", cpu.mem_read(address & 0x1FFFFFFF, 4))[0]

    for address, value in MASKS.items():
        put(address, value)
    put(0xB8800040, 0xA0)
    put(0xB8800060, 0x0E400F8C)
    put(0x89E66644, 1)
    put(0x89E6665C, TCB)
    depth = 0 if case == "no_critical" else 3 if case == "nested_critical" else 1
    put(TCB + 0x48, depth)
    put(0x89E5F168, 0)
    put(0x89E7FD74, 0)
    arguments = (0xFFFFFFFE, 0x89F56000, 0, 0)
    arg_regs = (mr.UC_MIPS_REG_A0, mr.UC_MIPS_REG_A1, mr.UC_MIPS_REG_A2, mr.UC_MIPS_REG_A3)
    preserved = {mr.UC_MIPS_REG_SP: 0x81C00000, mr.UC_MIPS_REG_GP: 0x89E6E1A0,
                 mr.UC_MIPS_REG_RA: 0x89DADBC8, mr.UC_MIPS_REG_S0: 0x11110000,
                 mr.UC_MIPS_REG_S1: 0x22220000, mr.UC_MIPS_REG_S2: 0x33330000,
                 mr.UC_MIPS_REG_S3: 0x44440000, mr.UC_MIPS_REG_S4: 0x55550000,
                 mr.UC_MIPS_REG_S5: 0x66660000, mr.UC_MIPS_REG_S6: 0x77770000,
                 mr.UC_MIPS_REG_S7: 0x88880000}
    for reg, value in list(zip(arg_regs, arguments)) + list(preserved.items()):
        cpu.reg_write(reg, value)
    cpu.reg_write(mr.UC_MIPS_REG_CP0_STATUS, 0x10000000)
    tag = int(manifest["session_tag"], 0)
    if case in ("pending", "different_tag"):
        for offset, value in [(0, 0x5233364C), (8, 3520), (12, 2), (16, 194),
                              (40, tag if case == "pending" else tag ^ 1)]:
            put(TRACE + offset, value)
    if case == "code_mismatch":
        put(RESOLVE, get(RESOLVE) ^ 1)
    calls = []
    written = bytearray(len(source_data) if copy_spec else 64)
    positions = {}
    bootm_observed = []
    original_plain = decrypt(source_data, recover_key(source)) if fallback_spec else None

    def api(uc, address, size, user):
        assert uc.reg_read(mr.UC_MIPS_REG_CP0_STATUS) & 1
        assert get(TCB + 0x48) == 0
        assert get(0xB8800038) == MASKS[0x89E7B864]
        assert get(0xB880003C) == get(0x89E7BBB4) == MASKS[0x89E7B868]
        assert get(0xB8800040) == 0xA4
        calls.append(hex(address))
        a0, a1, a2 = (uc.reg_read(reg) for reg in arg_regs[:3])
        if address == RESOLVE:
            assert get(0x89E5F168) == 1
            assert bytes(uc.mem_read(a1 & 0x1FFFFFFF, 7)) == b"cubegm\0"
            name = bytes(uc.mem_read(a2 & 0x1FFFFFFF, 13)).split(b"\0", 1)[0]
            assert name in (b"R36PROBE.BIN", b"R36WRITE.BIN", b"R36STOCK.ENC", b"R36COPY.BIN", b"advapi32.dll")
            uc.mem_write(a0 & 0x1FFFFFFF, b"/media/mmcblk0p2/cubegm/" + name + b"\0")
            main_failure = case in ("resolve_error", "fallback_missing", "fallback_corrupt", "bootm_returns") and name == b"R36PROBE.BIN"
            result = -1 if main_failure or case == "fallback_missing" and name == b"R36STOCK.ENC" else 0
        elif address == OPEN:
            path = bytes(uc.mem_read(a0 & 0x1FFFFFFF, 64)).split(b"\0", 1)[0]
            if path.endswith((b"R36WRITE.BIN", b"R36COPY.BIN", b"advapi32.dll")):
                assert a1 in (0, 2)
                result = 8 if a1 == 2 else 9
                if (case == "write_open_error" and a1 == 2) or (case == "verify_open_error" and a1 == 0):
                    result = -1
            elif path.endswith(b"R36STOCK.ENC"):
                assert a1 == 0
                result = 10
            else:
                assert a1 == 0
                result = -1 if case == "open_error" else 7
            if result >= 0:
                positions[result] = 0
        elif address == READ:
            assert a0 in (7, 9, 10)
            if (copy_spec or fallback_spec) and a0 in (9, 10):
                data = bytes(written) if a0 == 9 else source_data
                if a0 == 10 and case in ("backup_corrupt", "fallback_corrupt") or a0 == 9 and case == "target_verify_corrupt":
                    data = data[:-1] + bytes([data[-1] ^ 1])
                if a0 == 10 and case == "backup_short" or a0 == 9 and case == "target_verify_short":
                    data = data[:-1]
                count = min(a2, 4093) if case == "partial_IO" else a2
                block = data[positions[a0]:positions[a0] + count]
                if a0 == 10 and case == "backup_read_error":
                    result = -1
                else:
                    if block:
                        uc.mem_write(a1 & 0x1FFFFFFF, block)
                    positions[a0] += len(block)
                    result = len(block)
                uc.reg_write(mr.UC_MIPS_REG_V0, result & 0xFFFFFFFF)
                uc.reg_write(mr.UC_MIPS_REG_PC, uc.reg_read(mr.UC_MIPS_REG_RA))
                return
            assert a2 == 64
            data = content if a0 == 7 else bytes(written)
            if case == "wrong_content" or case == "verify_corrupt" and a0 == 9:
                data = bytes(64)
            uc.mem_write(a1 & 0x1FFFFFFF, data)
            result = 63 if case == "short_read" else 64
        elif address == WRITE:
            assert a0 == 8
            data = bytes(uc.mem_read(a1 & 0x1FFFFFFF, a2))
            assert data == (source_data[positions[a0]:positions[a0] + a2] if copy_spec else content)
            result = -1 if case == "write_error" else min(a2, 4093) if case == "partial_IO" else 31 if case == "short_write" else a2
            if result > 0:
                written[positions[a0]:positions[a0] + result] = data[:result]
                positions[a0] += result
        elif address == GET_FILE_POINTER:
            assert a0 == 8
            put(a1, 0x80301000)
            result = -9 if case == "bad_file_pointer" else 0
        elif address == FAT_SYNC:
            assert a0 == 0x80301000
            result = -5 if case == "sync_error" else 0
        else:
            assert a0 in (7, 8, 9, 10)
            result = -1 if case == "close_error" or case == "write_close_error" and a0 == 8 else 0
        uc.reg_write(mr.UC_MIPS_REG_V0, result & 0xFFFFFFFF)
        uc.reg_write(mr.UC_MIPS_REG_PC, uc.reg_read(mr.UC_MIPS_REG_RA))

    for address in (RESOLVE, OPEN, READ, CLOSE, WRITE, GET_FILE_POINTER, FAT_SYNC):
        cpu.hook_add(un.UC_HOOK_CODE, api, begin=address, end=address)
    if fallback_spec:
        def decrypt_stub(uc, address, size, user):
            a0, a1, a2, a3 = (uc.reg_read(reg) for reg in arg_regs)
            assert a0 == 0x81000000 and a1 == len(source_data) and a2 == 0x81000010
            container = bytes(uc.mem_read(a0 & 0x1FFFFFFF, a1))
            plain = decrypt(container, recover_key(source))
            uc.mem_write(a2 & 0x1FFFFFFF, plain)
            put(a3, len(plain))
            uc.reg_write(mr.UC_MIPS_REG_V0, 0)
            uc.reg_write(mr.UC_MIPS_REG_PC, uc.reg_read(mr.UC_MIPS_REG_RA))

        def bootm_stub(uc, address, size, user):
            a0, a1, a2, a3 = (uc.reg_read(reg) for reg in arg_regs)
            assert (a0, a1, a2) == (0, 0, 4)
            pointers = struct.unpack("<4I", uc.mem_read(a3 & 0x1FFFFFFF, 16))
            argv = [bytes(uc.mem_read(ptr & 0x1FFFFFFF, 32)).split(b"\0", 1)[0].decode() for ptr in pointers]
            assert argv == ["bootm", "81000010", "-", "89f56000"], argv
            assert bytes(uc.mem_read(0x01000010, len(original_plain))) == original_plain
            assert get(TCB + 0x48) == 0 and uc.reg_read(mr.UC_MIPS_REG_CP0_STATUS) & 1
            bootm_observed.append(argv)
            if case == "bootm_returns":
                uc.reg_write(mr.UC_MIPS_REG_PC, uc.reg_read(mr.UC_MIPS_REG_RA))
            else:
                uc.emu_stop()

        def stop_wait(uc, address, size, user):
            uc.emu_stop()

        if not native_decrypt:
            cpu.hook_add(un.UC_HOOK_CODE, decrypt_stub, begin=DECRYPT, end=DECRYPT)
        cpu.hook_add(un.UC_HOOK_CODE, bootm_stub, begin=BOOTM, end=BOOTM)
        wait = manifest["probe_symbols"]["fallback_wait"]
        cpu.hook_add(un.UC_HOOK_CODE, stop_wait, begin=wait, end=wait)
        terminal = fallback_spec["fail_entry"] + len(terminal_stub()) - 8
        cpu.hook_add(un.UC_HOOK_CODE, stop_wait, begin=terminal, end=terminal)
    entry = int(manifest["original_entry"], 0)
    reached = []
    if handoff:
        profile = Path(manifest.get("source_profile", ROOT / "payload/kernel_ready/boot"))
        with (profile / "vmlinux.elf").open("rb") as handle:
            elf = ELFFile(handle)
            symbols = {s.name: int(s["st_value"]) & 0xFFFFFFFF for s in elf.get_section_by_name(".symtab").iter_symbols() if s.name}

        def kernel_entry(uc, address, size, user):
            assert tuple(uc.reg_read(reg) for reg in arg_regs) == (0xFFFFFFFE, handoff["dtb"], 0, 0)
            assert bytes(written) == source_data
            reached.append("kernel_entry")

        def start_kernel(uc, address, size, user):
            reached.append("start_kernel")
            uc.emu_stop()

        cpu.hook_add(un.UC_HOOK_CODE, kernel_entry, begin=entry, end=entry)
        cpu.hook_add(un.UC_HOOK_CODE, start_kernel, begin=symbols["start_kernel"], end=symbols["start_kernel"])
    cpu.emu_start(int(manifest["probe_entry"], 0), 0x83F00000 if handoff else entry,
                  count=2_000_000_000 if copy_spec or fallback_spec else 100000, timeout=60_000_000)
    stage = get(TRACE + 16)
    if handoff and reached:
        assert reached == ["kernel_entry", "start_kernel"] and case == "success"
        receipt = struct.unpack("<16I", cpu.mem_read(RESTORE_RECEIPT & 0x1FFFFFFF, 64))
        assert receipt[:8] == (RESTORE_MAGIC, 1, tag, 1, len(source_data), zlib.crc32(source_data), zlib.crc32(source_data), 6)
        timeout = manifest.get('watchdog_seconds', 30)
        assert receipt[10] == timeout
        assert get(TRACE + 36) == timeout
        assert get(0xB8818500) == (-187500 * timeout) & 0xFFFFFFFF
        assert get(0xB8818504) == 0x26
        assert not bootm_observed
        return {"case": case, "reached": reached, "stock_Linux_executed": False,
                "pre_kernel_restore_receipt_verified": True, "passed": True}
    if handoff and case == "success":
        raise AssertionError(f"normal cold path did not enter custom kernel: stage={stage}")
    if fallback_spec:
        expected = 209 if case == "bootm_returns" else 207 if case in ("fallback_missing", "fallback_corrupt", "code_mismatch", "no_critical") else 208
        assert stage == expected, (case, stage, hex(cpu.reg_read(mr.UC_MIPS_REG_PC)))
        if expected == 208:
            assert bootm_observed and get(TRACE + 432) == 6
            assert get(TRACE + 436) == zlib.crc32(source_data)
        else:
            assert get(0xB8818500) == (-187500 * 5) & 0xFFFFFFFF
        return {"case": case, "stage": stage, "native_decrypt": native_decrypt,
                "bootm_arguments_verified": bool(bootm_observed), "passed": True}
    forced = manifest["forced_watchdog_test"] and case != "pending"
    if forced:
        assert stage == 194 and cpu.reg_read(mr.UC_MIPS_REG_PC) != entry and not calls
    else:
        assert cpu.reg_read(mr.UC_MIPS_REG_PC) == entry
        assert tuple(cpu.reg_read(reg) for reg in arg_regs) == arguments
        assert all(cpu.reg_read(reg) == value for reg, value in preserved.items())
        assert cpu.reg_read(mr.UC_MIPS_REG_CP0_STATUS) == 0x10000000
        assert get(TCB + 0x48) == depth
        assert get(0x89E5F168) == 0
        if case in ("pending", "code_mismatch", "no_critical"):
            assert stage == {"pending": 197, "code_mismatch": 198, "no_critical": 199}[case] and not calls
            if case == "pending":
                assert get(0xB8818504) == 0
        else:
            expected_success = (202 if copy_spec["restore_stock"] else 203) if copy_spec else 200 if manifest.get("filesystem_write_probe") else 195
            assert stage == (expected_success if case in ("success", "different_tag", "nested_critical", "partial_IO") else 196), (case, stage)
            if copy_spec and stage == expected_success:
                assert bytes(written) == source_data
                assert get(TRACE + 416) == get(TRACE + 420) == zlib.crc32(source_data)
                assert get(TRACE + 400) == len(source_data) and get(TRACE + 424) == 6
            assert get(0xB8800038) == get(0xB880003C) == get(0x89E7BBB4) == 0
            assert get(0xB8800040) == 0xA0
    if case != "pending":
        assert get(0xB8818500) == (-187500 * 30) & 0xFFFFFFFF
        assert get(0xB8818504) == 0x26
    if copy_spec and case in ("backup_corrupt", "backup_short", "backup_read_error"):
        assert hex(WRITE) not in calls
    return {"case": case, "stage": stage, "file_api_call_count": len(calls),
            "copy_bytes": len(source_data) if copy_spec else None, "passed": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--full-copy", action="store_true", help="execute full 4-MB copy and CRCs for one success case")
    parser.add_argument("--native-decrypt", action="store_true", help="execute original decrypt machine code for the fallback success case")
    args = parser.parse_args()
    manifest = json.loads((args.folder / "manifest.json").read_text())
    cases = ["success", "pending"] if manifest["forced_watchdog_test"] else [
        "success", "resolve_error", "open_error", "short_read", "wrong_content",
        "close_error", "pending", "different_tag", "code_mismatch", "nested_critical", "no_critical"]
    if manifest.get("filesystem_write_probe"):
        cases += ["write_open_error", "write_error", "short_write", "bad_file_pointer",
                  "sync_error", "write_close_error", "verify_open_error", "verify_corrupt"]
    if manifest.get("copy_spec"):
        cases += ["partial_IO", "backup_corrupt", "backup_short", "backup_read_error",
                  "write_open_error", "write_error", "bad_file_pointer", "sync_error",
                  "write_close_error", "verify_open_error", "target_verify_corrupt", "target_verify_short"]
    if args.full_copy:
        cases = ["success"]
    if manifest.get("stock_fallback"):
        cases = ["success"] if args.native_decrypt else ["success", "resolve_error", "short_read", "pending",
                                                       "fallback_missing", "fallback_corrupt", "bootm_returns", "code_mismatch", "no_critical"]
    if manifest.get("kernel_handoff"):
        cases = ["resolve_error"] if args.native_decrypt else ["success", "resolve_error", "short_read", "pending", "write_error",
                                                              "fallback_missing", "fallback_corrupt", "bootm_returns"]
    rows = [execute(args.folder, case, full_copy=args.full_copy, native_decrypt=args.native_decrypt) for case in cases]
    result = {"passed": True, "native_loader_critical_and_mask_helpers": True,
              "file_APIs_are_stubs_not_real_SD": True, "hardware_verified": False, "rows": rows}
    report = ("cold_restore_native_fallback.json" if args.native_decrypt else "cold_restore_emulation.json") if manifest.get("kernel_handoff") else "fallback_emulation_native_decrypt.json" if args.native_decrypt else "fallback_emulation.json" if manifest.get("stock_fallback") else "fs_emulation_full_copy.json" if args.full_copy else "fs_emulation.json"
    (args.folder / report).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
