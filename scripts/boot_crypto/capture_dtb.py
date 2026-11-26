"""Prepare (never deploy) a one-boot DTB for preserving early initramfs tools."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/kernel_lab"))
from preflight import properties


def patch_property(data, path, key, value):
    header = list(struct.unpack_from(">10I", data))
    magic, total, structure, strings, reserve, version, last, cpu, strings_size, structure_size = header
    if magic != 0xD00DFEED or total != len(data) or version < 17:
        raise ValueError("expected complete version17 FDT")
    stack, matches, pos = [], [], structure
    while pos < structure + structure_size:
        start = pos
        token = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        if token == 1:
            end = data.index(b"\0", pos, total)
            stack.append(data[pos:end].decode())
            pos = (end + 4) & ~3
        elif token == 2:
            stack.pop()
        elif token == 3:
            length, name_offset = struct.unpack_from(">II", data, pos)
            pos += 8
            name_start = strings + name_offset
            name = data[name_start:data.index(b"\0", name_start, strings + strings_size)].decode()
            end = (pos + length + 3) & ~3
            if "/" + "/".join(stack[1:]) == path and name == key:
                matches.append((start, end, name_offset))
            pos = end
        elif token == 4:
            pass
        elif token == 9:
            break
        else:
            raise ValueError("invalid FDT structure")
    if len(matches) != 1:
        raise ValueError("expected one existing property")
    begin, end, name_offset = matches[0]
    record = struct.pack(">III", 3, len(value), name_offset) + value + bytes((-len(value)) % 4)
    delta = len(record) - (end - begin)
    result = bytearray(data[:begin] + record + data[end:])
    header[1] += delta
    header[9] += delta
    for index in (2, 3, 4):
        if begin <= header[index] < end:
            raise ValueError("FDT block overlaps property")
        if header[index] >= end:
            header[index] += delta
    struct.pack_into(">10I", result, 0, *header)
    return bytes(result)


def prepare(original):
    before = properties(original)
    old_args = before["/chosen"]["bootargs"].rstrip(b"\0").decode("ascii")
    if "rdinit=" in old_args or "--" in shlex.split(old_args):
        raise ValueError("input already overrides the initial userspace; do not replace user work")
    # No embedded quotes/backslashes: this subset has identical token boundaries
    # in Linux4.4 next_arg and shlex; the quoted -c value is one init argument.
    command = (
        "B=/bin/busybox;D=/r36-capture;$B mkdir -p $D;"
        "$B cp /init $D/init;"
        "$B cp /etc/mdev.conf $D/mdev.conf;"
        "$B cp /etc/mdev/mount-helper.sh $D/mount-helper.sh;"
        "$B ls -l /bin /sbin /usr/bin /usr/sbin /lib /usr/lib >$D/list.txt 2>&1;"
        "for f in /bin/*crypt* /sbin/*crypt* /usr/bin/*crypt* /usr/sbin/*crypt* /lib/*crypt* /usr/lib/*crypt*;"
        "do test -f $f && $B cp $f $D/;done;exec /init"
    )
    args = old_args + ' rdinit=/bin/sh -- -c "' + command + '"'
    if shlex.split(args)[-3:] != ["--", "-c", command]:
        raise ValueError("init argument tokenization changed")
    candidate = patch_property(original, "/chosen", "bootargs", args.encode("ascii") + b"\0")
    after = properties(candidate)
    if set(before) != set(after):
        raise ValueError("unexpected device-tree node change")
    changes = [(path, name) for path in before for name in set(before[path]) | set(after[path])
               if before[path].get(name) != after[path].get(name)]
    if changes != [("/chosen", "bootargs")]:
        raise ValueError(f"unexpected property changes: {changes}")
    if len(candidate) > 0x9000 or len(args) >= 1024:
        raise ValueError("capture exceeds conservative DTB/bootargs size limits")
    return candidate, args, command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "analysis/card2_files/cubegm_enc/dtb.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "analysis/boot_crypto")
    args = parser.parse_args()
    if not args.out.is_dir():
        parser.error("output parent directory must exist")
    original = args.source.read_bytes()
    candidate, bootargs, command = prepare(original)
    (args.out / "dtb.original.bin").write_bytes(original)
    (args.out / "dtb.capture.candidate.bin").write_bytes(candidate)
    record = {
        "source": str(args.source), "source_sha256": hashlib.sha256(original).hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate).hexdigest(), "source_bytes": len(original),
        "candidate_bytes": len(candidate), "only_property_changed": "/chosen/bootargs",
        "bootargs": bootargs, "capture_command": command,
        "deployment_performed": False, "hardware_verified": False,
        "goal": "preserve early initramfs scripts and crypto tools in /r36-capture; exec original /init",
        "limitations": ["stock bootargs override behaviour not yet observed",
                        "tool availability and retained root directory must be tested",
                        "temporary DTB needs an external restoration path before deployment",
                        "does not establish cipher identity or recover a key by itself"],
    }
    (args.out / "capture_plan.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
