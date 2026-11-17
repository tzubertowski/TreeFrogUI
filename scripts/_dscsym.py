from elftools.elf.elffile import ELFFile
p=r'D:\r36s-\analysis\rootfs_card2\lib\modules\4.4.186-release\extra\dsc.ko'
f=open(p,'rb'); e=ELFFile(f)
sy=e.get_section_by_name('.symtab')
syms=[]
for i in range(1, sy.num_symbols()):
    s=sy.get_symbol(i)
    syms.append(s)
    print(f"{i:3d} {s.name:34s} val=0x{s['st_value']:08x} size={s['st_size']:6d} shn={s['st_shndx']} type={s['st_info']['type']}")
# dump .data and .rodata and str1.4
for nm in ('.rodata','.rodata.str1.4','.data','.modinfo'):
    sec=e.get_section_by_name(nm)
    print('==',nm)
    print(sec.data().hex())
