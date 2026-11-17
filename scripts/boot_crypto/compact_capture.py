"""Prepare a same-size/same-CRC DTB; this tool never connects to the device."""
import hashlib
import json
from pathlib import Path
import shlex
import zlib

from capture_dtb import patch_property, properties
from integrity import preserve_crc, file_check

ROOT = Path(__file__).resolve().parents[2]


def prepare(original):
    before = properties(original)
    old = before["/chosen"]["bootargs"]
    command = "/bin/busybox cat /etc/mdev/* >/r;exec /init"
    args = 'rw console=tty1 noirqdebug rdinit=/bin/sh -- -c "' + command + '"'
    encoded = args.encode("ascii") + b"\0"
    if len(encoded) + 5 > len(old):
        raise ValueError("not enough unused bootargs bytes for compensation")
    value = encoded + bytes(len(old) - len(encoded))
    candidate = patch_property(original, "/chosen", "bootargs", value)
    offset = candidate.index(encoded)
    if candidate.count(encoded) != 1 or len(candidate) != len(original):
        raise ValueError("ambiguous or resized bootargs")
    compensation = offset + len(old) - 5
    candidate = preserve_crc(candidate, compensation, zlib.crc32(original))
    after = properties(candidate)
    changes = [(path, key) for path in before for key in before[path]
               if before[path][key] != after[path][key]]
    if changes != [("/chosen", "bootargs")]:
        raise ValueError("unrelated DT property changed")
    parsed = after["/chosen"]["bootargs"].split(b"\0", 1)[0].decode("ascii")
    if parsed != args or shlex.split(parsed)[-3:] != ["--", "-c", command]:
        raise ValueError("command string changed")
    return candidate, {"bootargs": args, "command_bytes": len(args), "property_bytes": len(old),
                       "compensation_offset": compensation, "file_check": f"{file_check(candidate):08x}",
                       "source_md5": hashlib.md5(original).hexdigest(),
                       "candidate_md5": hashlib.md5(candidate).hexdigest(),
                       "bytes": len(candidate), "deployment_performed": False,
                       "note": "4 compensation bytes are after the first NUL; all offsets and sizes preserved"}


def main():
    root = ROOT / "analysis/boot_crypto"
    original = (root / "dtb.live.before.bin").read_bytes()
    candidate, report = prepare(original)
    (root / "dtb.compact.candidate.bin").write_bytes(candidate)
    (root / "compact_capture_plan.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
