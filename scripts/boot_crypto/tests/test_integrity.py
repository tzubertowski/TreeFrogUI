from pathlib import Path
import sys
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/boot_crypto"))
from compact_capture import prepare
from integrity import file_check, manifest_entries, preserve_crc
from capture_dtb import properties


def test_manifest_dtb_check():
    folder = ROOT / "analysis/card2_files/cubegm_enc"
    checks = dict(manifest_entries((folder / "AcXtrnal").read_bytes()))
    assert checks["cubegm/dtb.bin"] == file_check((folder / "dtb.bin").read_bytes())


def test_compact_keeps_size_crc_and_every_other_property():
    old = (ROOT / "analysis/boot_crypto/dtb.live.before.bin").read_bytes()
    new, report = prepare(old)
    assert len(new) == len(old)
    for seed in (0, 0xFFFFFFFF, 0xDEADBEEF, 0x12345678):
        assert zlib.crc32(new, seed) == zlib.crc32(old, seed)
    a, b = properties(old), properties(new)
    assert a.keys() == b.keys()
    assert [(p, k) for p in a for k in a[p] if a[p][k] != b[p][k]] == [("/chosen", "bootargs")]
    args = b["/chosen"]["bootargs"]
    assert args.split(b"\0", 1)[0].decode() == report["bootargs"]
    assert args[-1] == 0 and len(args) == len(a["/chosen"]["bootargs"])


def test_crc_patch_handles_various_positions():
    original = bytes(range(256)) * 4
    for offset in (0, 100, 1020):
        changed = bytearray(original); changed[500] ^= 17
        restored = preserve_crc(changed, offset, zlib.crc32(original))
        assert zlib.crc32(restored) == zlib.crc32(original)
