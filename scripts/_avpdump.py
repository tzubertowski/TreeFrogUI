"""Capture AVP NSH xd output, rejecting missing or reordered memory rows."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "release/upstream-TreeFrogUI/apps/usb_mode/pc"))
import r36

ROW = re.compile(rb"^([0-9a-fA-F]{8}): ((?:[0-9a-fA-F]{8} ){3}[0-9a-fA-F]{8})", re.M)


def parse_dump(raw, address, size):
    rows = ROW.findall(raw)
    expected = (size + 15) // 16
    if len(rows) != expected:
        raise ValueError(f"expected {expected} rows, received {len(rows)}")
    result = bytearray()
    for index, (where, words) in enumerate(rows):
        want = 0xA0000000 + address + index * 16
        if int(where, 16) != want:
            raise ValueError(f"row {index}: expected {want:08x}, got {where.decode()}")
        result.extend(struct.pack("<4I", *(int(word, 16) for word in words.split())))
    return bytes(result[:size])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=lambda v: int(v, 0), default=0x03DE0000)
    parser.add_argument("--size", type=lambda v: int(v, 0), default=1381713)
    parser.add_argument("--chunk", type=int, default=16384)
    parser.add_argument("--output", type=Path, default=ROOT / "analysis/avp_ram.bin")
    args = parser.parse_args()
    if args.start % 16 or args.size <= 0 or not 16 <= args.chunk <= 32768 or args.chunk % 16:
        parser.error("start/chunk must be 16-byte aligned; size positive; chunk 16..32768")
    if not args.output.parent.is_dir():
        parser.error("output parent directory must already exist")
    cache = args.output.with_suffix(".chunks")
    cache.mkdir(exist_ok=True)
    device = r36.R36()
    parts = []
    started = time.monotonic()
    try:
        for offset in range(0, args.size, args.chunk):
            address = args.start + offset
            size = min(args.chunk, args.size - offset)
            count = (size + 15) & ~15
            capture = cache / f"{address:08x}_{count}.txt"
            data = None
            if capture.exists():
                try:
                    data = parse_dump(capture.read_bytes(), address, size)
                except ValueError:
                    pass
            if data is None:
                # ash consumes one escape layer; xd count is DECIMAL, address HEX.
                command = f'/mnt/sdcard/cubegm/virtq2_fixed "xd\\\\x20{address:x}\\\\x20{count}\\\\r" 6000'
                for attempt in range(3):
                    code, raw = device.run(command)
                    if code:
                        raise RuntimeError(f"remote exit code {code}")
                    try:
                        data = parse_dump(raw, address, size)
                        break
                    except ValueError:
                        if attempt == 2:
                            raise
                capture.write_bytes(raw)
            parts.append(data)
            print(f"{offset + size}/{args.size} bytes ({time.monotonic() - started:.1f}s)", flush=True)
    finally:
        device.close()
    result = b"".join(parts)
    args.output.write_bytes(result)
    metadata = {
        "start_physical": hex(args.start), "size": len(result),
        "sha256": hashlib.sha256(result).hexdigest(),
        "source": "AVP NSH xd; each row address checked; little-endian words",
        "scope": "RAM region; correspondence to original firmware file not established",
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="ascii")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
