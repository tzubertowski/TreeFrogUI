"""Replace only an embedded initramfs in a new kernel profile; preserve frozen input."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import zlib

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/kernel_lab"))
from preflight import cpio_files, properties


def initramfs(binary):
    output = bytearray()
    records = [("dev", 0o040755, b"", 0, 0), ("proc", 0o040755, b"", 0, 0),
               ("sys", 0o040755, b"", 0, 0), ("sd", 0o040755, b"", 0, 0),
               ("tmp", 0o041777, b"", 0, 0), ("dev/console", 0o020600, b"", 5, 1),
               ("init", 0o100755, binary, 0, 0), ("TRAILER!!!", 0, b"", 0, 0)]
    for inode, (name, mode, data, major, minor) in enumerate(records, 1):
        name = name.encode() + b"\0"
        values = [inode, mode, 0, 0, 2 if mode & 0o170000 == 0o040000 else 1,
                  0, len(data), 0, 0, major, minor, len(name), 0]
        output.extend(b"070701" + "".join(f"{value:08x}" for value in values).encode())
        output.extend(name)
        output.extend(bytes((-len(output)) % 4))
        output.extend(data)
        output.extend(bytes((-len(output)) % 4))
    assert cpio_files(bytes(output))["init"] == binary
    return gzip.compress(bytes(output), compresslevel=9, mtime=0)


def reserve_framebuffer(data):
    header = list(struct.unpack_from(">10I", data))
    position = header[4]
    while True:
        address, size = struct.unpack_from(">QQ", data, position)
        if not address and not size:
            break
        assert (address, size) not in ((0x01A00000, 1228800), (0x01980000, 0x3C000)), "reservation already present"
        position += 16
    additions = struct.pack(">4Q", 0x01980000, 0x3C000, 0x01A00000, 1228800)
    result = bytearray(data[:position] + additions + data[position:])
    header[1] += len(additions)
    for field in (2, 3):
        if header[field] >= position:
            header[field] += len(additions)
    struct.pack_into(">10I", result, 0, *header)
    assert properties(bytes(result)) == properties(data)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=["avp", "core"], default="avp")
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error("output must be new with an existing parent")
    frozen = ROOT / "payload/kernel_ready/boot"
    manifest = json.loads((frozen / "manifest.json").read_text())
    raw = bytearray((frozen / "vmlinux.bin").read_bytes())
    elf_data = bytearray((frozen / "vmlinux.elf").read_bytes())
    old_blob = (frozen / "initramfs.cpio.gz").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["sha256"]["vmlinux.bin"]
    assert hashlib.sha256(elf_data).hexdigest() == manifest["sha256"]["vmlinux.elf"]
    assert hashlib.sha256(old_blob).hexdigest() == manifest["sha256"]["initramfs.cpio.gz"]
    binary = args.init.read_bytes()
    with args.init.open("rb") as handle:
        init_elf = ELFFile(handle)
        assert init_elf["e_machine"] == "EM_MIPS" and init_elf.little_endian and init_elf.elfclass == 32
        assert not any(s["p_type"] == "PT_INTERP" for s in init_elf.iter_segments())
        assert init_elf.get_section_by_name(".MIPS.abiflags").data()[7] == 3
    with (frozen / "vmlinux.elf").open("rb") as handle:
        elf = ELFFile(handle)
        segments = [p for p in elf.iter_segments() if p["p_type"] == "PT_LOAD"]
        assert len(segments) == 1
        segment = segments[0]
        load, file_offset = int(segment["p_vaddr"]), int(segment["p_offset"])
        assert elf_data[file_offset:file_offset + len(raw)] == raw
        symbols = {s.name: int(s["st_value"]) & 0xFFFFFFFF
                   for s in elf.get_section_by_name(".symtab").iter_symbols() if s.name}
    blob_offset = symbols["__initramfs_start"] - load
    size_offset = symbols["__initramfs_size"] - load
    assert raw[blob_offset:blob_offset + len(old_blob)] == old_blob
    assert struct.unpack_from("<I", raw, size_offset)[0] == len(old_blob)
    new_blob = initramfs(binary)
    if len(new_blob) > len(old_blob):
        parser.error(f"new compressed initramfs exceeds reserved capacity: {len(new_blob)} > {len(old_blob)}")
    replacement = new_blob + bytes(len(old_blob) - len(new_blob))
    raw[blob_offset:blob_offset + len(old_blob)] = replacement
    elf_data[file_offset + blob_offset:file_offset + blob_offset + len(old_blob)] = replacement
    struct.pack_into("<I", raw, size_offset, len(new_blob))
    struct.pack_into("<I", elf_data, file_offset + size_offset, len(new_blob))
    assert elf_data[file_offset:file_offset + len(raw)] == raw
    reverted = raw.copy()
    reverted[blob_offset:blob_offset + len(old_blob)] = old_blob
    struct.pack_into("<I", reverted, size_offset, len(old_blob))
    assert hashlib.sha256(reverted).hexdigest() == manifest["sha256"]["vmlinux.bin"]
    dtb = reserve_framebuffer((frozen / "r36-lab.dtb").read_bytes())
    args.out.mkdir()
    for name in ("System.map", "kernel.config", "r36hello.ko", "r36-wdt-diag"):
        shutil.copy2(frozen / name, args.out / name)
    for name, data in [("vmlinux.bin", raw), ("vmlinux.elf", elf_data), ("init.elf", binary),
                       ("initramfs.cpio.gz", new_blob), ("r36-lab.dtb", dtb)]:
        (args.out / name).write_bytes(data)
        manifest["sha256"][name] = hashlib.sha256(data).hexdigest()
    padded_kernel = bytes(raw) + bytes(((manifest["memsz"] + 4095) & ~4095) - len(raw))
    padded_dtb = dtb + bytes((-len(dtb)) % 4096)
    if args.mode == "core" and b"R36 CORE CONSOLE PROBE V1" not in binary:
        raise ValueError("core PID1 marker missing")
    manifest.update(profile="core-console-probe" if args.mode == "core" else "avp-userspace-probe", hardware_boot_verified=False,
                    source_profile=str(frozen), initramfs_patched_without_kernel_code_rebuild=True,
                    ram_handoff_supported=False,
                    elf_build_id_stale_after_initramfs_patch=True,
                    relocation_crc32=f"{zlib.crc32(padded_dtb, zlib.crc32(padded_kernel)):08x}")
    manifest["sha256"] = {name: digest for name, digest in manifest["sha256"].items() if (args.out / name).is_file()}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    patch = {"kernel_code_changed": False, "frozen_input_modified": False,
             "old_initramfs_bytes": len(old_blob), "new_initramfs_bytes": len(new_blob),
             "blob_offset": hex(blob_offset), "size_word_offset": hex(size_offset),
             "framebuffer1_reservation": {"physical": "0x01a00000", "bytes": 1228800},
             "conservative_ge_mapping_reservation": {"physical": "0x01980000", "bytes": 0x3C000},
             "probe_sha256": hashlib.sha256(binary).hexdigest(), "profile": str(args.out),
             "hardware_verified": False, "device_available": False}
    (args.out / "patch_receipt.json").write_text(json.dumps(patch, indent=2) + "\n")
    print(json.dumps(patch, indent=2))


if __name__ == "__main__":
    main()
