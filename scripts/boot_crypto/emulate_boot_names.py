"""Verify the filename-remapping prefix of the original hcboot path resolver."""
import json
from pathlib import Path

import unicorn as un
from unicorn import mips_const as mr
from codec import unpack_loader

ROOT = Path(__file__).resolve().parents[2]
loader = unpack_loader((ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes())
rows = []
for original, expected in [("vmlinux.uImage", "advapi32.dll"), ("dtb.bin", "Bubbles.scr"),
                           ("avp.uImage", "ApplicationFrame.dll")]:
    cpu = un.Uc(un.UC_ARCH_MIPS, un.UC_MODE_MIPS32 | un.UC_MODE_LITTLE_ENDIAN)
    cpu.ctl_set_cpu_model(mr.UC_CPU_MIPS32_24KEC)
    cpu.mem_map(0, 8 * 1024 * 1024); cpu.mem_map(0x09D00000, 0x300000)
    cpu.mem_write(0x09DA0000, loader)
    # Startup 0x89daa7e0..0x89daa804 clears this flag when the 128-MiB
    # address alias probe succeeds. The same alias is observed on this unit.
    cpu.mem_write(0x09E5F168, bytes(4))
    cpu.mem_write(0x100000, original.encode() + b"\0")
    for register, value in [(mr.UC_MIPS_REG_CP0_STATUS, 0x10000000),
                            (mr.UC_MIPS_REG_A0, 0x80200000), (mr.UC_MIPS_REG_A1, 0),
                            (mr.UC_MIPS_REG_A2, 0x80100000), (mr.UC_MIPS_REG_A3, 0),
                            (mr.UC_MIPS_REG_SP, 0x80410000), (mr.UC_MIPS_REG_GP, 0x89E6E1A0)]:
        cpu.reg_write(register, value)
    observed = []
    def capture(uc, address, size, user):
        pointer = uc.reg_read(mr.UC_MIPS_REG_S1)
        data = bytes(uc.mem_read(pointer & 0x1FFFFFFF, 64)).split(b"\0", 1)[0].decode()
        observed.append(data); uc.emu_stop()
    cpu.hook_add(un.UC_HOOK_CODE, capture, begin=0x89DA9198, end=0x89DA9198)
    cpu.emu_start(0x89DA9130, 0, count=100000)
    assert observed == [expected], (original, observed)
    rows.append({"logical": original, "resolved": expected, "native_code_verified": True})
record = {"verified": True, "function": "0x89da9130", "mapping_enabled_flag": "global0x89e5f168 equals0",
          "selection": "startup clears flag after a8000020/a0000020 alias probe (128 MiB)", "rows": rows}
(ROOT / "analysis/boot_crypto/boot_names_verified.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
