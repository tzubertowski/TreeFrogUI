from elftools.elf.elffile import ELFFile
from elftools.dwarf.descriptions import describe_form_class
p=r'D:\r36s-\analysis\rootfs_card2\lib\modules\4.4.186-release\extra\dsc.ko'
e=ELFFile(open(p,'rb')); dw=e.get_dwarf_info()
out=[]
# CU names
for cu in dw.iter_CUs():
    top=cu.get_top_DIE()
    name=top.attributes.get('DW_AT_name')
    comp=top.attributes.get('DW_AT_comp_dir')
    out.append(f"CU {name.value if name else '?'}  [{comp.value if comp else ''}]")
    for die in cu.iter_DIEs():
        if die.tag not in ('DW_TAG_subprogram','DW_TAG_variable','DW_TAG_structure_type','DW_TAG_union_type','DW_TAG_enumeration_type','DW_TAG_typedef'): continue
        n=die.attributes.get('DW_AT_name')
        if not n: continue
        nm=n.value.decode() if isinstance(n.value,bytes) else str(n.value)
        if die.tag=='DW_TAG_subprogram':
            lo=die.attributes.get('DW_AT_low_pc'); hi=die.attributes.get('DW_AT_high_pc')
            if lo:
                out.append(f"FUNC {nm} pc=0x{lo.value:x} size=0x{hi.value:x}" if hi else f"FUNC {nm} pc=0x{lo.value:x}")
                for ch in die.iter_children():
                    if ch.tag in ('DW_TAG_variable','DW_TAG_formal_parameter'):
                        cn=ch.attributes.get('DW_AT_name')
                        if cn:
                            out.append(f"    var {cn.value.decode() if isinstance(cn.value,bytes) else cn.value}")
        else:
            out.append(f"{die.tag[9:]} {nm}")
open(r'D:\r36s-\analysis\dsc_dwarf.txt','w',encoding='utf-8').write('\n'.join(out))
print(len(out),'lines ->',r'D:\r36s-\analysis\dsc_dwarf.txt')
