"""Build, never install, an encrypted uImage with its own DTB and cold-entry shim."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import secrets
import struct

from codec import decrypt, encrypt, make_uimage, parse_uimage, recover_key
from capture_dtb import patch_property

ROOT = Path(__file__).resolve().parents[2]
SHIM_BASE = 0x80000000
SHIM_ENTRY = 0x80010000
TRACE = 0xA2F91000


def li(register, value):
    value &= 0xFFFFFFFF
    return [0x3C000000 | register << 16 | value >> 16,
            0x34000000 | register << 21 | register << 16 | value & 65535]


def store(register, offset, base):
    return 0xAC000000 | base << 21 | register << 16 | offset & 65535


def shim(entry, dtb, tag, seconds):
    words = [0x41606000, 0x000000C0]  # di; ehb
    words += li(8, TRACE)
    metadata = [0x5233364C, 0, 3520, 2, 192, entry, 0, SHIM_ENTRY,
                187500, seconds, tag, 0, 0, 0, 0, 0]
    for index, value in enumerate(metadata):
        words += li(9, value) + [store(9, index * 4, 8)]
    words += li(8, 0xB8800060)
    words += [0x8D090000]  # lw t1,0(t0)
    words += li(10, 0xFFBFFFFF)
    words += [0x012A4824, store(9, 0, 8), 0x0000000F]  # and; store; sync
    words += li(8, 0xB8818500) + li(9, -187500 * seconds) + [store(9, 0, 8)]
    words += li(9, 0x26) + [store(9, 4, 8), 0x0000000F]
    words += li(4, 0xFFFFFFFE) + li(5, dtb) + li(6, 0) + li(7, 0) + li(25, entry)
    words += [0x03200408, 0]  # jr.hb t9; nop
    return struct.pack("<" + "I" * len(words), *words)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "payload/kernel_ready/boot")
    parser.add_argument("--out", type=Path, default=ROOT / "payload/kernel_direct_candidate")
    parser.add_argument("--oneshot", action="store_true", help="use SD userspace to restore stock before watchdog reset")
    parser.add_argument("--boot-file", choices=["advapi32.dll", "vmlinux.uImage"], default="advapi32.dll")
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error("output must be a new directory in an existing parent")
    manifest = json.loads((args.source / "manifest.json").read_text())
    image, dtb = (args.source / "vmlinux.bin").read_bytes(), (args.source / "r36-lab.dtb").read_bytes()
    assert hashlib.sha256(image).hexdigest() == manifest["sha256"]["vmlinux.bin"]
    assert hashlib.sha256(dtb).hexdigest() == manifest["sha256"]["r36-lab.dtb"]
    if args.oneshot:
        bootargs = ("console=r36ram root=/dev/mmcblk0p1 rootfstype=vfat rootflags=iocharset=iso8859-1 "
                    "rootwait rw rdinit=/r36-no-init init=/rootfs/lib/ld.so.1 clk_ignore_unused loglevel=8 panic=0 "
                    "-- --library-path /rootfs/lib /rootfs/bin/busybox sh /cubegm/r36-direct-once.sh")
        dtb = patch_property(dtb, "/chosen", "bootargs", bootargs.encode() + b"\0")
    load, entry = int(manifest["load"], 0), int(manifest["entry"], 0)
    memory_size = (manifest["memsz"] + 4095) & ~4095
    dtb_address = load + memory_size
    assert SHIM_BASE < SHIM_ENTRY < load and dtb_address + len(dtb) < 0x82F91000
    tag = int.from_bytes(secrets.token_bytes(4), "little")
    code = shim(entry, dtb_address, tag, 30)
    assert len(code) < load - SHIM_ENTRY
    # The stock pre-jump helper reads a boot-wait threshold at physical 0x2.
    # Keep low RAM zero-filled instead of exposing the first shim instruction.
    payload = bytes(SHIM_ENTRY - SHIM_BASE) + code + bytes(load - SHIM_ENTRY - len(code))
    payload += image + bytes(memory_size - len(image)) + dtb
    key = recover_key((ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes())
    stock_map = {
        "advapi32.dll": (ROOT / "analysis/boot_crypto/original_advapi32.dll", "3510ffdfd039f850345ace1489572659", "r36-stock-advapi32-3510ffdf.enc"),
        "vmlinux.uImage": (ROOT / "analysis/card2_files/cubegm_enc/vmlinux.uImage", "f994b5e32dc90c5eec7e4bd965bff8fe", "r36-stock-vmlinux-f994b5e3.enc"),
    }
    stock_source, stock_md5, stock_backup = stock_map[args.boot_file]
    stock = stock_source.read_bytes()
    assert hashlib.md5(stock).hexdigest() == stock_md5
    timestamp = parse_uimage(decrypt(stock, key))["timestamp"]
    legacy = make_uimage(payload, SHIM_BASE, SHIM_ENTRY, timestamp=timestamp)
    wrapped = encrypt(legacy, key, secrets.token_bytes(12))
    assert decrypt(wrapped, key) == legacy
    assert gzip.decompress(legacy[64:]) == payload
    info = parse_uimage(legacy)
    args.out.mkdir()
    (args.out / "vmlinux.uImage.encrypted.NOT_DEPLOYED").write_bytes(wrapped)
    (args.out / "vmlinux.uImage.plain").write_bytes(legacy)
    (args.out / "cold_payload.raw").write_bytes(payload)
    (args.out / "inline.dtb").write_bytes(dtb)
    if args.oneshot:
        script = (ROOT / "scripts/boot_crypto/direct_once.sh").read_text()
        script = script.replace("__STOCK_BACKUP__", stock_backup).replace("__STOCK_FILE__", args.boot_file).replace("__STOCK_MD5__", stock_md5)
        (args.out / "r36-direct-once.sh").write_text(script, encoding="ascii", newline="\n")
    record = {"hardware_verified": False, "deployed": False,
              "image_sha256": hashlib.sha256(wrapped).hexdigest(), "encrypted_bytes": len(wrapped),
              "source_kernel_sha256": manifest["sha256"]["vmlinux.bin"],
              "kernel_load": hex(load), "kernel_entry": hex(entry), "dtb_address": hex(dtb_address),
               "shim_load": hex(SHIM_BASE), "shim_entry": hex(SHIM_ENTRY),
               "low_ram_boot_wait_halfword": struct.unpack_from("<H", payload, 2)[0],
               "shim_bytes": len(code), "session_tag": hex(tag),
              "watchdog_seconds": 30, "legacy": info,
              "route": "unchanged NOR loader -> decrypt ChaCha20 -> inflate -> shim -> our kernel + inline DTB",
              "stock_linux_runtime_required": False,
              "blockers_before_hardware_trial": [
                  "No automatic restoration of stock SD kernel is included: watchdog would reload this image again",
                  "A one-shot restore init or spare-card/manual recovery plan is required before installation",
                  "Bootloader load/entry compatibility still needs a physical cold-start test"],
              "stock_dtb_and_avp_must_remain_unchanged": True, "oneshot": args.oneshot,
              "boot_filename": args.boot_file, "stock_md5": stock_md5,
              "stock_backup": stock_backup, "stock_host_source": str(stock_source)}
    if args.oneshot:
        record["blockers_before_hardware_trial"] = [
            "Verify and stage original stock backup plus direct_once.sh and a fresh run id before installation",
            "Requires existing rootfs/lib/ld.so.1 and rootfs/bin/busybox; inspected applets include devmem",
            "Cold SD-root boot still requires hardware acceptance; reader recovery remains available"]
    (args.out / "manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
