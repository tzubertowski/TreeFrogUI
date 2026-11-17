"""MIPS static analysis helper for rkgame.decrypted (Capstone).
Loads the ELF, disassembles .text, resolves lui/addiu(hi/lo) data refs,
finds xrefs to a target address, and disassembles windows around them."""
import struct, sys
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN
from capstone.mips import MIPS_OP_IMM, MIPS_OP_REG, MIPS_OP_MEM

PATH = sys.argv[1] if len(sys.argv) > 1 else r'D:\r36s-\analysis\decrypted\rkgame.decrypted'
d = open(PATH, 'rb').read()
en = '<'
e_shoff, = struct.unpack(en+'I', d[32:36])
e_shentsize, = struct.unpack(en+'H', d[46:48])
e_shnum, = struct.unpack(en+'H', d[48:50])
e_shstrndx, = struct.unpack(en+'H', d[50:52])
secs = []
for i in range(e_shnum):
    o = e_shoff+i*e_shentsize
    name, typ, flags, addr, off, size, link, info, align, entsz = struct.unpack(en+'10I', d[o:o+40])
    secs.append(dict(name=name, typ=typ, addr=addr, off=off, size=size, entsz=entsz, link=link))
shstr = secs[e_shstrndx]['off']
def sname(n): return d[shstr+n:d.index(b'\0', shstr+n)].decode('latin1')
for s in secs: s['nm'] = sname(s['name'])
def sec(nm): return next(s for s in secs if s['nm'] == nm)

text = sec('.text')
TEXT_ADDR, TEXT_OFF, TEXT_SZ = text['addr'], text['off'], text['size']
code = d[TEXT_OFF:TEXT_OFF+TEXT_SZ]

# dynsym for import names
def load_dynsym():
    ds, dstr = sec('.dynsym'), sec('.dynstr')
    out = {}
    for i in range(ds['size']//16):
        o = ds['off']+i*16
        nameoff, value, size, info, other, shndx = struct.unpack(en+'IIIBBH', d[o:o+16])
        nm = d[dstr['off']+nameoff:d.index(b'\0', dstr['off']+nameoff)].decode('latin1')
        if nm: out[value] = nm
    return out
DYN = load_dynsym()

md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
md.detail = True

def va_to_off(va):
    for s in secs:
        if s['typ'] != 8 and s['addr'] <= va < s['addr']+s['size']:
            return s['off']+(va-s['addr'])
    return None

def cstr(va, maxlen=80):
    o = va_to_off(va)
    if o is None: return None
    e = d.find(b'\0', o, o+maxlen)
    if e < 0: e = o+maxlen
    return d[o:e].decode('latin1', 'replace')

def disasm_all():
    """yield (addr, insn)."""
    for insn in md.disasm(code, TEXT_ADDR):
        yield insn

def build_xrefs():
    """Resolve hi/lo pairs per register to data addresses; map target_addr -> [site_addr,...]."""
    xref = {}             # data_addr -> list of instruction addrs
    hi = {}               # reg -> (hi<<16, site_addr)
    callsites = {}        # target_addr -> [addr] for jal
    for insn in disasm_all():
        m = insn.mnemonic
        ops = insn.operands
        if m == 'lui' and len(ops) == 2 and ops[0].type == MIPS_OP_REG and ops[1].type == MIPS_OP_IMM:
            hi[ops[0].reg] = ((ops[1].imm & 0xffff) << 16, insn.address)
        elif m in ('addiu', 'ori', 'daddiu') and len(ops) == 3 and ops[1].type == MIPS_OP_REG and ops[1].reg in hi and ops[2].type == MIPS_OP_IMM:
            base, _ = hi[ops[1].reg]
            lo = ops[2].imm
            addr = (base + (lo if m == 'ori' else struct.unpack('<h', struct.pack('<H', lo & 0xffff))[0])) & 0xffffffff
            xref.setdefault(addr, []).append(insn.address)
        elif m in ('lw', 'sw', 'lb', 'sb', 'lbu', 'lhu') and len(ops) == 2 and ops[1].type == MIPS_OP_MEM:
            r = ops[1].mem.base
            if r in hi:
                base, _ = hi[r]
                addr = (base + ops[1].mem.disp) & 0xffffffff
                xref.setdefault(addr, []).append(insn.address)
        elif m in ('jal', 'jalx') and ops and ops[0].type == MIPS_OP_IMM:
            callsites.setdefault(ops[0].imm, []).append(insn.address)
        # invalidate hi on reg overwrite (rough)
        if ops and ops[0].type == MIPS_OP_REG and m not in ('lui',):
            hi.pop(ops[0].reg, None)
    return xref, callsites

if __name__ == '__main__':
    cmd = sys.argv[2] if len(sys.argv) > 2 else 'info'
    if cmd == 'info':
        print('sections:', [(s['nm'], hex(s['addr']), s['size']) for s in secs if s['nm'] in ('.text','.rodata','.data','.sdata')])
        print('imports (dynsym) sample:', list(DYN.values())[:30])
    elif cmd == 'xref':
        target = int(sys.argv[3], 16)
        xref, calls = build_xrefs()
        sites = xref.get(target, [])
        print(f'xrefs to {target:#x} ("{cstr(target)}"): {len(sites)} sites')
        for s in sites: print(f'  {s:#x}')
