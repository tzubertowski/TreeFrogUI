import sys
from elftools.elf.elffile import ELFFile
from capstone import *

path = sys.argv[1]
data = open(path, "rb").read()
e = ELFFile(open(path, "rb"))
dynsym = e.get_section_by_name(".dynsym")
dynstr = e.get_section_by_name(".dynstr")
rel = e.get_section_by_name(".rel.plt")
names = {}
if rel is not None:
    for r in rel.iter_relocations():
        sym = dynsym.get_symbol(r["r_info_sym"])
        names[r["r_offset"]] = sym.name or ""
got = 0x411254
for k in sorted(names):
    print("GOT %08x -> %s" % (k, names[k]))

md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 + CS_MODE_LITTLE_ENDIAN)
for sec in e.iter_sections():
    if sec.name not in (".text", ".init", ".fini"):
        continue
    print("---- %s ----" % sec.name)
    for i in md.disasm(sec.data(), sec["sh_addr"]):
        line = "%08x  %-24s %s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str)
        if i.mnemonic == "lw" and "$gp" in i.op_str:
            parts = i.op_str.split(",")
            try:
                offv = int(parts[1].strip(), 0)
                tgt = got + offv
                if tgt in names:
                    line += "   ; %s" % names[tgt]
            except Exception:
                pass
        print(line)
