from elftools.elf.elffile import ELFFile
p=r'D:\r36s-\analysis\rootfs_card2\lib\modules\4.4.186-release\extra\dsc.ko'
e=ELFFile(open(p,'rb')); dw=e.get_dwarf_info()
def nm(d):
    a=d.attributes.get('DW_AT_name')
    return (a.value.decode() if isinstance(a.value,bytes) else str(a.value)) if a else None
byoff={}
cus=list(dw.iter_CUs())
for cu in cus:
    try:
        for d in cu.iter_DIEs(): byoff[d.offset]=d
    except Exception: pass
def tname(die,seen=None):
    seen=seen or set()
    r=die.attributes.get('DW_AT_type')
    if not r: return 'void'
    t=byoff.get(r.value)
    if t is None or t.offset in seen: return '?'
    seen.add(t.offset)
    n=nm(t)
    if t.tag=='DW_TAG_pointer_type': return tname(t,seen)+'*'
    if t.tag=='DW_TAG_typedef' and n: return n
    if t.tag=='DW_TAG_const_type': return 'const '+tname(t,seen)
    return n or (t.tag[9:] if t.tag else '?')
lines=[]
for cu in cus:
    for die in cu.iter_DIEs():
        if die.tag=='DW_TAG_enumeration_type':
            n=nm(die); mem=[]
            for ch in die.iter_children():
                if ch.tag=='DW_TAG_enumerator':
                    v=ch.attributes.get('DW_AT_const_value')
                    mem.append(f"{nm(ch)}={v.value if v else '?'}")
            if n: lines.append(f"ENUM {n} {{{', '.join(mem)}}}")
        elif die.tag in ('DW_TAG_structure_type','DW_TAG_union_type'):
            n=nm(die)
            if not n: continue
            mem=[]
            for ch in die.iter_children():
                if ch.tag=='DW_TAG_member':
                    loc=ch.attributes.get('DW_AT_data_member_location')
                    mem.append(f"+0x{(loc.value if loc else 0):x}:{nm(ch)}:{tname(ch)}")
            sz=die.attributes.get('DW_AT_byte_size')
            lines.append(f"{die.tag[9:]} {n} size={sz.value if sz else '?'} [{' | '.join(mem)}]")
        elif die.tag=='DW_TAG_subprogram':
            lo=die.attributes.get('DW_AT_low_pc')
            if not lo: continue
            vs=[]
            for ch in die.iter_children():
                if ch.tag in ('DW_TAG_variable','DW_TAG_formal_parameter'):
                    cn=nm(ch)
                    if cn: vs.append(f"{cn}:{tname(ch)}")
            lines.append(f"FUNC 0x{lo.value:x} {nm(die)}({', '.join(vs)})")
open(r'D:\r36s-\analysis\dsc_types.txt','w',encoding='utf-8').write('\n'.join(lines))
print('wrote',len(lines))
