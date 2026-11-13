#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Pavel Kotek
"""Static checks of build/tfshim.so against the real driver (needs pyelftools).

    python check_shim.py tfshim.so tfshim.dbg.so driver_sf3500.so [tfrec]

- tfshim.so and tfshim.dbg.so have byte-identical loadable segments
- ELF flags / FP ABI equal to the real driver (MIPS32r2 o32 PIC, hard float)
- DT_NEEDED only libc/libdl/libpthread, no RPATH/RUNPATH/TEXTREL, no DT_INIT/FINI
- every imported symbol is versioned and every version is GLIBC <= 2.20
- exported FUNC/OBJECT set (name, type, binding, object size) == real driver's
- each trampoline decodes to the expected 8 instructions, its gp equals _gp,
  it loads a *local* GOT page entry, and the slot it jumps through is
  tfshim_slots[i] where tfshim_slot_names[i] is the trampoline's own name;
  each slot starts as tfshim_missing_asm with a R_MIPS_REL32 relocation
- tfrec is a static MIPS executable (no interpreter, no dynamic section)
"""
import struct, sys
from elftools.elf.elffile import ELFFile

INTERCEPT = {'video_driver_disp_frame', 'sound_driver_playframe', 'sound_driver_init'}
ALLOWED_NEEDED = {'libc.so.6', 'libdl.so.2', 'libpthread.so.0'}
fails = []


def check(cond, msg):
    print(('ok   ' if cond else 'FAIL ') + msg)
    if not cond:
        fails.append(msg)


def dyn_tags(f):
    return [(t.entry.d_tag, t) for t in f.get_section_by_name('.dynamic').iter_tags()]


def exports(f):
    out = {}
    for s in f.get_section_by_name('.dynsym').iter_symbols():
        if s['st_shndx'] == 'SHN_UNDEF' or not s.name or s['st_info']['bind'] == 'STB_LOCAL':
            continue
        t = s['st_info']['type']
        if t in ('STT_FUNC', 'STT_OBJECT'):
            out[s.name] = (t, s['st_info']['bind'], s['st_size'] if t == 'STT_OBJECT' else None)
    return out


class Image:
    def __init__(self, f):
        self.segs = [(p['p_vaddr'], p['p_filesz'], p.data()) for p in f.iter_segments() if p['p_type'] == 'PT_LOAD']

    def read(self, addr, n):
        for va, sz, data in self.segs:
            if va <= addr and addr + n <= va + sz:
                return data[addr - va:addr - va + n]
        raise KeyError(hex(addr))

    def word(self, addr):
        return struct.unpack('<I', self.read(addr, 4))[0]

    def cstr(self, addr):
        out = b''
        while True:
            c = self.read(addr + len(out), 1)
            if c == b'\0':
                return out.decode()
            out += c


def sext16(v):
    return v - 0x10000 if v & 0x8000 else v


