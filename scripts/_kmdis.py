import sys, struct
from capstone import *

DUMP = r"D:\r36s-\analysis\kmem\kernel_80000000.bin"
BASE = 0x80000000
TEXT_END = 0x8033a4d0

d = open(DUMP, "rb").read()
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 + CS_MODE_LITTLE_ENDIAN)
md.detail = True


def off(va):
    return va - BASE


def dis(va, n, title=""):
    print("=== %s @ %08x ===" % (title, va))
    code = d[off(va):off(va) + n]
    for i in md.disasm(code, va):
        print("%08x  %-24s %s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))


def callers(target, span=TEXT_END):
    res = []
    for o in range(0, span - BASE, 4):
        w = struct.unpack_from("<I", d, o)[0]
        if (w >> 26) == 3:  # jal
            t = 0x80000000 | ((w & 0x3FFFFFF) << 2)
            if t == target:
                res.append(BASE + o)
    return res


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "callers":
        t = int(sys.argv[2], 16)
        cs = callers(t)
        print("callers of %08x: %s" % (t, ["%08x" % c for c in cs]))
        for c in cs[:6]:
            dis(c - 0x20, 0x30, "caller %08x" % c)
    else:
        va = int(sys.argv[1], 16)
        n = int(sys.argv[2], 0)
        dis(va, n, "range")
