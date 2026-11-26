from elftools.elf.elffile import ELFFile
import re
p=r'D:\r36s-\analysis\rootfs_card2\lib\modules\4.4.186-release\extra\dsc.ko'
f=open(p,'rb'); e=ELFFile(f); dw=e.get_dwarf_info()
want=re.compile(r'(dsc|param|algo|sha|cmdq|key|iv|priv|residue|pid)',re.I)
def typename(die):
    a=die.attributes.get('DW_AT_type')
    return a
for cu in dw.iter_CUs():
    for die in cu.iter_DIEs():
        if die.tag not in ('DW_TAG_structure_type','DW_TAG_union_type','DW_TAG_typedef'): continue
        nm=die.attributes.get('DW_AT_name')
        nm=nm.value.decode() if nm else ''
        if not want.search(nm): continue
        sz=die.attributes.get('DW_AT_byte_size')
        print(f"{die.tag[8:]:14s} {nm:34s} size={sz.value if sz else '?'}")
        if die.tag=='DW_TAG_typedef': continue
        for ch in die.iter_children():
            if ch.tag!='DW_TAG_member': continue
            mn=ch.attributes.get('DW_AT_name'); mn=mn.value.decode() if mn else ''
            loc=ch.attributes.get('DW_AT_data_member_location')
            lv=loc.value if loc else 0
            ty=ch.attributes.get('DW_AT_type')
            tn=''
            if ty:
                try:
                    td=dw.get_DIE_from_refaddr(cu.cu_offset+ty.value if ty.form=='DW_FORM_ref4' else ty.value)
                    n2=td.attributes.get('DW_AT_name'); tn=n2.value.decode() if n2 else td.tag[8:]
                except Exception: tn='?'
            print(f"    +0x{lv:02x} {mn:28s} {tn}")
