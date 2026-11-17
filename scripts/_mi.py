from elftools.elf.elffile import ELFFile
p=r'D:\r36s-\analysis\rootfs_card2\lib\modules\4.4.186-release\extra\dsc.ko'
e=ELFFile(open(p,'rb'))
print('sections:', [s.name for s in e.iter_sections() if s.name.startswith(('.modinfo','__versions','.gnu.linkonce.this_module'))])
for s in e.iter_sections():
    if s.name=='.modinfo':
        d=s.data()
        for part in d.split(b'\0'):
            if part: print('modinfo:', part.decode('latin1'))
