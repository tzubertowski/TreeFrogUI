from elftools.elf.elffile import ELFFile
p=r'D:\r36s-\analysis\rootfs_card2\lib\modules\4.4.186-release\extra\dsc.ko'
f=open(p,'rb'); e=ELFFile(f)
secs=[s for s in e.iter_sections()]
names={i:s.name for i,s in enumerate(secs)}
sy=e.get_section_by_name('.symtab')
def symname(idx):
    try: return sy.get_symbol(idx).name
    except Exception: return f'<{idx}>'
for rn,tn in [('.rel.data','.data'),('.rel.rodata','.rodata'),('.rel.gnu.linkonce.this_module','.gnu.linkonce.this_module')]:
    r=e.get_section_by_name(rn)
    if not r: continue
    print('==',rn,'->',tn, 'entries',r.num_relocations() if hasattr(r,'num_relocations') else '?')
    for rel in r.iter_relocations():
        s=symname(rel['r_info_sym'])
        print(f"   off=0x{rel['r_offset']:04x} sym={s:36s} type={rel['r_info_type']}")
