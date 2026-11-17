from elftools.elf.elffile import ELFFile
from capstone import *
import struct
p=r'D:\r36s-\analysis\rootfs_card2\lib\modules\4.4.186-release\extra\dsc.ko'
f=open(p,'rb'); e=ELFFile(f)
text=e.get_section_by_name('.text').data(); base=0
sy=e.get_section_by_name('.symtab')
names={}
for i in range(1,sy.num_symbols()):
    s=sy.get_symbol(i)
    if s.name and s['st_shndx']==2: names[s['st_value']]=s.name
names.setdefault(0,'dxzVMCTUOHohAWjaiTTZERZpHKIUYkkB')
# build call target map from relocations
rt=e.get_section_by_name('.rel.text')
callmap={}
for rel in rt.iter_relocations():
    off=rel['r_offset']
    add=struct.unpack_from('<I',text,off)[0]
    callmap[off]=add
md=Cs(CS_ARCH_MIPS, CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN)
def dis(lo,hi):
    out=[]
    for ins in md.disasm(text[lo:hi],lo):
        line=f"{ins.address:04x}: {ins.bytes.hex():8s} {ins.mnemonic:8s} {ins.op_str}"
        if ins.address in names and ins.address!=0: line+=f"   <{names[ins.address]}>"
        out.append(line)
    return out
allout=dis(0, len(text))
open(r'D:\r36s-\analysis\dsc_text.asm','w').write('\n'.join(allout))
print('relocs in text:',len(callmap))
for k in sorted(callmap): print(f"  reloc at 0x{k:04x} -> 0x{callmap[k]:04x} {names.get(callmap[k],'')}")
print('functions:')
for a,n in sorted(names.items()): print(f"  0x{a:04x} {n}")
print('len .text',hex(len(text)))
