"""Compare the C packet builder with original stock avp_open instructions."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

import unicorn as un
from unicorn import mips_const as mr

ROOT = Path(__file__).resolve().parents[2]


def original(image, path, slot, flags, mode):
    cpu = un.Uc(un.UC_ARCH_MIPS, un.UC_MODE_MIPS32 | un.UC_MODE_LITTLE_ENDIAN)
    cpu.ctl_set_cpu_model(mr.UC_CPU_MIPS32_74KF)
    cpu.mem_map(0, 0x400000)
    cpu.mem_write(0, image[:0x400000])
    cpu.mem_map(0xB50000, 0x2000)
    cpu.mem_map(0x01000000, 0x20000)
    cpu.mem_map(0x01200000, 0x8000)
    cpu.mem_map(0x01400000, 4096)
    source = 0x81000000
    stop = 0x81400000
    cpu.mem_write(source & 0x1FFFFFFF, path + b"\0")
    cpu.mem_write(0xB50E00, struct.pack("<I", 255))
    cpu.mem_write(0xB50E44, struct.pack("<8I", *[0xA1200000 + index * 4096 for index in range(8)]))
    packet = []

    def hook(uc, address, size, user):
        if address == 0x802BA658:
            ptr = uc.reg_read(mr.UC_MIPS_REG_A0)
            packet.append(bytes(uc.mem_read(ptr & 0x1FFFFFFF, 4096)))
            uc.emu_stop()
            return
        if address == 0x8018F584:
            uc.reg_write(mr.UC_MIPS_REG_V0, len(path))
        elif address == 0x802BA580:
            uc.reg_write(mr.UC_MIPS_REG_V0, slot)
        elif address == 0x801943A0:
            dst, src, length = (uc.reg_read(reg) for reg in (mr.UC_MIPS_REG_A0, mr.UC_MIPS_REG_A1, mr.UC_MIPS_REG_A2))
            uc.mem_write(dst & 0x1FFFFFFF, bytes(uc.mem_read(src & 0x1FFFFFFF, length)))
            uc.reg_write(mr.UC_MIPS_REG_V0, dst)
        else:
            uc.reg_write(mr.UC_MIPS_REG_V0, 0)
        uc.reg_write(mr.UC_MIPS_REG_PC, uc.reg_read(mr.UC_MIPS_REG_RA))

    for address in (0x802BA658, 0x8018F584, 0x802BA580, 0x801943A0, 0x8004AD8C, 0x8004B014, 0x8007BE00):
        cpu.hook_add(un.UC_HOOK_CODE, hook, begin=address, end=address)
    for reg, value in [(mr.UC_MIPS_REG_A0, source), (mr.UC_MIPS_REG_A1, flags),
                       (mr.UC_MIPS_REG_A2, mode), (mr.UC_MIPS_REG_SP, 0x8101F000),
                       (mr.UC_MIPS_REG_RA, stop), (mr.UC_MIPS_REG_CP0_STATUS, 0x10000000)]:
        cpu.reg_write(reg, value)
    cpu.emu_start(0x802BAD04, stop, count=100000)
    return packet[0] if packet else None


def main():
    folder = ROOT / "analysis/driver_port"
    executable = folder / "wire_packet.exe"
    subprocess.run(["gcc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", str(ROOT / "scripts/peripheral_lab/wire_packet.c"), "-o", str(executable)], check=True)
    image = (ROOT / "analysis/kmem/kernel_80000000.bin").read_bytes()
    cases = [(b"x", 0, 0, 0), (b"/dev/r36_probe_no_such_device", 0, 0, 0),
             (b"/dev/fb0", 3, 2, 0o644), (b"x" * 255, 7, 0x12345678, 0xFFFFFFFF),
             (b"x" * 4067, 5, 0, 0), (b"x" * 4068, 1, 0, 0), (b"x" * 4095, 0, 0, 0)]
    rows = []
    for path, slot, flags, mode in cases:
        token = 0x80B50E04 + 8 * slot
        output = subprocess.check_output([str(executable), path.decode(), hex(token), hex(flags), hex(mode)])
        rc = struct.unpack_from("<i", output)[0]
        expected = original(image, path, slot, flags, mode)
        if expected is None:
            assert rc < 0
        else:
            assert rc == 0 and output[4:] == expected
        rows.append({"path_bytes": len(path), "slot": slot, "flags": hex(flags), "mode": hex(mode),
                     "accepted": expected is not None, "passed": True})
    result = {"passed": True, "original_function": "0x802bad04",
              "machine_code_sha256": hashlib.sha256(image[0x2BAD04:0x2BAF34]).hexdigest(),
              "scope": "native stock open packet before submission vs C bytes; no hardware/AVP acceptance",
              "stubs": ["strlen", "memcpy", "semaphores", "slot allocator", "submission observation"], "rows": rows}
    (folder / "amprpc_open_wire_verified.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
