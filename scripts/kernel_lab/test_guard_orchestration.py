"""Run actual native guard orchestration with MIPS fsck via a test-only wrapper."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess


def invoke(guard, tool, image):
    return subprocess.run([str(guard), "--image-test", str(tool), str(image)],
                          capture_output=True, text=True, timeout=60)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guard", type=Path, required=True)
    parser.add_argument("--tool", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    results = {}
    for name in ("clean", "dirty", "orphan", "loop", "invalid"):
        # Previous direct tests repaired their working images. Recreate corruption
        # in fresh copies so every orchestration run has independent input.
        import struct
        source = args.images / ("invalid.img" if name == "invalid" else "clean.img")
        target = args.out / (name + ".img")
        shutil.copyfile(source, target)
        if name in ("dirty", "orphan", "loop"):
            with target.open("r+b") as file:
                boot = file.read(512)
                fat = struct.unpack_from("<H", boot, 14)[0] * 512
                size = struct.unpack_from("<I", boot, 36)[0] * 512
                for index in range(2):
                    offset = fat + index * size + (4 if name == "dirty" else 100 * 4)
                    file.seek(offset)
                    word = (struct.unpack("<I", file.read(4))[0] & ~0x08000000) if name == "dirty" else (0x0FFFFFFF if name == "orphan" else 100)
                    file.seek(offset); file.write(struct.pack("<I", word))
        p = invoke(args.guard, args.tool, target)
        expected = ("fat_guard=CLEAN" if name == "clean" else "fat_guard=CHECK_FAILED_NO_REPAIR" if name == "invalid" else "fat_guard=REPAIRED_VERIFIED")
        assert p.returncode == (2 if name == "invalid" else 0) and expected in p.stdout, (name, p.stdout, p.stderr)
        results[name] = {"exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    # Upstream/unpatched tools returning status 1 (or zero) without our final
    # marker must never lead to the writer path.
    for status in (0, 1, 8):
        tool = args.out / f"missing-marker-{status}.sh"
        tool.write_text(f"#!/bin/sh\nexit {status}\n")
        tool.chmod(0o700)
        p = invoke(args.guard, tool, args.out / "clean.img")
        assert p.returncode == 2 and "fat_guard=CHECK_FAILED_NO_REPAIR" in p.stdout
        results[f"missing_marker_{status}"] = {"exit": p.returncode, "stdout": p.stdout}
    report = {"passed": True, "scope": "native Linux guard + real MIPS fsck through qemu-user wrapper; regular images only", "hardware_verified": False, "cases": results}
    (args.out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": True, "cases": len(results), "output": str(args.out / "result.json")}))


if __name__ == "__main__":
    main()
