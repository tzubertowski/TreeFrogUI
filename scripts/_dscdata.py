from elftools.elf.elffile import ELFFile
import struct
p=r'D:\r36s-\analysis\rootfs_card2\lib\modules\4.4.186-release\extra\dsc.ko'
f=open(p,'rb'); e=ELFFile(f)
ro=e.get_section_by_name('.rodata').data(); da=e.get_section_by_name('.data').data()
def u32(b,o): return struct.unpack_from('<I',b,o)[0]
print('misc_dev .data[0x5c:0x84]:')
for o in range(0x5c,0x84,4): print(f'  +0x{o-0x5c:02x} val=0x{u32(da,o):08x}')
print('rodata 0x120..0x1f8 nonzero/reloc:')
for o in range(0x120,0x1f8,4):
    v=u32(ro,o)
    if v: print(f'  0x{o:04x} = 0x{v:08x}')
print('rodata[0x188:0x1f4] hex:',ro[0x188:0x1f4].hex())
print('rodata[0x100:0x130] hex:',ro[0x100:0x130].hex())
print('rodata[0x000:0x100] hex:',ro[0x000:0x100].hex())