def main():
    shim_p, dbg_p, real_p = sys.argv[1:4]
    tfrec_p = sys.argv[4] if len(sys.argv) > 4 else None
    S, D, R = (ELFFile(open(p, 'rb')) for p in (shim_p, dbg_p, real_p))

    # identical code/data between the shipped and the symbolized build
    # (the 52-byte ELF header is mapped too; only its section-table fields may differ)
    def segs(f):
        return [(p['p_vaddr'], p['p_memsz'], p['p_flags'], p.data()[0x34:] if p['p_offset'] == 0 else p.data())
                for p in f.iter_segments() if p['p_type'] == 'PT_LOAD']
    ls, ld = segs(S), segs(D)
    check(ls == ld, 'tfshim.so and tfshim.dbg.so loadable bytes identical apart from the ELF header (%d PT_LOAD)' % len(ls))

    # default real-driver path compiled in (guards against MSYS path mangling)
    import os
    want = ('/mnt/sdcard/cubegm/' + os.path.basename(real_p)).encode() + b'\0'
    blob = open(shim_p, 'rb').read()
    check(want in blob and b'Program Files' not in blob, 'default real driver path %s' % want[:-1].decode())

    # ABI
    check(S['e_machine'] == 'EM_MIPS' and S['e_type'] == 'ET_DYN', 'ET_DYN EM_MIPS')
    check(S.header.e_flags == R.header.e_flags, 'e_flags 0x%08x == real 0x%08x' % (S.header.e_flags, R.header.e_flags))
    fa = [struct.unpack_from('<HBBBBBB', f.get_section_by_name('.MIPS.abiflags').data())[6] for f in (S, R)]
    check(fa[0] == fa[1], '.MIPS.abiflags fp_abi %d == real %d (hard-float double)' % tuple(fa))

    # dynamic section
    tags = dyn_tags(S)
    needed = [t.needed for k, t in tags if k == 'DT_NEEDED']
    check(set(needed) <= ALLOWED_NEEDED, 'DT_NEEDED %s' % needed)
    names = {k for k, _ in tags}
    check(not names & {'DT_RPATH', 'DT_RUNPATH', 'DT_TEXTREL'}, 'no RPATH/RUNPATH/TEXTREL')
    flags = [t.entry.d_val for k, t in tags if k == 'DT_FLAGS']
    check(not flags or not flags[0] & 4, 'no DF_TEXTREL')
    check('DT_INIT' not in names and 'DT_FINI' not in names, 'no DT_INIT/DT_FINI (the _init/_fini exports are plain trampolines)')
    check('DT_INIT_ARRAY' in names, 'constructor via DT_INIT_ARRAY')

    # symbol versions
    vers = []
    for v, aux in S.get_section_by_name('.gnu.version_r').iter_versions():
        for a in aux:
            vers.append((v.name, a.name))
    bad = [x for x in vers if not x[1].startswith('GLIBC_') or
           tuple(int(n) for n in x[1][6:].split('.')) > (2, 20)]
    check(not bad, 'version needs %s all <= GLIBC_2.20' % sorted({v for _, v in vers}, key=lambda s: [int(n) for n in s[6:].split('.')]))
    vs = S.get_section_by_name('.gnu.version')
    dsym = list(S.get_section_by_name('.dynsym').iter_symbols())
    unver = [s.name for i, s in enumerate(dsym) if i and s['st_shndx'] == 'SHN_UNDEF' and s.name
             and s['st_info']['bind'] != 'STB_WEAK' and vs.get_symbol(i)['ndx'] in ('VER_NDX_LOCAL', 'VER_NDX_GLOBAL', 0, 1)]
    check(not unver, 'every imported symbol carries a GLIBC version (unversioned: %s)' % unver)
    imports = sorted(s.name for s in dsym if s.name and s['st_shndx'] == 'SHN_UNDEF')
    print('     imports: ' + ' '.join(imports))

    # export set
    es, er = exports(S), exports(R)
    check(es == er, 'exported FUNC/OBJECT set identical to real driver (%d functions, %d objects)'
          % (sum(v[0] == 'STT_FUNC' for v in er.values()), sum(v[0] == 'STT_OBJECT' for v in er.values())))
    if es != er:
        print('     only in shim:', sorted(set(es) - set(er)), ' only in real:', sorted(set(er) - set(es)),
              ' differing:', sorted(k for k in set(es) & set(er) if es[k] != er[k]))
    extra = [s.name for s in dsym if s.name and s['st_shndx'] != 'SHN_UNDEF' and s['st_info']['bind'] != 'STB_LOCAL'
             and s.name not in er]
    check(not extra, 'no extra exported symbols %s' % extra)

    # trampolines
    img = Image(S)
    sym = {s.name: s for s in D.get_section_by_name('.symtab').iter_symbols() if s.name}
    slots, missing = sym['tfshim_slots']['st_value'], sym['tfshim_missing_asm']['st_value']
    names_arr, names_sz = sym['tfshim_slot_names']['st_value'], sym['tfshim_slot_names']['st_size']
    nslots = sym['tfshim_slots']['st_size'] // 4
    pltgot = [t.entry.d_val for k, t in tags if k == 'DT_PLTGOT'][0]
    local_gotno = [t.entry.d_val for k, t in tags if k == 'DT_MIPS_LOCAL_GOTNO'][0]
    rel32 = set()
    for sec in S.iter_sections():
        if sec['sh_type'] == 'SHT_REL':
            for r in sec.iter_relocations():
                if r['r_info_type'] == 3 and r['r_info_sym'] == 0:     # R_MIPS_REL32, relative
                    rel32.add(r['r_offset'])
    slot_names = []
    for i in range(names_sz // 4):
        a = names_arr + 4 * i
        check(a in rel32, 'tfshim_slot_names[%d] has R_MIPS_REL32' % i) if a not in rel32 else None
        slot_names.append(img.cstr(img.word(a)))
    check(len(slot_names) == nslots, 'slot name table size %d == slots %d' % (len(slot_names), nslots))
    bad_init = [i for i in range(nslots) if img.word(slots + 4 * i) != missing or slots + 4 * i not in rel32]
    check(not bad_init, 'all %d slots start as tfshim_missing_asm with R_MIPS_REL32' % nslots)

    used, problems = {}, []
    for name, (typ, bind, _) in sorted(es.items()):
        if typ != 'STT_FUNC' or name in INTERCEPT:
            continue
        s = next(x for x in dsym if x.name == name)
        a = s['st_value']
        w = struct.unpack('<8I', img.read(a, 32))
        op = [x >> 26 for x in w]
        rs = [(x >> 21) & 31 for x in w]
        rt = [(x >> 16) & 31 for x in w]
        imm = [x & 0xFFFF for x in w]
        ok = (s['st_size'] == 32 and
              op[0] == 0x0F and rt[0] == 28 and                                   # lui   gp, %hi(_gp_disp)
              op[1] == 0x09 and rs[1] == 28 and rt[1] == 28 and                   # addiu gp, gp, %lo
              op[2] == 0 and (w[2] & 0x3F) == 0x21 and ((w[2] >> 11) & 31) == 28 and
              {rs[2], rt[2]} == {28, 25} and                                      # addu  gp, gp, t9
              op[3] == 0x23 and rs[3] == 28 and rt[3] == 25 and                   # lw    t9, %got(slots)(gp)
              op[4] == 0x09 and rs[4] == 25 and rt[4] == 25 and                   # addiu t9, t9, %lo(slots)
              op[5] == 0x23 and rs[5] == 25 and rt[5] == 25 and                   # lw    t9, 4*i(t9)
              op[6] == 0 and rs[6] == 25 and ((w[6] & 0x3F) == 0x08 or            # jr    t9
                                             ((w[6] & 0x3F) == 0x09 and ((w[6] >> 11) & 31) == 0)) and
              op[7] == 0x09 and rs[7] == 0 and rt[7] == 24)                       # addiu t8, zero, i
        if not ok:
            problems.append('%s: unexpected instruction pattern %s' % (name, ' '.join('%08x' % x for x in w)))
            continue
        gp = (a + (imm[0] << 16) + sext16(imm[1])) & 0xFFFFFFFF
        got_addr = (gp + sext16(imm[3])) & 0xFFFFFFFF
        gi = (got_addr - pltgot) // 4
        slot = (img.word(got_addr) + sext16(imm[4]) + sext16(imm[5])) & 0xFFFFFFFF
        idx = imm[7]
        if gp != pltgot + 0x7FF0:
            problems.append('%s: gp 0x%x != _gp 0x%x' % (name, gp, pltgot + 0x7FF0))
        elif not 2 <= gi < local_gotno:
            problems.append('%s: GOT index %d is not a local entry' % (name, gi))
        elif slot != slots + 4 * idx or idx >= nslots:
            problems.append('%s: jumps through 0x%x, expected slot %d at 0x%x' % (name, slot, idx, slots + 4 * idx))
        elif slot_names[idx] != name:
            problems.append('%s: slot %d is resolved as %r' % (name, idx, slot_names[idx]))
        elif idx in used:
            problems.append('%s: slot %d shared with %s' % (name, idx, used[idx]))
        else:
            used[idx] = name
    for p in problems[:10]:
        print('     ' + p)
    check(not problems and len(used) == nslots,
          '%d trampolines: exact 8-insn pattern, gp=_gp, local GOT page entry, slot i <-> own name' % len(used))
    for name in sorted(INTERCEPT):
        check(es.get(name, (None,))[0] == 'STT_FUNC', 'C wrapper exported: %s' % name)

    if tfrec_p:
        T = ELFFile(open(tfrec_p, 'rb'))
        pt = {p['p_type'] for p in T.iter_segments()}
        check(T['e_machine'] == 'EM_MIPS' and T['e_type'] == 'ET_EXEC' and 'PT_INTERP' not in pt
              and 'PT_DYNAMIC' not in pt, 'tfrec: static MIPS executable, e_flags 0x%08x' % T.header.e_flags)

    print('\n%s' % ('ALL CHECKS PASSED' if not fails else '%d FAILED' % len(fails)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
