"""Prove the conditional pre-jump dependency on the halfword at physical 0x2."""
import argparse
import json
from pathlib import Path
import struct

import unicorn as un
from unicorn import mips_const as mr

from codec import unpack_loader

ROOT = Path(__file__).resolve().parents[2]


def run_case(loader, prefix, magic):
    cpu = un.Uc(un.UC_ARCH_MIPS, un.UC_MODE_MIPS32 | un.UC_MODE_LITTLE_ENDIAN)
    cpu.ctl_set_cpu_model(mr.UC_CPU_MIPS32_74KF)
    cpu.mem_map(0, 8 * 1024 * 1024)
    cpu.mem_map(0x09D00000, 0x300000)
    cpu.mem_map(0x18818000, 4096)
    cpu.mem_write(0x09DA0000, loader)
    cpu.mem_write(0, prefix[:4])
    cpu.mem_write(0x18818A00, struct.pack("<H", magic))
    cpu.mem_write(0x18818A0A, struct.pack("<HI", 0, 1))  # timer = 1000 ms
    cpu.reg_write(mr.UC_MIPS_REG_CP0_STATUS, 0x10000000)
    cpu.reg_write(mr.UC_MIPS_REG_SP, 0x80600000)
    cpu.reg_write(mr.UC_MIPS_REG_RA, 0x80700000)
    polled = []

    def poll(uc, address, size, user):
        polled.append(address)
        uc.emu_stop()

    cpu.hook_add(un.UC_HOOK_CODE, poll, begin=0x89DB9F9C, end=0x89DB9F9C)
    cpu.emu_start(0x89DBA100, 0x80700000, count=10000)
    return {"threshold_ms": struct.unpack_from("<H", prefix, 2)[0],
            "timer_ms": 1000, "magic": hex(magic),
            "entered_wait_poll": bool(polled),
            "returned": cpu.reg_read(mr.UC_MIPS_REG_PC) == 0x80700000}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixed", type=Path, required=True)
    args = parser.parse_args()
    loader = unpack_loader((ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes())
    old = (ROOT / "payload/kernel_direct_advapi_oneshot/cold_payload.raw").read_bytes()
    fixed = (args.fixed / "cold_payload.raw").read_bytes()
    rows = []
    for name, prefix, magic, waiting in [("old_magic_enabled", old, 0x1995, True),
                                         ("fixed_magic_enabled", fixed, 0x1995, False),
                                         ("old_magic_disabled", old, 0, False)]:
        result = run_case(loader, prefix, magic)
        assert result["entered_wait_poll"] == waiting
        assert result["returned"] != waiting
        result["name"] = name
        rows.append(result)
    record = {"passed": True, "original_function": "0x89dba100",
              "called_by_linux_transfer": "0x89dadbac before jalr at 0x89dadbc0",
              "scope": "native pre-jump wait code with synthetic timer; actual magic during failed boot unknown",
              "not_proven_as_sole_hardware_failure_cause": True, "rows": rows}
    (ROOT / "analysis/boot_crypto/loader_wait_emulation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
