"""Report board display configuration from the actual boot DTB, without hardware I/O."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/kernel_lab"))
from preflight import properties


def main():
    path = ROOT / "analysis/boot_crypto/original_Bubbles.scr"
    data = path.read_bytes()
    nodes = {}
    for name, values in properties(data).items():
        if not any(term in name.lower() for term in ("de-engine", "mipi", "fb0", "fb1", "boot-fb", "osd")):
            continue
        props = {}
        for key, value in values.items():
            item = {"bytes": len(value)}
            if len(value) <= 128:
                item["hex"] = value.hex()
                if value and len(value) % 4 == 0:
                    item["cells"] = list(struct.unpack(">" + "I" * (len(value) // 4), value))
                if value.endswith(b"\0") and all(byte == 0 or 32 <= byte < 127 for byte in value):
                    item["strings"] = value.rstrip(b"\0").decode().split("\0")
            else:
                item["sha256"] = hashlib.sha256(value).hexdigest()
            props[key] = item
        nodes[name] = props
    result = {"source": str(path), "sha256": hashlib.sha256(data).hexdigest(), "nodes": nodes}
    output = ROOT / "analysis/driver_port/DISPLAY_BOARD_DTB.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
