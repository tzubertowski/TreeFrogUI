import sys
from capstone import *

path = sys.argv[1]
base = int(sys.argv[2], 16)
length = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x8000
out = sys.argv[4] if len(sys.argv) > 4 else None

d = open(path, 'rb').read()[:length]
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
lines = []
for ins in md.disasm(d, base):
    lines.append("%08x  %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
txt = "\n".join(lines)
if out:
    open(out, 'w', encoding='utf-8').write(txt + "\n")
    print("wrote %d lines -> %s" % (len(lines), out))
else:
    print(txt)
