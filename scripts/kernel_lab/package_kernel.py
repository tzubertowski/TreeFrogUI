"""Record exact ELF loading bounds for the RAM-only diagnostic kernel."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import re

root = Path(sys.argv[1])
data = (root / "vmlinux.elf").read_bytes()
assert data[:6] == b"\x7fELF\x01\x01"
entry, phoff = struct.unpack_from("<II", data, 24)
phsize, phnum = struct.unpack_from("<HH", data, 42)
segments = [struct.unpack_from("<8I", data, phoff + i * phsize) for i in range(phnum)]
loads = [s for s in segments if s[0] == 1]
assert len(loads) == 1, "loader needs exactly one PT_LOAD"
_, offset, address, physical, filesz, memsz, _, _ = loads[0]
raw = (root / "vmlinux.bin").read_bytes()
normalization = None
if len(raw) < filesz:
    # LLD can leave the segment file span covering trailing NOBITS sections.
    # Keep only initialized section bytes file-backed; retain the full RAM span.
    assert raw == data[offset:offset + len(raw)]
    shoff = struct.unpack_from("<I", data, 32)[0]
    shsize, shnum = struct.unpack_from("<HH", data, 46)
    sections = [struct.unpack_from("<10I", data, shoff + i * shsize) for i in range(shnum)]
    initialized = [s for s in sections if s[2] & 2 and s[1] != 8 and s[5]]
    assert initialized and max(s[3] + s[5] for s in initialized) <= address + len(raw)
    assert any(s[1] == 8 and s[2] & 2 for s in sections)
    changed = bytearray(data)
    load_index = next(i for i, s in enumerate(segments) if s[0] == 1)
    struct.pack_into("<I", changed, phoff + load_index * phsize + 16, len(raw))
    normalization = {"old_filesz": filesz, "initialized_filesz": len(raw), "memsz": memsz,
                     "reason": "exclude trailing NOBITS span from PT_LOAD file bytes"}
    data, filesz = bytes(changed), len(raw)
    (root / "vmlinux.elf").write_bytes(data)
assert len(raw) == filesz
assert data[offset:offset + filesz] == raw
assert 0x80000000 <= address <= entry < address + filesz
assert address + memsz < 0x82e00000
manifest = {
    "upstream": "https://github.com/SiarheiVolkau/linux-hichip",
    "revision": sys.argv[2],
    "profile": sys.argv[3] if len(sys.argv) > 3 else "unspecified",
    "load": hex(address), "entry": hex(entry), "filesz": filesz,
    "memsz": memsz, "end": hex(address + memsz), "dtb": "0x82e00000",
    "hardware_boot_verified": False,
    "elf_program_header_normalization": normalization,
    "sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
               for name in ["System.map", "kernel.config", "r36-lab.dtb", "vmlinux.bin",
                             "vmlinux.elf", "vmlinuz.bin", "modules.tar.gz", "r36hello.ko", "r36memcheck.ko", "r36_amprpc_poll.ko", "r36_hc16xx_drm.ko", "r36_hc16xx_i2s.ko"]
               if (root / name).is_file()},
}
for name in ["init.elf", "initramfs.cpio.gz"]:
    if (root / name).is_file():
        manifest["sha256"][name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
if len(sys.argv) > 4:
    source = Path(sys.argv[4])
    for name, header, define in [
        ("release", "include/generated/utsrelease.h", "UTS_RELEASE"),
        ("build_version", "include/generated/utsversion.h", "UTS_VERSION"),
    ]:
        match = re.search(r'^#define\s+' + define + r'\s+"([^"]+)"', (source / header).read_text(), re.M)
        if not match:
            raise ValueError(f"missing {define}")
        manifest[name] = match.group(1)
(root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
