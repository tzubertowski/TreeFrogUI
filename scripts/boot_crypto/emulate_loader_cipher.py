"""Execute the recovered bootloader decrypt routine, not a reimplementation."""
import json
from pathlib import Path
import struct

import unicorn as un
from unicorn import mips_const as mr

from codec import encrypt, recover_key, unpack_loader

ROOT = Path(__file__).resolve().parents[2]
blob = (ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes()
loader, key = unpack_loader(blob), recover_key(blob)
results = []
for size in (1, 63, 64, 65, 257, 4097):
    for inplace in (False, True):
        plain = bytes((i * 17 + 9) & 255 for i in range(size))
        container = encrypt(plain, key, bytes(range(12)))
        cpu = un.Uc(un.UC_ARCH_MIPS, un.UC_MODE_MIPS32 | un.UC_MODE_LITTLE_ENDIAN)
        cpu.ctl_set_cpu_model(mr.UC_CPU_MIPS32_24KEC)
        cpu.mem_map(0, 8 * 1024 * 1024)
        cpu.mem_map(0x09D00000, 0x300000)
        cpu.mem_write(0x09DA0000, loader)
        cpu.mem_write(0x100000, container)
        source, output, outsize, stop = 0x80100000, 0x80200000, 0x80300000, 0x80002000
        if inplace: output = source + 16
        cpu.reg_write(mr.UC_MIPS_REG_CP0_STATUS, 0x10000000)
        cpu.reg_write(mr.UC_MIPS_REG_A0, source)
        cpu.reg_write(mr.UC_MIPS_REG_A1, len(container))
        cpu.reg_write(mr.UC_MIPS_REG_A2, output)
        cpu.reg_write(mr.UC_MIPS_REG_A3, outsize)
        cpu.reg_write(mr.UC_MIPS_REG_SP, 0x80410000)
        cpu.reg_write(mr.UC_MIPS_REG_GP, 0x89E6E1A0)
        cpu.reg_write(mr.UC_MIPS_REG_RA, stop)
        returned = []
        def finish(uc, address, count, user):
            returned.append(True); uc.emu_stop()
        cpu.hook_add(un.UC_HOOK_CODE, finish, begin=stop, end=stop)
        cpu.emu_start(0x89DAB188, 0, count=10_000_000)
        assert returned and cpu.reg_read(mr.UC_MIPS_REG_V0) == 0
        assert struct.unpack("<I", cpu.mem_read(outsize & 0x1FFFFFFF, 4))[0] == size
        assert bytes(cpu.mem_read(output & 0x1FFFFFFF, size)) == plain
        results.append({"bytes": size, "inplace": inplace, "passed": True})
report = {"passed": True, "native_function": "0x89dab188", "cases": results,
          "scope": "original hcboot code including its key deobfuscation and memcpy, emulated MIPS24KE"}
(ROOT / "analysis/boot_crypto/loader_cipher_emulation.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
