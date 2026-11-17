import json
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from amprpc_inspect import (CONTROL, CONTROL_SIZE, DATA, DESCRIPTOR_SIZE,
                            MAILBOX_PHYS, RAM_END, SLOT_SIZE, capture,
                            decode_message, decode_tables, ram_physical, read_ram)


def tables():
    descriptor = struct.pack("<17I", 66, *(0xA0000000 | p for p in MAILBOX_PHYS))
    control = bytearray(CONTROL_SIZE)
    control[0] = 0x0F
    struct.pack_into("<I", control, 4, 0xFF)
    struct.pack_into("<8I", control, 72, *(0xA21D8000 + i * SLOT_SIZE for i in range(8)))
    return descriptor, bytes(control)


def test_measured_geometry():
    descriptor, control = tables()
    result = decode_tables(descriptor, control)
    assert result["irq"] == 66
    assert result["free_slots"] == 255
    assert result["slot_pointers"][-1] == "0xa21df000"
    assert len(result["resources"]) == 16


@pytest.mark.parametrize("address,size", [
    (0x18800800, 4), (0xB8800800, 4), (0xC0000000, 4),
    (0xFFFFFFFF, 4), (0x80000000 + RAM_END - 1, 2),
    (0x80000000, 0), (0x80000000, -1),
])
def test_no_mmio_or_outside_ram(address, size):
    with pytest.raises(ValueError):
        ram_physical(address, size)


def test_direct_aliases():
    assert ram_physical(0x80200000, 4) == ram_physical(0xA0200000, 4) == 0x200000
    assert ram_physical(0x80000000 + RAM_END - 1, 1) == RAM_END - 1


@pytest.mark.parametrize("target,offset,value", [
    ("descriptor", 0, 65), ("descriptor", 4, 0xB8800804),
    ("control", 0, 0x10), ("control", 4, 0x100),
    ("control", 72, 0xB8800800), ("control", 72, 0x821D8000),
    ("control", 72, 0xA21D8004), ("control", 76, 0xA21DA000),
])
def test_fingerprint_and_pointer_validation(target, offset, value):
    descriptor, control = map(bytearray, tables())
    struct.pack_into("<I", descriptor if target == "descriptor" else control, offset, value)
    with pytest.raises(ValueError):
        decode_tables(descriptor, control)


def test_short_tables():
    descriptor, control = tables()
    with pytest.raises(ValueError):
        decode_tables(descriptor[:-1], control)
    with pytest.raises(ValueError):
        decode_tables(descriptor, control[:-1])


def test_open_layout_signed_return_and_path():
    raw = bytearray(SLOT_SIZE)
    struct.pack_into("<7I", raw, 0, 2, 0x1000, 3, 0x80B50E04, 0xFFFFFFFE, 1, 2)
    raw[0x1C:0x24] = b"/dev/fb\0"
    result = decode_message(raw)
    assert result["result_signed"] == -2
    assert result["path_hex"] == b"/dev/fb".hex()
    assert result["path_terminated"]


def test_unterminated_path():
    raw = bytearray(b"X" * SLOT_SIZE)
    struct.pack_into("<3I", raw, 0, 1, 0x1000, 1)
    result = decode_message(raw)
    assert not result["path_terminated"]
    assert "path_hex" not in result


def test_callback_never_dereferences_pointers_or_assumes_length_fits():
    raw = bytearray(SLOT_SIZE)
    struct.pack_into("<8I", raw, 0, 3, 0x1009, 1, 0, 0xDEADBEEF, 0xFFFFFFFF,
                     0x1FFF0000, 0xB8800800)
    result = decode_message(raw)
    assert result["callback_pointer"] == "0xdeadbeef"
    assert result["inline_length_bits"] == 8191
    assert not result["inline_fits_slot"]
    assert result["out_of_line_word"] == "0xb8800800"


def test_unknown_opcode_remains_unknown():
    raw = bytearray(SLOT_SIZE)
    struct.pack_into("<3I", raw, 0, 3, 0x9999, 1)
    assert decode_message(raw)["interpretation"] == "unknown_or_stale"
    with pytest.raises(ValueError):
        decode_message(raw[:-1])


class FakeRam:
    def __init__(self):
        self.descriptor, self.control = tables()
        self.commands = []
        self.short = False

    def run(self, command, timeout):
        self.commands.append(command)
        if command.startswith("uname -a;"):
            return 0, (b"Linux buildroot 4.4.186-release #23 PREEMPT Tue Jan 27 16:21:59 CST 2026 mips GNU/Linux\n"
                       b"3000.00 0.00\nR36_INSPECT_END\n")
        prefix, address, size = command.split()
        assert prefix == "/mnt/sdcard/cubegm/mdump"
        address, size = int(address, 16), int(size)
        if address == DATA - 0x80000000:
            return 0, self.descriptor
        if address == CONTROL - 0x80000000:
            return 0, self.control
        assert 0x21D8000 <= address <= 0x21DF000 and size == SLOT_SIZE
        return 0, bytes(size - int(self.short))


def test_capture_is_read_only_and_preserves_evidence(tmp_path):
    transport = FakeRam()
    report = capture(transport, tmp_path / "new")
    assert not report["atomic_snapshot"] and not report["hardware_driver_verified"]
    assert len(report["messages"]) == 8
    assert report["table_bytes_unchanged"]
    assert len(transport.commands) == 13
    assert len(list((tmp_path / "new").glob("slot_*.bin"))) == 8
    assert json.loads((tmp_path / "new/snapshot.json").read_text())["tables_before"]["irq"] == 66
    with pytest.raises(FileExistsError):
        capture(transport, tmp_path / "new")


def test_failed_read_never_publishes_snapshot(tmp_path):
    transport = FakeRam()
    transport.short = True
    with pytest.raises(ValueError, match="RAM read failed"):
        capture(transport, tmp_path / "failed")
    assert not (tmp_path / "failed/snapshot.json").exists()


def test_read_guard_runs_before_remote_command():
    transport = FakeRam()
    with pytest.raises(ValueError):
        read_ram(transport, 0xB8800800, 4)
    assert not transport.commands
