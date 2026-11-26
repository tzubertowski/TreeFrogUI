from elftools.elf.elffile import ELFFile
from elftools.dwarf.descriptions import describe_form_class
p=r'D:\r36s-\analysis\rootfs_card2\lib\modules\4.4.186-release\extra\dsc.ko'
f=open(p,'rb'); e=ELFFile(f); dw=e.get_dwarf_info()
out=[]
for cu in dw.iter_CUs():
    top=cu.get_top_DIE()
    lp=cu['version']
    for die in cu.iter_DIEs():
        t=die.tag
        if t in ('DW_TAG_subprogram','DW_TAG_variable','DW_TAG_structure_type','DW_TAG_union_type','DW_TAG_typedef','DW_TAG_member','DW_TAG_enumerator','DW_TAG_constant'):
            name=die.attributes.get('DW_AT_name')
            name=name.value.decode() if name else ''
            addr=die.attributes.get('DW_AT_low_pc')
            a=addr.value if addr else None
            if t=='DW_TAG_subprogram':
                out.append(('FUNC',a,name))
            elif t=='DW_TAG_variable':
                out.append(('VAR',a,name))
            elif t in ('DW_TAG_structure_type','DW_TAG_union_type'):
                out.append(('TYPE',None,name))
            elif t=='DW_TAG_enumerator':
                v=die.attributes.get('DW_AT_const_value')
                out.append(('ENUM',v.value if v else None, name))
            elif t=='DW_TAG_member':
                out.append(('MEMB',None,name))
            elif t=='DW_TAG_constant':
                v=die.attributes.get('DW_AT_const_value')
                out.append(('CONST',v.value if v else None, name))
for kind,a,n in out:
    if kind in ('FUNC','VAR'): print(f"{kind:4s} 0x{a:08x}  {n}" if a is not None else f"{kind:4s} ----------  {n}")
print('=== types/enums/members ===')
seen=set()
for kind,a,n in out:
    if kind in ('ENUM','CONST'):
        print(f"{kind:5s} {a:>12}  {n}")
