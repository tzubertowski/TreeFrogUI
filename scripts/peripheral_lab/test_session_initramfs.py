"""Verify full session initramfs builder compiles static MIPS32r2 ELFs and valid cpio.gz."""
import gzip
from pathlib import Path
import sys

from elftools.elf.elffile import ELFFile
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/kernel_lab"))
sys.path.insert(0, str(ROOT / "scripts/peripheral_lab"))
from preflight import cpio_files
from prepare_session_initramfs import ZIG, build_session_initramfs


def test_build_session_initramfs_compiles_all_static_mips_binaries(tmp_path):
    if not ZIG.exists():
        pytest.skip("zig compiler not present")
    manifest = build_session_initramfs(tmp_path, ZIG, include_fsck=True)
    assert manifest["cpio_gz_bytes"] > 0
    for expected in ("init", "sbin/r36-chkdsk", "sbin/r36-sysd", "sbin/r36-usb-mtp-adb"):
        assert expected in manifest["files"]

    blob = gzip.decompress((tmp_path / "initramfs.cpio.gz").read_bytes())
    entries = cpio_files(blob)
    for name in ("init", "sbin/r36-chkdsk", "sbin/r36-sysd", "sbin/r36-usb-mtp-adb"):
        assert name in entries
        with (tmp_path / "bins" / name).open("rb") as fh:
            elf = ELFFile(fh)
            assert elf["e_machine"] == "EM_MIPS"
            assert elf.little_endian
            assert not any(s["p_type"] == "PT_INTERP" for s in elf.iter_segments())
