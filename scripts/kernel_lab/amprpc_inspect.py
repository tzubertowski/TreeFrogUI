"""Read stock AMPRPC RAM only; never acknowledge mailboxes or send AVP messages.

Addresses apply exclusively to measured 4.4.186 #23. A capture is not atomic:
unchanged allocation tables do not prove message contents are stable.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import time

BASE = 0x80000000
RAM_END = 0x02F91E50
DATA = 0x80B509B0
CONTROL = 0x80B50DFC
SLOT_SIZE = 0x1000
SLOT_COUNT = 8
DESCRIPTOR_SIZE = 68
CONTROL_SIZE = 104
MAILBOX_PHYS = tuple(0x18800800 + 0x20 * i for i in range(8)) + tuple(
    0x18866800 + 0x20 * i for i in range(8))


def ram_physical(address, size):
    if not isinstance(address, int) or not isinstance(size, int) or size <= 0:
        raise ValueError("invalid RAM read")
    if not 0x80000000 <= address < 0xC0000000:
        raise ValueError("only direct-mapped MIPS RAM pointers are accepted")
    physical = address & 0x1FFFFFFF
    if physical + size > RAM_END:
        raise ValueError("read escapes measured Linux RAM")
    return physical


def decode_tables(descriptor, control):
    if len(descriptor) != DESCRIPTOR_SIZE or len(control) != CONTROL_SIZE:
        raise ValueError("short AMPRPC table")
    words = struct.unpack("<17I", descriptor)
    expected = tuple(0xA0000000 | p for p in MAILBOX_PHYS)
    if words[0] != 66 or words[1:] != expected:
        raise ValueError("stock IRQ/resource fingerprint differs")
    mailboxes = control[0]
    slots = struct.unpack_from("<I", control, 4)[0]
    if mailboxes & ~0x0F or slots & ~0xFF:
        raise ValueError("unexpected allocation bitmap")
    pointers = struct.unpack_from("<8I", control, 72)
    for i, pointer in enumerate(pointers):
        ram_physical(pointer, SLOT_SIZE)
        if pointer & (SLOT_SIZE - 1) or pointer >> 29 != 5:
            raise ValueError("message slot must be page-aligned KSEG1 RAM")
        if pointer != pointers[0] + i * SLOT_SIZE:
            raise ValueError("message slots are not one contiguous 32-KiB pool")
    # Waitqueues are Linux-local objects, not callable pointers received from AVP.
    queues = struct.unpack_from("<16I", control, 8)
    return {
        "irq": words[0], "resources": [hex(p) for p in MAILBOX_PHYS],
        "free_mailboxes": mailboxes, "free_slots": slots,
        "slot_pointers": [hex(p) for p in pointers],
        "waitqueue_words": [hex(p) for p in queues],
    }


def decode_message(raw):
    if len(raw) != SLOT_SIZE:
        raise ValueError("message must fill exactly one slot")
    state, opcode, peer_state, token, result, arg1, arg2 = struct.unpack_from("<7I", raw)
    report = {
        "state": state, "opcode": hex(opcode), "peer_state": peer_state,
        "opaque_waitqueue_or_token": hex(token),
        "word_10": hex(result), "word_14": hex(arg1), "word_18": hex(arg2),
        "interpretation": "unknown_or_stale",
    }
    if opcode == 0x1000 and state in (1, 2):
        end = raw.find(b"\0", 0x1C)
        report["interpretation"] = "observed_open_layout_not_liveness"
        report["path_terminated"] = end >= 0
        if end >= 0:
            report["path_hex"] = raw[0x1C:end].hex()
        report["result_signed"] = struct.unpack_from("<i", raw, 0x10)[0]
    elif state == 3 and opcode == 0x1009 and peer_state in (1, 2, 3):
        inline_length = (arg2 >> 16) & 0x1FFF
        report.update({
            "interpretation": "observed_callback_layout_never_invoke",
            "callback_pointer": hex(result), "callback_argument": hex(arg1),
            "inline_length_bits": inline_length,
            "inline_fits_slot": inline_length <= SLOT_SIZE - 0x20,
            "out_of_line_word": hex(struct.unpack_from("<I", raw, 0x1C)[0]),
        })
    return report


def read_ram(transport, address, size):
    physical = ram_physical(address, size)
    code, raw = transport.run(f"/mnt/sdcard/cubegm/mdump {physical:x} {size}", timeout=20)
    if code or len(raw) != size:
        raise ValueError(f"RAM read failed at {address:#x}: rc={code}, bytes={len(raw)}")
    return raw


def capture(transport, directory):
    # Require a new directory so historical evidence cannot be overwritten.
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    from acceptance import INSPECT, inspect
    code, identity_raw = transport.run(INSPECT, timeout=20)
    if code:
        raise ValueError("cannot read stock identity")
    identity = inspect(identity_raw)
    (directory / "identity.txt").write_bytes(identity_raw)
    descriptor = read_ram(transport, DATA, DESCRIPTOR_SIZE)
    control_before = read_ram(transport, CONTROL, CONTROL_SIZE)
    tables = decode_tables(descriptor, control_before)
    (directory / "descriptor.bin").write_bytes(descriptor)
    (directory / "control_before.bin").write_bytes(control_before)
    messages = []
    for i, pointer in enumerate(tables["slot_pointers"]):
        raw = read_ram(transport, int(pointer, 0), SLOT_SIZE)
        name = f"slot_{i}.bin"
        (directory / name).write_bytes(raw)
        messages.append({"slot": i, "free_at_start": bool(tables["free_slots"] & (1 << i)),
                         "sha256": hashlib.sha256(raw).hexdigest(), **decode_message(raw)})
    descriptor_after = read_ram(transport, DATA, DESCRIPTOR_SIZE)
    control_after = read_ram(transport, CONTROL, CONTROL_SIZE)
    (directory / "descriptor_after.bin").write_bytes(descriptor_after)
    (directory / "control_after.bin").write_bytes(control_after)
    tables_after = decode_tables(descriptor_after, control_after)
    if tables["slot_pointers"] != tables_after["slot_pointers"]:
        raise ValueError("allocation changed while capturing; do not correlate messages")
    report = {"identity": identity, "tables_before": tables, "tables_after": tables_after,
              "table_bytes_unchanged": descriptor == descriptor_after and control_before == control_after,
              "atomic_snapshot": False, "hardware_driver_verified": False,
              "scope": "read-only stock RAM evidence; no MMIO reads/writes or AVP requests",
              "messages": messages}
    (directory / "snapshot.json").write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[2] /
                        "analysis/driver_port/amprpc" / str(time.time_ns()))
    args = parser.parse_args()
    from acceptance import WorkerTransport
    report = capture(WorkerTransport(), args.output)
    print(json.dumps({"output": str(args.output), "tables": report["tables_before"],
                      "atomic_snapshot": False, "hardware_driver_verified": False}, indent=2))


if __name__ == "__main__":
    main()
