from elftools.elf.elffile import ELFFile
import struct
p=r'D:\r36s-\dumpcard\dump_out\file_rkgame'
e=ELFFile(open(p,'rb'))
print('type',e['e_type'],'entry',hex(e['e_entry']))
for sec in e.iter_sections():
    if sec['sh_flags'] & 0x2 or sec.name in ('.rodata','.data'):
        print(sec.name, hex(sec['sh_addr']), hex(sec['sh_offset']), hex(sec['sh_size']))
