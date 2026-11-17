from elftools.elf.elffile import ELFFile
from capstone import *
p=r'D:\r36s-\dumpcard\dump_out\file_rkgame'
f=open(p,'rb'); e=ELFFile(f)
text=e.get_section_by_name('.text')
tb=text.data(); tva=text['sh_addr']
md=Cs(CS_ARCH_MIPS, CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN); md.detail=False
def show(va,n=48,label=''):
    off=va-tva
    print('=== '+label+f' va=0x{va:x}')
    for ins in md.disasm(tb[off:off+n*4],va):
        print(f"  {ins.address:08x}: {ins.bytes.hex():8s} {ins.mnemonic:8s} {ins.op_str}")
for va in (0x4bbccc,0x4bbd70,0x49cbd4,0x5a3944):
    show(va,26)
