"""Capture stock hardware bindings and decode compatible/reg from its DTB."""
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "release/upstream-TreeFrogUI/apps/usb_mode/pc"))
import r36


def decode_dtb(data):
    if len(data) < 40:
        raise ValueError("short FDT")
    magic, total, structure, strings = struct.unpack_from(">4I", data)
    if magic != 0xD00DFEED or total > len(data):
        raise ValueError("invalid FDT header")
    stack, nodes = [], []
    pos = structure
    while pos + 4 <= total:
        token = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        if token == 1:
            end = data.index(b"\0", pos, total)
            name = data[pos:end].decode("ascii")
            stack.append({"name": name, "properties": {}})
            pos = (end + 4) & ~3
        elif token == 2:
            node = stack.pop()
            props = node["properties"]
            if "compatible" in props:
                nodes.append({
                    "path": "/" + "/".join(n["name"] for n in stack[1:] + [node]),
                    "compatible": props["compatible"].rstrip(b"\0").decode().split("\0"),
                    "status": props.get("status", b"okay\0").rstrip(b"\0").decode(),
                    "reg_hex": props.get("reg", b"").hex(),
                    "interrupts_hex": props.get("interrupts", b"").hex(),
                })
        elif token == 3:
            if pos + 8 > total or not stack:
                raise ValueError("truncated FDT property")
            size, name_offset = struct.unpack_from(">II", data, pos)
            pos += 8
            start = strings + name_offset
            if start >= total or pos + size > total:
                raise ValueError("property outside FDT")
            end = data.index(b"\0", start, total)
            stack[-1]["properties"][data[start:end].decode()] = data[pos:pos + size]
            pos = (pos + size + 3) & ~3
        elif token == 4:
            continue
        elif token == 9:
            return sorted(nodes, key=lambda node: node["path"])
        else:
            raise ValueError(f"unknown FDT token {token}")
    raise ValueError("missing FDT end token")


def main():
    out = ROOT / "analysis/driver_port"
    out.mkdir(exist_ok=True)
    device = r36.R36()
    queries = {
        "identity": "uname -a; cat /proc/cmdline; cat /proc/uptime",
        "modules": "cat /proc/modules; find /lib/modules -type f",
        "devices": "cat /proc/devices; ls -l /dev",
        "interrupts": "cat /proc/interrupts",
        "iomem": "cat /proc/iomem",
        "bindings": "for d in /sys/bus/platform/devices/*; do echo DEVICE=$d; cat $d/modalias 2>/dev/null; echo; readlink $d/driver; done; echo END",
        "input": "cat /proc/bus/input/devices; ls -l /sys/class/input",
        "framebuffer": "for d in /sys/class/graphics/fb*; do echo DEVICE=$d; cat $d/name $d/virtual_size $d/bits_per_pixel $d/stride $d/modes 2>/dev/null; done; echo END",
        "usb": "ls /sys/class/udc; cat /sys/kernel/config/usb_gadget/*/UDC; cat /sys/kernel/config/usb_gadget/*/idVendor; cat /sys/kernel/config/usb_gadget/*/idProduct",
        "dmesg": "dmesg",
    }
    try:
        for name, command in queries.items():
            code, raw = device.run(command)
            (out / f"stock_{name}.txt").write_bytes(raw)
            print(name, "rc", code, "bytes", len(raw), flush=True)
    finally:
        device.close()
    dtb = ROOT / "analysis/card2_files/cubegm_enc/dtb.bin"
    nodes = decode_dtb(dtb.read_bytes())
    (out / "stock_dtb_nodes.json").write_text(json.dumps(nodes, indent=2) + "\n")
    print("DTB compatible nodes", len(nodes))


if __name__ == "__main__":
    main()
