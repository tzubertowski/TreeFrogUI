"""Validate fsck 64-bit seeks using one NEW sparse regular FAT image, never SD."""
import argparse
import json
from pathlib import Path
import struct
import subprocess


def execute(tool, *args):
    p = subprocess.run(["qemu-mipsel", "-cpu", "74Kf", str(tool), *map(str, args)],
                       capture_output=True, text=True, timeout=120)
    return {"exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fsck", type=Path, required=True)
    parser.add_argument("--mkfs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    image = args.out / "large.img"
    with image.open("xb") as f:
        f.truncate(5 * 1024**3)
    formatted = execute(args.mkfs, "-F", "32", "-s", "8", "--codepage=437", image)
    assert formatted["exit"] == 0, formatted
    with image.open("r+b") as f:
        boot = f.read(512)
        bps = struct.unpack_from("<H", boot, 11)[0]
        reserved = struct.unpack_from("<H", boot, 14)[0]
        fatsz = struct.unpack_from("<I", boot, 36)[0]
        root = struct.unpack_from("<I", boot, 44)[0]
        cluster_bytes = bps * boot[13]
        data = (reserved + boot[16] * fatsz) * bps
        high = ((4 * 1024**3 + 1024**2 - data) // cluster_bytes) + 2
        physical = data + (high - 2) * cluster_bytes
        assert physical > 0xFFFFFFFF and physical + cluster_bytes < image.stat().st_size
        for i in range(boot[16]):
            f.seek((reserved + i * fatsz) * bps + high * 4)
            f.write(struct.pack("<I", 0x0FFFFFFF))
        entry = bytearray(32)
        entry[:11] = b"HIGH       "; entry[11] = 0x10
        struct.pack_into("<H", entry, 20, high >> 16)
        struct.pack_into("<H", entry, 26, high & 0xFFFF)
        f.seek(data + (root - 2) * cluster_bytes)
        f.write(entry)
        directory = bytearray(cluster_bytes)
        directory[:11] = b".          "; directory[11] = 0x10
        struct.pack_into("<H", directory, 20, high >> 16)
        struct.pack_into("<H", directory, 26, high & 0xFFFF)
        directory[32:43] = b"..         "; directory[43] = 0x10
        f.seek(physical); f.write(directory)
    check = execute(args.fsck, "-c", "437", "-n", "-l", image)
    assert check["exit"] in (0, 1) and "R36_FSCK_COMPLETE_V1 mode=check" in check["stdout"], check
    assert "/HIGH" in check["stdout"], check
    repair = execute(args.fsck, "-c", "437", "-a", image)
    assert repair["exit"] in (0, 1) and "R36_FSCK_COMPLETE_V1 mode=repair" in repair["stdout"], repair
    verify = execute(args.fsck, "-c", "437", "-n", image)
    assert verify["exit"] == 0, verify
    report = {"passed": True, "high_directory_offset": physical, "image_bytes": image.stat().st_size,
              "scope": "MIPS fsck directory traversal above 4 GiB in sparse regular image, no real SD",
              "check": check, "repair": repair, "verify": verify}
    (args.out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": True, "high_directory_offset": physical}))


if __name__ == "__main__":
    main()
