"""Stage RAM-only early-check inputs; does NOT build, boot or install a kernel.

Writes a gen_init_cpio list that a separate candidate build may embed. Production
repair remains disabled in the guard; this stage is for read-only acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]


def check_static(path):
    with path.open("rb") as handle:
        elf = ELFFile(handle)
        if elf.elfclass != 32 or not elf.little_endian or elf["e_machine"] != "EM_MIPS" or elf["e_type"] != "ET_EXEC":
            raise ValueError(f"incorrect MIPS ELF: {path}")
        if any(s["p_type"] in ("PT_INTERP", "PT_DYNAMIC") for s in elf.iter_segments()):
            raise ValueError(f"not self-contained: {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--next-init", type=Path, default=ROOT / "analysis/driver_port/r36-display-probe-v2")
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error("output must be new with an existing parent")
    tools = {
        "init": ROOT / "analysis/driver_port/r36-fat-guard-init-staged",
        "next-init": args.next_init,
        "fat-boot-guard": ROOT / "analysis/driver_port/r36-fat-boot-guard-v3",
        "fsck.fat": ROOT / "analysis/driver_port/r36-fsck-cp437-v2",
    }
    for path in tools.values():
        check_static(path)
    # A patched fsck is mandatory; an upstream binary has ambiguous fatal rc1.
    if b"R36_FSCK_COMPLETE_V1" not in tools["fsck.fat"].read_bytes():
        raise ValueError("fsck lacks post-close completion protocol")
    guard = tools["fat-boot-guard"].read_bytes()
    if b"fat_guard=REPAIR_NOT_VALIDATED_NO_WRITE" not in guard:
        raise ValueError("this staging tool requires a production-write-locked guard")
    args.out.mkdir()
    for name, path in tools.items():
        shutil.copy2(path, args.out / name)
    records = [f"dir /{name} {mode} 0 0" for name, mode in
               (("dev", "0755"), ("proc", "0755"), ("sys", "0755"), ("sd", "0755"),
                ("tmp", "1777"), ("sbin", "0755"))]
    records += ["nod /dev/console 0600 0 0 c 5 1"]
    # Paths are intentionally relative to a future build work directory, not
    # hardcoded Windows paths interpreted by a Linux build.
    for name in tools:
        destination = "/sbin/" + name if name in ("fsck.fat", "fat-boot-guard") else "/" + name
        records.append(f"file {destination} fat-guard-ramfs/{name} 0755 0 0")
    (args.out / "initramfs.list").write_text("\n".join(records) + "\n")
    receipt = {"production_repair_enabled": False, "built_into_kernel": False,
               "deployed": False, "hardware_verified": False,
               "scope": "staged static RAM tools for read-only pre-mount acceptance",
               "files_sha256": {name: hashlib.sha256((args.out / name).read_bytes()).hexdigest() for name in tools},
               "requires": ["embed this list in a separate kernel build", "PID1 waits for SD without mounting it",
                            "only continue to next-init if guard returns zero", "export RAM log after successful check",
                            "hardware acceptance before enabling any filesystem writer"]}
    (args.out / "staging_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
