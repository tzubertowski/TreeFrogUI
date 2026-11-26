from elftools.elf.elffile import ELFFile
from capstone import *
p=r'D:\r36s-\dumpcard\dump_out\file_driver.so'
e=ELFFile(open(p,'rb'))
print('type',e['e_type'],'entry',hex(e['e_entry']))
segs=[]
for s in e.iter_segments():
    if s['p_type']=='PT_LOAD': segs.append((s['p_vaddr'],s['p_offset'],s['p_filesz']))
    print('seg',hex(s['p_vaddr']),hex(s['p_offset']),hex(s['p_filesz']))
f=open(p,'rb')
md=Cs(CS_ARCH_MIPS, CS_MODE_MIPS32+CS_MODE_LITTLE_ENDIAN)
def show(va,n=60):
    for v,o,sz in segs:
        if v<=va<v+sz:
            off=o+(va-v); data=open(p,'rb').read()[off:off+n*4]
            print(f'=== va=0x{va:x} off=0x{off:x}')
            for ins in md.disasm(data,va):
                print(f"  {ins.address:08x}: {ins.bytes.hex():8s} {ins.mnemonic:8s} {ins.op_str}")
            return
    print('unmapped',hex(va))
show(0x3370,80)
show(0x6ac0,40)
