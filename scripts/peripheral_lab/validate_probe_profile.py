"""Verify profile patch bounds, static PID1, framebuffer reservations and cold wrapper."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/kernel_lab"))
sys.path.insert(0, str(ROOT / "scripts/boot_crypto"))
from preflight import cpio_files, properties
from codec import decrypt, recover_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--cold", type=Path, required=True)
    args = parser.parse_args()
    profile = args.profile
    manifest = json.loads((profile / "manifest.json").read_text())
    patch = json.loads((profile / "patch_receipt.json").read_text())
    frozen = ROOT / "payload/kernel_ready/boot"
    original = json.loads((frozen / "manifest.json").read_text())
    for name, expected in original["sha256"].items():
        assert hashlib.sha256((frozen / name).read_bytes()).hexdigest() == expected, name
    for name, expected in manifest["sha256"].items():
        assert hashlib.sha256((profile / name).read_bytes()).hexdigest() == expected, name
    raw = bytearray((profile / "vmlinux.bin").read_bytes())
    blob = (profile / "initramfs.cpio.gz").read_bytes()
    init = (profile / "init.elf").read_bytes()
    assert cpio_files(gzip.decompress(blob))["init"] == init
    blob_offset, size_offset = int(patch["blob_offset"], 0), int(patch["size_word_offset"], 0)
    assert struct.unpack_from("<I", raw, size_offset)[0] == len(blob)
    assert raw[blob_offset:blob_offset + len(blob)] == blob
    original_blob = (frozen / "initramfs.cpio.gz").read_bytes()
    raw[blob_offset:blob_offset + len(original_blob)] = original_blob
    struct.pack_into("<I", raw, size_offset, len(original_blob))
    assert hashlib.sha256(raw).hexdigest() == original["sha256"]["vmlinux.bin"]
    with (profile / "vmlinux.elf").open("rb") as handle:
        elf = ELFFile(handle)
        segment = next(p for p in elf.iter_segments() if p["p_type"] == "PT_LOAD")
        assert segment.data() == (profile / "vmlinux.bin").read_bytes()
    dtb = (profile / "r36-lab.dtb").read_bytes()
    assert properties(dtb) == properties((frozen / "r36-lab.dtb").read_bytes())
    position = struct.unpack_from(">I", dtb, 16)[0]
    reservations = []
    while True:
        entry = struct.unpack_from(">QQ", dtb, position)
        if entry == (0, 0): break
        reservations.append(entry)
        position += 16
    assert (0x01A00000, 1228800) in reservations and (0x01980000, 245760) in reservations
    cold = json.loads((args.cold / "manifest.json").read_text())
    binary = (args.cold / "advapi32.dll.encrypted.NOT_DEPLOYED").read_bytes()
    assert hashlib.sha256(binary).hexdigest() == cold["sha256"]
    key = recover_key((ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes())
    payload = gzip.decompress(decrypt(binary, key)[64:])
    offset = int(manifest["load"], 0) - 0x80000000
    assert payload[offset:offset + manifest["filesz"]] == (profile / "vmlinux.bin").read_bytes()
    result = {"passed": True, "kernel_code_unchanged": True, "frozen_verified_unchanged": True,
              "new_PID1_in_archive": True, "ELF_and_flat_image_agree": True,
              "reserved_display_ranges": [{"start": hex(a), "bytes": b} for a, b in reservations],
              "cold_image_sha256": cold["sha256"], "hardware_verified": False, "deployed": False}
    (args.cold / "profile_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
