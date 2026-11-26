"""Build and emulate a stock-kernel entry probe locally; never install or reboot."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import secrets
import struct
import zlib

import unicorn as un
from unicorn import mips_const as mr

from build_direct_candidate import li, store
from codec import decrypt, encrypt, make_uimage, parse_uimage, recover_key
from emulate_loader_image import validate
from codec import unpack_loader
from loader_fs_probe import make_probe
from loader_fallback import terminal_stub, FAIL_ENTRY

ROOT = Path(__file__).resolve().parents[2]
TRACE = 0xA2F91000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fs-probe", action="store_true", help="read a sandbox file using loader APIs before stock Linux")
    parser.add_argument("--force-watchdog", action="store_true", help="exercise retained-RAM skip after an intentional watchdog reset")
    parser.add_argument("--write-probe", action="store_true", help="write and read back an existing 64-byte sandbox file")
    parser.add_argument("--copy-probe", action="store_true", help="copy and CRC-verify the full stock container into a sandbox file")
    parser.add_argument("--restore-stock", action="store_true", help="restore advapi32.dll before starting the embedded original stock kernel")
    parser.add_argument("--fallback-stock", action="store_true", help="boot the SD stock backup via native decrypt/bootm instead of the resident kernel")
    args = parser.parse_args()
    if (args.force_watchdog or args.write_probe or args.copy_probe or args.restore_stock or args.fallback_stock) and not args.fs_probe:
        parser.error("filesystem operations require --fs-probe")
    if sum([args.force_watchdog, args.write_probe, args.copy_probe, args.restore_stock, args.fallback_stock]) > 1:
        parser.error("choose one filesystem probe operation")
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error("output must be a new directory in an existing parent")
    source = (ROOT / "analysis/boot_crypto/original_advapi32.dll").read_bytes()
    assert hashlib.md5(source).hexdigest() == "3510ffdfd039f850345ace1489572659"
    loader_source = (ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes()
    key = recover_key(loader_source)
    original = decrypt(source, key)
    header = parse_uimage(original)
    raw = gzip.decompress(original[64:])
    load, entry = int(header["load"], 0), int(header["entry"], 0)
    padding = bytes((-len(raw)) % 16)
    probe_entry = load + len(raw) + len(padding)
    tag = int.from_bytes(secrets.token_bytes(4), "little")
    words = li(8, TRACE)
    metadata = [0x5233364C, 0, 3520, 2, 193, entry, 0, probe_entry,
                0, 0, tag, 0, 0, 0, 0, 0]
    for index, value in enumerate(metadata):
        words += li(9, value) + [store(9, 4 * index, 8)]
    # Preserve the loader's UHI arguments and all CP0/MMIO state.
    words += [store(4, 48, 8), store(5, 52, 8), store(5, 56, 8), 0x0000000F]
    words += li(25, entry) + [0x03200408, 0]
    shim = struct.pack("<" + "I" * len(words), *words)
    content = b"R36FS-READ-PROBE\0" + struct.pack("<I", tag)
    content += bytes(64 - len(content))
    copy_spec = None
    fallback_spec = None
    probe_symbols = {}
    if args.copy_probe or args.restore_stock:
        copy_spec = {"bytes": len(source), "crc32": zlib.crc32(source),
                     "restore_stock": args.restore_stock, "scratch_base": "0x81000000"}
    if args.fallback_stock:
        fallback_spec = {"bytes": len(source), "crc32": zlib.crc32(source), "fail_entry": FAIL_ENTRY}
    if args.fs_probe:
        shim = make_probe(probe_entry, entry, tag, content, unpack_loader(loader_source),
                          force_watchdog=args.force_watchdog, write_probe=args.write_probe, copy_spec=copy_spec,
                          fallback_spec=fallback_spec, force_fallback=args.fallback_stock, symbols_out=probe_symbols)
    payload = raw + padding + shim
    if fallback_spec:
        assert len(payload) < FAIL_ENTRY - load
        payload += bytes(FAIL_ENTRY - load - len(payload)) + terminal_stub()
    plain = make_uimage(payload, load, probe_entry, timestamp=header["timestamp"])
    if args.restore_stock:
        for level, memory, strategy in [(level, memory, strategy) for strategy in (zlib.Z_DEFAULT_STRATEGY, zlib.Z_FILTERED)
                                         for level in (9, 8, 7, 6) for memory in (9, 8)]:
            if len(plain) <= len(source) - 16:
                break
            compressor = zlib.compressobj(level, zlib.DEFLATED, 31, memory, strategy)
            body = compressor.compress(payload) + compressor.flush()
            compact = bytearray(make_uimage(body, load, probe_entry, timestamp=header["timestamp"], compression=0))
            compact[31] = 1
            compact[4:8] = bytes(4)
            struct.pack_into(">I", compact, 4, zlib.crc32(compact[:64]))
            if len(compact) < len(plain):
                plain = bytes(compact)
        if len(plain) > len(source) - 16:
            parser.error(f"restore probe {len(plain)} bytes exceeds original plain size {len(source) - 16}; refusing to require truncation")
        plain += bytes(len(source) - 16 - len(plain))
    wrapped = encrypt(plain, key, secrets.token_bytes(12))
    assert decrypt(wrapped, key) == plain
    loader_result = validate(unpack_loader(loader_source), plain, inflate=True)
    assert loader_result["return_code"] == 0
    assert int(loader_result["entry"], 0) == probe_entry
    cpu = un.Uc(un.UC_ARCH_MIPS, un.UC_MODE_MIPS32 | un.UC_MODE_LITTLE_ENDIAN)
    cpu.ctl_set_cpu_model(mr.UC_CPU_MIPS32_74KF)
    cpu.mem_map(0, 64 * 1024 * 1024)
    cpu.mem_write(load & 0x1FFFFFFF, payload)
    arguments = (0xFFFFFFFE, 0x82E00000, 0, 0)
    registers = (mr.UC_MIPS_REG_A0, mr.UC_MIPS_REG_A1, mr.UC_MIPS_REG_A2, mr.UC_MIPS_REG_A3)
    for register, value in zip(registers, arguments):
        cpu.reg_write(register, value)
    cpu.reg_write(mr.UC_MIPS_REG_CP0_STATUS, 0x10000000)
    if not args.fs_probe:
        cpu.emu_start(probe_entry, entry, count=10000)
        assert cpu.reg_read(mr.UC_MIPS_REG_PC) == entry
        assert tuple(cpu.reg_read(reg) for reg in registers) == arguments
        assert cpu.reg_read(mr.UC_MIPS_REG_CP0_STATUS) == 0x10000000
        assert bytes(cpu.mem_read(load & 0x1FFFFFFF, len(raw))) == raw
        trace = struct.unpack("<16I", cpu.mem_read(TRACE & 0x1FFFFFFF, 64))
        assert trace[4] == 193 and trace[10] == tag
    record = {"deployed": False, "hardware_verified": False,
              "purpose": "isolate NOR image loading and custom entry from new-kernel startup",
              "kernel": "original stock 4.4, not the custom Linux",
              "original_inflated_kernel_bytes_unchanged": True,
              "loader_arguments_and_cp0_status_preserved": True,
              "watchdog_or_other_mmio_writes": args.fs_probe,
              "filesystem_probe": args.fs_probe, "forced_watchdog_test": args.force_watchdog,
              "filesystem_write_probe": args.write_probe,
              "copy_spec": copy_spec,
              "stock_fallback": fallback_spec,
              "probe_symbols": probe_symbols,
              "original_entry": hex(entry), "probe_entry": hex(probe_entry),
              "session_tag": hex(tag), "trace_stage": 208 if fallback_spec else ((202 if args.restore_stock else 203) if copy_spec else 197 if args.force_watchdog else 200 if args.write_probe else 195) if args.fs_probe else 193,
              "probe_bytes": len(shim),
              "sha256": hashlib.sha256(wrapped).hexdigest(),
              "native_loader_image_and_gzip": loader_result,
              "limitations": ["No SoC/cache/SD hardware emulation",
                              "Pre-kernel fixed-size restoration enabled" if args.restore_stock else "No boot-file restoration by this probe",
                              "Physical acceptance requires verified recovery and collecting trace before power-off"]}
    args.out.mkdir()
    (args.out / "advapi32.dll.encrypted.NOT_DEPLOYED").write_bytes(wrapped)
    if args.fs_probe:
        (args.out / "R36PROBE.BIN").write_bytes(content)
    if args.write_probe:
        (args.out / "R36WRITE.BIN").write_bytes(bytes(64))
    if args.copy_probe:
        (args.out / "R36COPY.BIN").write_bytes(bytes(len(source)))
    (args.out / "manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
