"""Guard the ELF header-only normalization needed for LLD-built MIPS kernels."""
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def fixture(directory, *, expanded=True, initialized_tail=False, wrong_prefix=False):
    directory.mkdir()
    raw = bytes(range(64))
    data = bytearray(0x380)
    data[:16] = b"\x7fELF\x01\x01\x01" + bytes(9)
    struct.pack_into("<HHIIIIIHHHHHH", data, 16, 2, 8, 1, 0x80100004, 52, 0x300, 0,
                     52, 32, 1, 40, 3, 0)
    struct.pack_into("<8I", data, 52, 1, 0x100, 0x80100000, 0x80100000, 128 if expanded else 64, 128, 7, 4096)
    data[0x100:0x140] = raw if not wrong_prefix else bytes(64)
    data[0x140:0x180] = b"D" * 64
    struct.pack_into("<10I", data, 0x328, 0, 1, 6, 0x80100000, 0x100, 64, 0, 0, 4, 0)
    struct.pack_into("<10I", data, 0x350, 0, 1 if initialized_tail else 8, 3, 0x80100040, 0x140, 64, 0, 0, 4, 0)
    (directory / "vmlinux.elf").write_bytes(data)
    (directory / "vmlinux.bin").write_bytes(raw)
    return bytes(data), raw


def package(directory):
    return subprocess.run([sys.executable, str(ROOT / "scripts/kernel_lab/package_kernel.py"), str(directory), "test-revision", "test"], capture_output=True)


def test_lld_tail_only_changes_program_filesz(tmp_path):
    folder = tmp_path / "lld"
    before, raw = fixture(folder)
    reply = package(folder)
    assert reply.returncode == 0, reply.stderr
    after = (folder / "vmlinux.elf").read_bytes()
    assert after[:68] == before[:68] and after[72:] == before[72:]
    assert struct.unpack_from("<II", after, 68) == (64, 128)
    assert (folder / "vmlinux.bin").read_bytes() == raw
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["filesz"] == 64 and manifest["memsz"] == 128


def test_normal_gnu_layout_is_unchanged(tmp_path):
    folder = tmp_path / "gnu"
    before, _ = fixture(folder, expanded=False)
    assert package(folder).returncode == 0
    assert (folder / "vmlinux.elf").read_bytes() == before
    assert json.loads((folder / "manifest.json").read_text())["elf_program_header_normalization"] is None


def test_reject_initialized_data_in_trimmed_span(tmp_path):
    folder = tmp_path / "initialized"
    before, _ = fixture(folder, initialized_tail=True)
    assert package(folder).returncode != 0
    assert (folder / "vmlinux.elf").read_bytes() == before


def test_reject_different_objcopy_prefix(tmp_path):
    folder = tmp_path / "mismatched"
    before, _ = fixture(folder, wrong_prefix=True)
    assert package(folder).returncode != 0
    assert (folder / "vmlinux.elf").read_bytes() == before
