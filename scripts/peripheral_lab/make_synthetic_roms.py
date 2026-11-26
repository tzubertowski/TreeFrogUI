"""Generate tiny original test programs, no commercial ROM/assets or BIOS.

Both programs publish RAM[0:3] = signature0x42, A-press-seen1, release-seen1.
They draw a simple pattern/color and enable a square-wave audio channel. Useful
for real libretro CPU/video/input/audio callback tests, not real-game acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path


def gameboy():
    rom = bytearray(32768)
    rom[0x100:0x104] = bytes([0x00, 0xC3, 0x50, 0x01])
    rom[0x134:0x144] = b"R36 INPUT TEST".ljust(16, b"\0")
    rom[0x147:0x14A] = bytes(3)  # plain 32KiB ROM, no cartridge RAM
    code = bytearray()
    def emit(*values): code.extend(values)
    def write(value, address): emit(0x3E, value, 0xEA, address & 255, address >> 8)
    emit(0xF3, 0x31, 0xF0, 0xDF)  # DI; LD SP,$DFF0
    write(0, 0xFF40)
    write(0x42, 0xC000); write(0, 0xC001); write(0, 0xC002)
    for i in range(16): write(0xAA if i % 2 else 0x55, 0x8000 + i)
    write(0xE4, 0xFF47); write(0x91, 0xFF40)
    for address, value in [(0xFF26,0x80),(0xFF24,0x77),(0xFF25,0x11),
                           (0xFF11,0x80),(0xFF12,0x80),(0xFF13,0x00),(0xFF14,0x87)]:
        write(value, address)
    loop = 0x150 + len(code)
    write(0x10, 0xFF00)
    emit(0xF0, 0x00, 0xF0, 0x00, 0xE6, 1)  # settle, read P1 & A
    emit(0x20, 8)  # JR NZ,released
    write(1, 0xC001)
    emit(0xC3, loop & 255, loop >> 8)
    emit(0xFA, 0x01, 0xC0, 0xB7, 0x28, 5)  # if press seen, flag release
    write(1, 0xC002)
    emit(0xC3, loop & 255, loop >> 8)
    rom[0x150:0x150 + len(code)] = code
    checksum = 0
    for value in rom[0x134:0x14D]: checksum = (checksum - value - 1) & 255
    rom[0x14D] = checksum
    total = sum(rom) & 65535
    rom[0x14E:0x150] = total.to_bytes(2, "big")
    return bytes(rom)


def nes():
    prg = bytearray([0xEA] * 16384)
    code = bytearray()
    def emit(*values): code.extend(values)
    def write(value, address): emit(0xA9, value, 0x8D, address & 255, address >> 8)
    emit(0x78, 0xD8, 0xA2, 0xFF, 0x9A)  # SEI CLD LDX #FF TXS
    write(0,0x2000); write(0,0x2001)
    write(0x42,0); write(0,1); write(0,2)
    emit(0x2C,0x02,0x20)  # reset PPU address latch
    write(0x3F,0x2006); write(0,0x2006); write(0x21,0x2007)
    write(0x08,0x2001)
    for address,value in [(0x4015,1),(0x4000,0xBF),(0x4001,0),(0x4002,0xFD),(0x4003,0x08)]: write(value,address)
    loop = 0x8000 + len(code)
    write(1,0x4016); write(0,0x4016)
    emit(0xAD,0x16,0x40,0x29,1,0xF0,8)  # BEQ released
    write(1,1)
    emit(0x4C,loop & 255,loop >> 8)
    emit(0xA5,1,0xF0,5)
    write(1,2)
    emit(0x4C,loop & 255,loop >> 8)
    prg[:len(code)] = code
    prg[0x3FFA:0x4000] = bytes([0,0x80,0,0x80,0,0x80])
    header = b"NES\x1a" + bytes([1,1]) + bytes(10)
    return header + bytes(prg) + bytes(8192)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    records = {}
    for name, data in (("input_test.gb", gameboy()), ("input_test.nes", nes())):
        (args.out / name).write_bytes(data)
        records[name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    (args.out / "manifest.json").write_text(json.dumps({"original_synthetic_programs": True, "files": records}, indent=2) + "\n")
    print(json.dumps(records, indent=2))
