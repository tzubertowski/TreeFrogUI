"""Print bounded boot-related strings and their MIPS address references offline."""
import argparse
import gzip
import re
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN
from codec import decrypt, recover_key, unpack_loader

ROOT = Path(__file__).resolve().parents[2]
BASE = 0x89DA0000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--range", dest="address_range", help="virtual start:end, hexadecimal")
    parser.add_argument("--kernel-prefixes", action="store_true")
    parser.add_argument("--strings", help="regex selecting strings for the reference scan")
    args = parser.parse_args()
    data = unpack_loader((ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes())
    if args.kernel_prefixes:
        key = recover_key((ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes())
        stock = gzip.decompress(decrypt((ROOT / "analysis/boot_crypto/original_advapi32.dll").read_bytes(), key)[64:])
        candidate = (ROOT / "payload/kernel_direct_advapi_oneshot/cold_payload.raw").read_bytes()
        for name, raw in (("stock", stock), ("failed_direct_candidate", candidate)):
            print(f"{name}: prefix={raw[:16].hex()} halfword_at_physical_2={struct.unpack_from('<H', raw, 2)[0]}")
        return
    dis = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
    if args.address_range:
        start, end = (int(value, 16) for value in args.address_range.split(":"))
        assert BASE <= start < end <= BASE + len(data)
        for ins in dis.disasm(data[start - BASE:end - BASE], start):
            print(f"{ins.address:08x}: {ins.mnemonic:9} {ins.op_str}")
        return
    strings = {}
    for match in re.finditer(rb"[ -~]{5,}", data):
        text = match.group().decode("ascii")
        if "/data/home/" not in text and re.search(args.strings or r"kernel|uImage|bootm|gzip|magic|decompress|Starting|Linux|checksum|Bad Data|load addr|entry point", text, re.I):
            strings[BASE + match.start()] = text
    print("BOOT STRINGS")
    for address, text in strings.items():
        print(f"{address:08x} {text}")
    print("ADDRESS REFERENCES (lui followed within 12 instructions by addiu/ori)")
    for offset in range(0, len(data) - 52, 4):
        word = struct.unpack_from("<I", data, offset)[0]
        if word >> 26 != 15:
            continue
        reg = (word >> 16) & 31
        upper = (word & 65535) << 16
        for delta in range(4, 52, 4):
            low = struct.unpack_from("<I", data, offset + delta)[0]
            op, rs, rt = low >> 26, (low >> 21) & 31, (low >> 16) & 31
            if rs == reg and op in (9, 13):
                immediate = low & 65535
                address = (upper + (immediate - 65536 if op == 9 and immediate & 32768 else immediate)) & 0xFFFFFFFF
                if address in strings:
                    print(f"\nREFERENCE {BASE + offset:08x} -> {address:08x} {strings[address]}")
                    start, end = max(0, offset - 32), min(len(data), offset + delta + 36)
                    for ins in dis.disasm(data[start:end], BASE + start):
                        print(f"{ins.address:08x}: {ins.mnemonic:9} {ins.op_str}")
            if rt == reg and op in (9, 13, 15, 35):
                break


if __name__ == "__main__":
    main()
