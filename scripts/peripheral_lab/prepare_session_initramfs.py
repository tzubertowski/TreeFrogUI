"""Build and package static MIPS32r2 binaries into a full Linux 7.2 session initramfs."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
ZIG = Path(r"C:\Users\palpa\Tools\zig-x86_64-windows-0.17.0\zig.exe")

BINARY_SPECS = [
    ("init", ROOT / "scripts/peripheral_lab/r36_session_init.c", []),
    ("sbin/r36-chkdsk", ROOT / "scripts/kernel_lab/r36_chkdsk_console.c", []),
    ("sbin/r36-sysd", ROOT / "scripts/peripheral_lab/r36_sysd.c", []),
    ("sbin/r36-power-settings", ROOT / "scripts/peripheral_lab/r36_power_settings.c", []),
    ("sbin/r36-usb-mtp-adb", ROOT / "scripts/peripheral_lab/usb_mtp_adb_service.c", []),
]
FSCK_BIN = ROOT / "analysis/driver_port/r36-fsck-cp437-v2"


def compile_static_mips(zig_exe: Path, src: Path, out: Path, extra_flags: Iterable[str] = ()) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(zig_exe),
        "cc",
        "-target",
        "mipsel-linux.4.4-musleabi",
        "-march=mips32r2",
        "-msoft-float",
        "-static",
        "-Os",
        "-Wall",
        "-Wextra",
        "-Werror",
        *extra_flags,
        str(src),
        "-o",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)


def _cpio_newc_entry(name: str, mode: int, data: bytes = b"", rdev_major: int = 0, rdev_minor: int = 0) -> bytes:
    name_bytes = name.encode("utf-8") + b"\x00"
    nlink = 2 if (mode & 0o170000) == 0o040000 else 1
    header = (
        f"070701"
        f"{0:08x}"
        f"{mode:08x}"
        f"{0:08x}"
        f"{0:08x}"
        f"{nlink:08x}"
        f"{0:08x}"
        f"{len(data):08x}"
        f"{0:08x}"
        f"{0:08x}"
        f"{rdev_major:08x}"
        f"{rdev_minor:08x}"
        f"{len(name_bytes):08x}"
        f"{0:08x}"
    ).encode("ascii")
    rec = bytearray(header + name_bytes)
    while len(rec) % 4 != 0:
        rec.append(0)
    if data:
        rec.extend(data)
        while len(rec) % 4 != 0:
            rec.append(0)
    return bytes(rec)


def build_session_initramfs(out_dir: Path, zig_exe: Path = ZIG, include_fsck: bool = True) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    bin_dir = out_dir / "bins"
    bin_dir.mkdir(exist_ok=True)

    files: dict[str, Path] = {}
    for cpio_path, src, flags in BINARY_SPECS:
        dest = bin_dir / cpio_path
        compile_static_mips(zig_exe, src, dest, flags)
        files[cpio_path] = dest

    if include_fsck and FSCK_BIN.is_file():
        files["sbin/fsck.fat"] = FSCK_BIN

    buf = io.BytesIO()
    for d in ("dev", "proc", "sys", "tmp", "sbin", "mnt", "mnt/sdcard"):
        mode = 0o041777 if d == "tmp" else 0o040755
        buf.write(_cpio_newc_entry(d, mode))
    buf.write(_cpio_newc_entry("dev/console", 0o020600, rdev_major=5, rdev_minor=1))

    digests: dict[str, str] = {}
    for cpio_path, host_path in files.items():
        data = host_path.read_bytes()
        digests[cpio_path] = hashlib.sha256(data).hexdigest()
        buf.write(_cpio_newc_entry(cpio_path, 0o100755, data))
    buf.write(_cpio_newc_entry("TRAILER!!!", 0))

    cpio_gz = out_dir / "initramfs.cpio.gz"
    cpio_gz.write_bytes(gzip.compress(buf.getvalue(), compresslevel=9, mtime=0))

    list_lines = [
        "dir /dev 0755 0 0",
        "nod /dev/console 0600 0 0 c 5 1",
        "dir /proc 0755 0 0",
        "dir /sys 0755 0 0",
        "dir /tmp 1777 0 0",
        "dir /sbin 0755 0 0",
        "dir /mnt 0755 0 0",
        "dir /mnt/sdcard 0755 0 0",
    ]
    for cpio_path, host_path in files.items():
        list_lines.append(f"file /{cpio_path} {host_path.as_posix()} 0755 0 0")
    (out_dir / "initramfs.list").write_text("\n".join(list_lines) + "\n", encoding="utf-8")

    manifest = {
        "cpio_gz": cpio_gz.name,
        "cpio_gz_bytes": cpio_gz.stat().st_size,
        "files": digests,
    }
    (out_dir / "session_initramfs_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--zig", type=Path, default=ZIG)
    args = parser.parse_args()
    manifest = build_session_initramfs(args.out, args.zig)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
