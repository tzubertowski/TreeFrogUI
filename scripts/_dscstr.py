from elftools.elf.elffile import ELFFile
p=r'D:\r36s-\analysis\rootfs_card2\lib\modules\4.4.186-release\extra\dsc.ko'
e=ELFFile(open(p,'rb'))
for sec in e.iter_sections():
    if sec.name in ('.rodata','.rodata.str1.4','.data','.modinfo','.modinfo.str','__versions'):
        d=sec.data(); print('==',sec.name,hex(len(d)))
        if sec.name in ('.rodata.str1.4','.modinfo'):
            print(repr(d))
        else:
            print(d.hex())
