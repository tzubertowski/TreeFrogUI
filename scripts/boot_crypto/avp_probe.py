"""Read-only AVP console commands with bounded WPD calls and retained output."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "payload/kernel_ready/tools"))
import os
os.environ["R36_PROJECT_ROOT"] = str(ROOT)
from acceptance import WorkerTransport


def issue(command, ms=2000):
    # ash consumes one backslash layer; virtq2 consumes the remaining escapes.
    if any(c in command for c in '\\"\r\n'):
        raise ValueError("only plain AVP command text is accepted")
    encoded = command.replace(" ", "\\\\x20") + "\\\\r"
    remote = f'/mnt/sdcard/cubegm/virtq2_fixed "{encoded}" {ms}'
    code, raw = WorkerTransport().run(remote, timeout=15)
    if code:
        raise RuntimeError(f"remote exit={code}: {raw!r}")
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command")
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    raw = issue(args.command)
    if args.save:
        if not args.save.parent.is_dir():
            parser.error("save parent directory must already exist")
        args.save.write_bytes(raw)
    print(raw.decode("utf-8", "replace"))


if __name__ == "__main__":
    main()
