from elftools.elf.elffile import ELFFile
import re
for p in (r'D:\r36s-\dumpcard\libemu_md.so.new', r'D:\r36s-\card2_backup\libemu_md.so.stock'):
    print('=====',p)
    try:
        f=open(p,'rb'); e=ELFFile(f)
    except Exception as ex:
        print('ERR',ex); continue
    print('type',e['e_type'],'machine',e['e_machine'],'entry',hex(e['e_entry']))
    for sec in e.iter_sections():
        print(' sec',sec.name,hex(sec['sh_addr']),hex(sec['sh_size']))
    sym=e.get_section_by_name('.dynsym') or e.get_section_by_name('.symtab')
    if sym:
        for i in range(sym.num_symbols()):
            s=sym.get_symbol(i)
            if s.name: print(' sym',s.name,hex(s['st_value']),s['st_info']['type'])
    d=open(p,'rb').read()
    for m in re.finditer(rb'[ -~]{5,}',d):
        t=m.group().decode()
        print('  str @0x%x %s'%(m.start(),t))
