"""Build Linux 7 with native pre-kernel restoration and a stock-backup boot path."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import secrets
import struct
import zlib

from codec import decrypt, encrypt, make_uimage, parse_uimage, recover_key, unpack_loader
from loader_fs_probe import make_probe, RESTORE_RECEIPT
from loader_fallback import FAIL_ENTRY, terminal_stub
from capture_dtb import properties
from emulate_loader_image import validate

ROOT = Path(__file__).resolve().parents[2]
SHIM = 0x80010000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=ROOT / "payload/kernel_ready/boot")
    parser.add_argument('--watchdog-seconds', type=int, default=30, choices=range(30, 121))
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error("output must be new, with an existing parent")
    frozen = args.profile
    kernel_manifest = json.loads((frozen / "manifest.json").read_text())
    image = (frozen / "vmlinux.bin").read_bytes()
    dtb = (frozen / "r36-lab.dtb").read_bytes()
    for name, data in (("vmlinux.bin", image), ("r36-lab.dtb", dtb)):
        assert hashlib.sha256(data).hexdigest() == kernel_manifest["sha256"][name]
    config = (frozen / "kernel.config").read_text()
    assert "CONFIG_PAGE_SIZE_4KB=y" in config
    memories = [p for p in properties(dtb).values() if p.get("device_type") == b"memory\0"]
    assert len(memories) == 1
    start, size = struct.unpack(">II", memories[0]["reg"])
    receipt_phys = RESTORE_RECEIPT & 0x1FFFFFFF
    assert start == 0 and size // 4096 * 4096 == 0x02F91000
    assert receipt_phys + 64 <= size <= 0x02F92000

    stock = (ROOT / "analysis/boot_crypto/original_advapi32.dll").read_bytes()
    assert hashlib.md5(stock).hexdigest() == "3510ffdfd039f850345ace1489572659"
    loader_source = (ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes()
    loader, key = unpack_loader(loader_source), recover_key(loader_source)
    stock_header = parse_uimage(decrypt(stock, key))
    load, entry = int(kernel_manifest["load"], 0), int(kernel_manifest["entry"], 0)
    memory_size = (kernel_manifest["memsz"] + 4095) & ~4095
    dtb_address = load + memory_size
    tag = int.from_bytes(secrets.token_bytes(4), "little")
    content = b"R36FS-READ-PROBE\0" + struct.pack("<I", tag)
    content += bytes(64 - len(content))
    copy_spec = {"bytes": len(stock), "crc32": zlib.crc32(stock), "restore_stock": True,
                 "scratch_base": "0x81000000"}
    fallback = {"bytes": len(stock), "crc32": zlib.crc32(stock), "fail_entry": FAIL_ENTRY}
    handoff = {"dtb": dtb_address, "kernel_entry": entry}
    symbols = {}
    code = make_probe(SHIM, entry, tag, content, loader, copy_spec=copy_spec,
                      fallback_spec=fallback, kernel_handoff=handoff, symbols_out=symbols,
                      watchdog_seconds=args.watchdog_seconds)
    assert SHIM + len(code) < load
    assert dtb_address + len(dtb) < FAIL_ENTRY < 0x81000000
    payload = bytes(SHIM - 0x80000000) + code
    payload += bytes(load - 0x80000000 - len(payload))
    payload += image + bytes(memory_size - len(image)) + dtb
    payload += bytes(FAIL_ENTRY - 0x80000000 - len(payload)) + terminal_stub()
    assert payload[:4] == bytes(4)
    plain = make_uimage(payload, 0x80000000, SHIM, timestamp=stock_header["timestamp"])
    if len(plain) > len(stock) - 16:
        parser.error("candidate does not fit the original file size")
    plain += bytes(len(stock) - 16 - len(plain))
    wrapped = encrypt(plain, key, secrets.token_bytes(12))
    assert len(wrapped) == len(stock) and decrypt(wrapped, key) == plain
    assert gzip.decompress(plain[64:]) == payload
    native = validate(loader, plain, inflate=True)
    assert native["return_code"] == 0 and int(native["entry"], 0) == SHIM
    record = {"watchdog_seconds": args.watchdog_seconds,
              "deployed": False, "hardware_verified": False, "kernel": "custom Linux " + kernel_manifest["release"],
              "custom_kernel": True, "filesystem_probe": True, "filesystem_write_probe": False,
              "forced_watchdog_test": False, "copy_spec": copy_spec, "stock_fallback": fallback,
              "kernel_handoff": handoff, "original_entry": hex(entry), "probe_entry": hex(SHIM),
              "probe_bytes": len(code), "probe_symbols": symbols, "session_tag": hex(tag),
              "sha256": hashlib.sha256(wrapped).hexdigest(), "trace_stage": 6,
              "source_kernel_sha256": kernel_manifest["sha256"]["vmlinux.bin"],
              "source_dtb_sha256": kernel_manifest["sha256"]["r36-lab.dtb"],
              "source_release": kernel_manifest["release"], "inline_dtb": hex(dtb_address),
              "source_profile": str(frozen),
              "extra_device_files": kernel_manifest.get("extra_device_files", []),
              "restore_receipt_phys": hex(receipt_phys), "source_kernel_load": hex(load),
              "native_loader_image_and_gzip": native,
              "normal_path_requires_stock_Linux_runtime": False,
              "normal_path": "NOR -> native file restoration/CRC -> custom kernel entry -> embedded PID1",
              "error_path": "NOR file APIs -> verified backup -> native decrypt -> bootm -> stock Linux",
              "limitations": ["SoC cold boot requires hardware acceptance", "In-place SD restoration is not a power-loss transaction"]}
    args.out.mkdir()
    (args.out / "advapi32.dll.encrypted.NOT_DEPLOYED").write_bytes(wrapped)
    (args.out / "R36PROBE.BIN").write_bytes(content)
    (args.out / "manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
