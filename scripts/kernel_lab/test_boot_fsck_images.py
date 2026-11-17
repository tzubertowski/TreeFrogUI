"""Regular-image-only integration tests under qemu-mipsel inside the build VM.

Pass absolute paths for a NEW test directory and the patched tools. Never pass
block devices: the directory must not exist and mkfs gets only files created here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess


def run(tool, *args):
    process = subprocess.run(["qemu-mipsel", "-cpu", "74Kf", str(tool), *map(str, args)],
                             capture_output=True, text=True, timeout=60)
    return {"exit": process.returncode, "stdout": process.stdout, "stderr": process.stderr}


def geometry(image):
    with image.open("rb") as handle:
        boot = handle.read(512)
    sector = struct.unpack_from("<H", boot, 11)[0]
    reserved = struct.unpack_from("<H", boot, 14)[0]
    fat_sectors = struct.unpack_from("<I", boot, 36)[0]
    assert sector == 512 and boot[16] == 2
    return reserved * sector, fat_sectors * sector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fsck", type=Path, required=True)
    parser.add_argument("--mkfs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--guard", type=Path)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    tool = args.fsck.resolve()
    baseline = args.out / "clean.img"
    with baseline.open("xb") as handle:
        handle.truncate(64 * 1024 * 1024)
    formatted = run(args.mkfs, "-F", "32", "--codepage=437", baseline)
    assert formatted["exit"] == 0, formatted
    cases = {"codepage": run(tool, "-c", "437", "--help")}
    assert cases["codepage"]["exit"] == 0
    cases["clean"] = run(tool, "-c", "437", "-n", baseline)
    assert cases["clean"]["exit"] == 0 and "R36_FSCK_COMPLETE_V1 mode=check status=0" in cases["clean"]["stdout"], cases
    fat, size = geometry(baseline)
    for name in ("dirty", "orphan", "loop"):
        image = args.out / (name + ".img")
        shutil.copyfile(baseline, image)
        with image.open("r+b") as handle:
            for index in range(2):
                if name == "dirty":
                    pos = fat + index * size + 4
                    handle.seek(pos)
                    word = struct.unpack("<I", handle.read(4))[0] & ~0x08000000
                else:
                    pos = fat + index * size + 100 * 4
                    word = 0x0FFFFFFF if name == "orphan" else 100
                handle.seek(pos); handle.write(struct.pack("<I", word))
        if args.guard:
            guarded_image = args.out / (name + "-guard.img")
            shutil.copyfile(image, guarded_image)
            guarded = run(args.guard, "--image-test", tool, guarded_image)
            assert guarded["exit"] == 0 and "fat_guard=REPAIRED_VERIFIED" in guarded["stdout"], guarded
            guarded_verify = run(tool, "-c", "437", "-n", guarded_image)
            assert guarded_verify["exit"] == 0, guarded_verify
            cases[name + "_guard"] = guarded
        before = hashlib.sha256(image.read_bytes()).hexdigest()
        check = run(tool, "-c", "437", "-n", image)
        assert check["exit"] == 1 and "R36_FSCK_COMPLETE_V1 mode=check status=1" in check["stdout"], check
        assert hashlib.sha256(image.read_bytes()).hexdigest() == before, "read-only check wrote the image"
        repair = run(tool, "-c", "437", "-a", "-f", image)
        assert repair["exit"] == 1 and "R36_FSCK_COMPLETE_V1 mode=repair status=1" in repair["stdout"], repair
        verify = run(tool, "-c", "437", "-n", image)
        assert verify["exit"] == 0 and "R36_FSCK_COMPLETE_V1 mode=check status=0" in verify["stdout"], verify
        cases[name] = {"check": check, "repair": repair, "verify": verify}
    bad = args.out / "invalid.img"
    bad.write_bytes(bytes(4096))
    cases["invalid"] = run(tool, "-c", "437", "-n", bad)
    assert cases["invalid"]["exit"] == 8 and "R36_FSCK_COMPLETE" not in cases["invalid"]["stdout"], cases["invalid"]
    report = {"passed": True, "scope": "regular FAT32 image tests only; no block device/hardware",
              "fsck_sha256": hashlib.sha256(tool.read_bytes()).hexdigest(), "cases": cases}
    (args.out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": True, "cases": list(cases), "output": str(args.out / "result.json")}))


if __name__ == "__main__":
    main()
