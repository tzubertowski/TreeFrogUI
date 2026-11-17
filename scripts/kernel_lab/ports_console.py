"""Talk only to this project's CDC diagnostic console, not the stock MTP device."""
import argparse
from pathlib import Path
import time

import serial
from serial.tools import list_ports

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("command", nargs="?", default="status")
parser.add_argument("--wait", type=int, default=0)
args = parser.parse_args()
deadline = time.monotonic() + args.wait
port = None
while True:
    matches = [p for p in list_ports.comports() if p.vid == 0x1D6B and p.pid == 0x0104
               and (p.serial_number or "").startswith("R36LAB-")]
    if matches:
        port = matches[0].device
        break
    if time.monotonic() >= deadline:
        raise SystemExit("R36Lab CDC console not enumerated")
    time.sleep(1)
with serial.Serial(port, 115200, timeout=0.2, write_timeout=2) as channel:
    channel.reset_input_buffer()
    channel.write((args.command + "\n").encode("ascii"))
    output = bytearray()
    end = time.monotonic() + 15
    while time.monotonic() < end:
        output.extend(channel.read(4096))
        if b"R36LAB> " in output:
            break
text = output.decode("utf-8", "replace")
print(f"Port: {port}\n{text}")
if not output:
    raise SystemExit("CDC enumerated but no command reply was received")
root = Path(__file__).resolve().parents[2]
label = "".join(c for c in args.command if c.isalnum() or c in "_-")[:48] or "response"
(root / "analysis/driver_port" / f"serial_{label}.txt").write_bytes(output)
