#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Pavel Kotek
"""Run the real MIPS tfshim.so under Unicorn (MIPS32 74Kf) with a tiny loader.

    python emu_shim.py build/tfshim.so build/tfshim.dbg.so

The loader maps the PT_LOAD segments, applies R_MIPS_REL32 relocations and the
MIPS GOT (local entries + base, global entries -> symbols), and replaces every
glibc import by a Python stub. A fake "real driver" answers dlsym() with one
hook address per exported name. Scenarios:

  A constructor: dlopen(real, RTLD_NOW|RTLD_LOCAL), slots resolved by name,
    data objects re-pointed (.dynsym st_value) with mprotect RW and restore
  B every trampoline: a0-a3, 4 stack args, sp, ra, s0-s8 and $f12/$f14 reach
    the right real function unchanged, its v0 comes back, 8 instructions
  C an unresolved function returns 0 and is logged once
  D wrappers while detached: exact forwarding, fast-path instruction count,
    one open(TFCAP_PATH) per 64 hooked calls
  E attach to a recorder segment: frames (incl. padded pitch) and audio land
    bit-exact in the shm, fps cap, sample rate from sound_driver_init
  F state=CLOSED -> munmap; stale heartbeat -> munmap and no re-attach to the
    same inode
  G real driver missing -> no crash, calls return 0
  H TFSHIM_REAL pointing at the shim itself -> refused
"""
import os, random, re, struct, sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE, UC_HOOK_BLOCK, UcError
from unicorn.mips_const import *

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

BASE, STUB, REAL, RDATA, DATA, HEAP, SHM = 0x40000000, 0x60000000, 0x61000000, 0x61800000, 0x62000000, 0x63000000, 0x50000000
STACK_TOP, MAGIC = 0x7f100000, 0x7ff00000
SHIM_PATH, REAL_PATH, CAP_PATH = '/fake/tfshim.so', '/fake/driver_sf3500.so', '/dev/shm/tfcap'
INTERCEPT = ('video_driver_disp_frame', 'sound_driver_playframe', 'sound_driver_init')
REG_A = [UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3]
REG_S = [UC_MIPS_REG_S0, UC_MIPS_REG_S1, UC_MIPS_REG_S2, UC_MIPS_REG_S3, UC_MIPS_REG_S4, UC_MIPS_REG_S5,
         UC_MIPS_REG_S6, UC_MIPS_REG_S7, UC_MIPS_REG_S8]

fails = []


def check(cond, msg):
    print(('ok   ' if cond else 'FAIL ') + msg)
    if not cond:
        fails.append(msg)


# ---- tfcap layout (mirror of tfcap.h) ------------------------------------
HDR = 4096
VMAX = 640 * 480 * 2
POLL = int(re.search(r'#define TFSHIM_POLL_CALLS\s+(\d+)', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tfshim.c')).read()).group(1))
STRIDE = (64 + VMAX + 4095) & ~4095
NDESC, RING, AMAX = 256, 512 * 1024, 64 * 1024
DESC_OFF = HDR + 3 * STRIDE
RING_OFF = DESC_OFF + ((NDESC * 32 + 4095) & ~4095)
TOTAL = RING_OFF + RING
H = dict(magic=0, version=4, hdr_bytes=8, total=12, enabled=16, heartbeat=20, v_min=24, state=28, shim_pid=32,
         attaches=36, vseq=40, v_nslots=44, v_slot_off=48, v_slot_stride=52, v_max=56, v_too_big=60, a_cidx=64,
         a_wpos=68, a_ring_off=72, a_ring_bytes=76, a_desc_off=80, a_ndesc=84, a_rate=88, a_channels=92,
         a_bad_len=96, v_calls=100, a_calls=104)


class Emu:
    def __init__(self, shim, dbg, env=None, real_ok=True, missing=('hcge_ge_coeff',), same_inode=False, quiet=False):
        self.f = ELFFile(open(shim, 'rb'))
        st = ELFFile(open(dbg, 'rb')).get_section_by_name('.symtab')
        self.dbgsym = {s.name: s['st_value'] for s in st.iter_symbols() if s.name} if st else {}
        self.env = env or {'TFSHIM_REAL': REAL_PATH}
        self.real_ok, self.missing, self.same_inode, self.quiet = real_ok, set(missing), same_inode, quiet
        self.log, self.calls, self.real_calls = [], [], []
        self.clock_ns = 1000 * 10 ** 9
        self.shm_present, self.shm_ino, self.errno = False, 1, 0
        self.uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 + UC_MODE_LITTLE_ENDIAN)
        self.uc.ctl_set_cpu_model(UC_CPU_MIPS32_74KF)
        self.heap = HEAP
        for a, sz in ((STUB, 0x10000), (REAL, 0x10000), (RDATA, 0x10000), (DATA, 0x10000), (HEAP, 0x400000),
                      (SHM, (TOTAL + 0xFFFF) & ~0xFFFF), (STACK_TOP - 0x100000, 0x100000), (MAGIC, 0x1000)):
            self.uc.mem_map(a, sz)
        self.data = DATA
        self.load()
        self.uc.hook_add(UC_HOOK_CODE, self.on_stub, begin=STUB, end=STUB + 0xFFFF)
        self.uc.hook_add(UC_HOOK_CODE, self.on_real, begin=REAL, end=REAL + 0xFFFF)
        self.uc.hook_add(UC_HOOK_BLOCK, self.on_block)
        self.icount = 0

    # ---- loading ----
    def load(self):
        f, uc = self.f, self.uc
        for p in f.iter_segments():
            if p['p_type'] != 'PT_LOAD':
                continue
            lo = (BASE + p['p_vaddr']) & ~0xFFF
            hi = (BASE + p['p_vaddr'] + p['p_memsz'] + 0xFFF) & ~0xFFF
            try:
                uc.mem_map(lo, hi - lo)
            except UcError:
                pass
            uc.mem_write(BASE + p['p_vaddr'], p.data())
        self.phoff, self.phnum = f['e_phoff'], f['e_phnum']
        self.dyn = {t.entry.d_tag: t.entry.d_val for t in f.get_section_by_name('.dynamic').iter_tags()}
        self.dynvaddr = f.get_section_by_name('.dynamic')['sh_addr']
        self.syms = list(f.get_section_by_name('.dynsym').iter_symbols())
        self.symaddr = {}
        self.stubs, self.stubnames = {}, {}
        for i, s in enumerate(self.syms):
            if not s.name:
                continue
            if s['st_shndx'] == 'SHN_UNDEF':
                if s['st_info']['type'] == 'STT_OBJECT' or s.name == 'stderr':
                    a = self.alloc_data(4); self.w32(a, 0x0BADF11E)   # FILE *stderr
                else:
                    a = STUB + 16 * len(self.stubs)
                    uc.mem_write(a, struct.pack('<II', 0x03E00008, 0))   # jr ra; nop
                    self.stubnames[a] = s.name
                self.stubs[s.name] = a
                self.symaddr[i] = a
            else:
                self.symaddr[i] = BASE + s['st_value']
        for sec in f.iter_sections():
            if sec['sh_type'] != 'SHT_REL':
                continue
            for r in sec.iter_relocations():
                t, si, off = r['r_info_type'], r['r_info_sym'], BASE + r['r_offset']
                if t == 0:
                    continue
                assert t == 3, 'unexpected relocation type %d' % t      # R_MIPS_REL32
                v = self.r32(off)
                self.w32(off, (v + (BASE if si == 0 else self.symaddr[si])) & 0xFFFFFFFF)
        got, lg = BASE + self.dyn['DT_PLTGOT'], self.dyn['DT_MIPS_LOCAL_GOTNO']
        self.w32(got, 0); self.w32(got + 4, 0)
        for i in range(2, lg):
            self.w32(got + 4 * i, (self.r32(got + 4 * i) + BASE) & 0xFFFFFFFF)
        gs, n = self.dyn['DT_MIPS_GOTSYM'], self.dyn['DT_MIPS_SYMTABNO']
        for k, i in enumerate(range(gs, n)):
            self.w32(got + 4 * (lg + k), self.symaddr[i])
        self.exports = {s.name: BASE + s['st_value'] for s in self.syms
                        if s.name and s['st_shndx'] != 'SHN_UNDEF' and s['st_info']['type'] == 'STT_FUNC'}
        self.objs = {s.name: (i, s['st_size']) for i, s in enumerate(self.syms)
                     if s.name and s['st_shndx'] != 'SHN_UNDEF' and s['st_info']['type'] == 'STT_OBJECT'}
        # fake real driver: one hook address per function name, data in RDATA
        self.realfn = {n: REAL + 16 * k for k, n in enumerate(sorted(self.exports))}
        for a in self.realfn.values():
            uc.mem_write(a, struct.pack('<II', 0x03E00008, 0))
        self.realname = {a: n for n, a in self.realfn.items()}
        self.realobj = {n: RDATA + 0x100 * k for k, n in enumerate(sorted(self.objs))}
        self.real_ret = {}

    # ---- memory helpers ----
    def r32(self, a): return struct.unpack('<I', self.uc.mem_read(a, 4))[0]
    def w32(self, a, v): self.uc.mem_write(a, struct.pack('<I', v & 0xFFFFFFFF))
    def reg(self, r): return self.uc.reg_read(r)

    def cstr(self, a):
        out = bytearray()
        while True:
            c = self.uc.mem_read(a + len(out), 64)
            z = c.find(b'\0')
            if z >= 0:
                return (out + c[:z]).decode('latin-1')
            out += c

    def alloc_data(self, n):
        a = self.data; self.data += (n + 7) & ~7; return a

    def str_data(self, s):
        b = s.encode() + b'\0'; a = self.alloc_data(len(b)); self.uc.mem_write(a, b); return a

    def alloc(self, data):
        a = self.heap; self.heap += (len(data) + 15) & ~15
        self.uc.mem_write(a, bytes(data)); return a

    # ---- hooks ----
    def on_block(self, uc, addr, size, ud):
        self.icount += size // 4

    def stack_arg(self, k):
        return self.r32(self.reg(UC_MIPS_REG_SP) + 16 + 4 * k)

    def fmt(self, f, argi):
        out, i = '', 0
        def nxt():
            nonlocal argi
            v = self.reg(REG_A[argi]) if argi < 4 else self.stack_arg(argi - 4)
            argi += 1
            return v
        while i < len(f):
            c = f[i]
            if c != '%':
                out += c; i += 1; continue
            j = i + 1
            while f[j] in '-0123456789.lz':
                j += 1
            t = f[j]
            if t == 's': out += self.cstr(nxt())
            elif t in 'du': v = nxt(); out += str(v - (1 << 32) if t == 'd' and v & 0x80000000 else v)
            elif t in 'xp': out += hex(nxt())
            elif t == '%': out += '%'
            i = j + 1
        return out

    def on_stub(self, uc, addr, size, ud):
        name = self.stubnames.get(addr)
        if name is None:
            return
        a = [self.reg(r) for r in REG_A]
        self.calls.append((name, a))
        ret = 0
        if name == 'getenv':
            v = self.env.get(self.cstr(a[0])); ret = self.str_data(v) if v is not None else 0
        elif name == 'fopen':
            ret = 0
        elif name == 'strlen':
            ret = len(self.cstr(a[0]))
        elif name == 'strcpy':
            uc.mem_write(a[0], self.cstr(a[1]).encode() + b'\0'); ret = a[0]
        elif name == 'strcmp':
            x, y = self.cstr(a[0]), self.cstr(a[1]); ret = (x > y) - (x < y)
        elif name == 'memcpy':
            uc.mem_write(a[0], bytes(uc.mem_read(a[1], a[2]))); ret = a[0]
        elif name == 'dladdr':
            if BASE <= a[0] < BASE + 0x100000:
                fn, fb = self.str_data(SHIM_PATH), BASE
            elif REAL <= a[0] < REAL + 0x20000 or RDATA <= a[0] < RDATA + 0x10000:
                fn, fb = self.str_data(REAL_PATH), REAL
            else:
                fn = fb = 0
            uc.mem_write(a[1], struct.pack('<IIII', fn, fb, 0, 0)); ret = 1 if fb else 0
        elif name == '__xstat':
            p = self.cstr(a[1])
            ino = 77 if (self.same_inode or p == SHIM_PATH) else 99
            uc.mem_write(a[2], struct.pack('<I', 1) + b'\0' * 12 + struct.pack('<I', ino)); ret = 0
        elif name == 'dlopen':
            p = self.cstr(a[0]) if a[0] else ''
            self.log.append('dlopen(%s, 0x%x)' % (p, a[1]))
            if p == REAL_PATH and self.real_ok and not a[1] & 8:
                ret = 0x1000
            elif p == SHIM_PATH and a[1] & 8:
                ret = 0x2000
        elif name == 'dlerror':
            ret = self.str_data('fake: no such file')
        elif name == 'dlsym':
            n = self.cstr(a[1])
            if a[0] == 0x1000 and n not in self.missing:
                ret = self.realfn.get(n) or self.realobj.get(n, 0)
        elif name == 'dlinfo':
            lm = self.alloc_data(20)
            uc.mem_write(lm, struct.pack('<IIIII', BASE, self.str_data(SHIM_PATH), BASE + self.dynvaddr, 0, 0))
            self.w32(a[2], lm); ret = 0
        elif name == 'dl_iterate_phdr':        # one object: tail-call the callback
            info = self.alloc_data(16)
            uc.mem_write(info, struct.pack('<IIIH', BASE, self.str_data(SHIM_PATH), BASE + self.phoff, self.phnum))
            uc.reg_write(UC_MIPS_REG_A0, info); uc.reg_write(UC_MIPS_REG_A1, 16); uc.reg_write(UC_MIPS_REG_A2, a[1])
            uc.reg_write(UC_MIPS_REG_T9, a[0]); uc.reg_write(UC_MIPS_REG_PC, a[0])
            return
        elif name == 'sysconf':
            ret = 4096
        elif name == 'mprotect':
            self.log.append('mprotect(0x%x, 0x%x, %d)' % (a[0], a[1], a[2]))
        elif name == '__errno_location':
            ret = self.alloc_data(4) if not hasattr(self, 'errno_cell') else self.errno_cell
            self.errno_cell = ret
        elif name == 'strerror':
            ret = self.str_data('error')
        elif name == 'fprintf':
            line = self.fmt(self.cstr(a[1]), 2)
            self.log.append(line)
            if not self.quiet:
                print('     [shim] ' + line.rstrip())
        elif name == 'fputc':
            ret = a[0]
        elif name == 'clock_gettime':
            uc.mem_write(a[1], struct.pack('<II', self.clock_ns // 10 ** 9, self.clock_ns % 10 ** 9))
        elif name == 'open':
            p = self.cstr(a[0])
            self.log.append('open(%s)' % p)
            if p == CAP_PATH and self.shm_present:
                ret = 7
            else:
                ret = 0xFFFFFFFF
        elif name == '__fxstat':
            st = bytearray(144)
            struct.pack_into('<I', st, 0, 0x16); struct.pack_into('<I', st, 16, self.shm_ino)
            struct.pack_into('<I', st, 20, 0o100666); struct.pack_into('<I', st, 48, TOTAL)
            uc.mem_write(a[2], bytes(st)); ret = 0
        elif name == 'mmap':
            fd, off = self.stack_arg(0), self.stack_arg(1)
            self.log.append('mmap(len=%d prot=%d flags=%d fd=%d off=%d)' % (a[1], a[2], a[3], fd, off))
            ret = SHM if (a[1] == TOTAL and a[2] == 3 and a[3] == 1 and fd == 7 and off == 0) else 0xFFFFFFFF
        elif name == 'munmap':
            self.log.append('munmap(0x%x, %d)' % (a[0], a[1]))
        elif name == 'getpid':
            ret = 4242
        elif name in ('close', 'sched_yield', 'dlclose', 'fclose', 'fgets'):
            ret = 0
        else:
            raise RuntimeError('unhandled import ' + name)
        uc.reg_write(UC_MIPS_REG_V0, ret & 0xFFFFFFFF)

    def on_real(self, uc, addr, size, ud):
        name = self.realname.get(addr)
        if name is None:
            return
        sp = self.reg(UC_MIPS_REG_SP)
        self.real_calls.append(dict(name=name, a=[self.reg(r) for r in REG_A], sp=sp, ra=self.reg(UC_MIPS_REG_RA),
                                    stack=[self.r32(sp + 16 + 4 * k) for k in range(4)],
                                    s=[self.reg(r) for r in REG_S],
                                    f=(self.reg(UC_MIPS_REG_F12), self.reg(UC_MIPS_REG_F14))))
        uc.reg_write(UC_MIPS_REG_V0, self.real_ret.get(name, 0x5EA10000 | (addr >> 4 & 0xFFF)))

    # ---- calling ----
    def call(self, addr, args=(), stack=(), sregs=None, fregs=None):
        uc = self.uc
        sp = STACK_TOP - 0x1000
        for k, v in enumerate(stack):
            self.w32(sp + 16 + 4 * k, v)
        for k in range(4):
            uc.reg_write(REG_A[k], args[k] if k < len(args) else 0)
        for k, r in enumerate(REG_S):
            uc.reg_write(r, sregs[k] if sregs else 0x5A5A0000 + k)
        if fregs:
            uc.reg_write(UC_MIPS_REG_F12, fregs[0]); uc.reg_write(UC_MIPS_REG_F14, fregs[1])
        uc.reg_write(UC_MIPS_REG_SP, sp); uc.reg_write(UC_MIPS_REG_RA, MAGIC)
        uc.reg_write(UC_MIPS_REG_T9, addr); uc.reg_write(UC_MIPS_REG_GP, 0xDEAD0000)
        self.icount = 0
        uc.emu_start(addr, MAGIC, count=50_000_000)
        assert self.reg(UC_MIPS_REG_PC) == MAGIC, 'did not return'
        return self.reg(UC_MIPS_REG_V0)

    def run_ctor(self):
        ia = self.dyn['DT_INIT_ARRAY']
        for k in range(self.dyn['DT_INIT_ARRAYSZ'] // 4):
            self.call(self.r32(BASE + ia + 4 * k))

    # ---- shm (recorder side) ----
    def shm_init(self, enabled=3, fps=30):
        self.uc.mem_write(SHM, b'\0' * TOTAL)
        hv = dict(version=1, hdr_bytes=HDR, total=TOTAL, v_nslots=3, v_slot_off=HDR, v_slot_stride=STRIDE,
                  v_max=VMAX, a_desc_off=DESC_OFF, a_ndesc=NDESC, a_ring_off=RING_OFF, a_ring_bytes=RING,
                  v_min=1000000 // fps if fps else 0, state=1, magic=0x31504354, enabled=enabled)
        for k, v in hv.items():
            self.w32(SHM + H[k], v)

    def h(self, k): return self.r32(SHM + H[k])


def main():
    shim, dbg = sys.argv[1], sys.argv[2]
    rnd = random.Random(1)

    print('[A] constructor')
    e = Emu(shim, dbg)
    e.run_ctor()
    check(any(l.startswith('dlopen(%s, 0x2)' % REAL_PATH) for l in e.log), 'dlopen(real, RTLD_NOW|RTLD_LOCAL) (MIPS RTLD_NOW=2)')
    slots = BASE + e.dbgsym['tfshim_slots']
    missing_asm = BASE + e.dbgsym['tfshim_missing_asm']
    from gen_tramp import INTERCEPT as GI
    names = sorted(n for n in e.exports if n not in GI)
    got = [e.r32(slots + 4 * i) for i in range(len(names))]
    want = [missing_asm if n in e.missing else e.realfn[n] for n in names]
    check(got == want, '%d slots resolved to the real function of the same name (%s left unresolved on purpose)'
          % (len(names), ','.join(sorted(e.missing))))
    ok_objs = all((BASE + e.r32(BASE + e.f.get_section_by_name('.dynsym')['sh_addr'] + 16 * i + 4)) & 0xFFFFFFFF
                  == e.realobj[n] for n, (i, _) in e.objs.items())
    check(ok_objs, '%d data objects: .dynsym st_value re-pointed to the real objects (dlsym returns real address)' % len(e.objs))
    mp = [l for l in e.log if l.startswith('mprotect')]
    check(len(mp) == 2 * len(e.objs) and all(l.endswith(', 3)') for l in mp[0::2]) and all(l.endswith(', 1)') for l in mp[1::2]),
          'mprotect RW then back to R for each patch (%d calls)' % len(mp))
    nf = len(e.exports)
    summ = '%d/%d functions, %d/%d data objects aliased' % (nf - len(e.missing), nf, len(e.objs), len(e.objs))
    check(any(summ in l for l in e.log), 'load summary logged (%s)' % summ)

    print('[B] trampolines')
    bad, counts = [], set()
    for n in sorted(e.exports):
        if n in INTERCEPT or n in e.missing:
            continue
        args = [rnd.getrandbits(32) for _ in range(4)]
        stack = [rnd.getrandbits(32) for _ in range(4)]
        sregs = [rnd.getrandbits(32) for _ in range(9)]
        fr = (rnd.getrandbits(32), rnd.getrandbits(32))
        e.real_ret[n] = rnd.getrandbits(32)
        e.real_calls.clear()
        v0 = e.call(e.exports[n], args, stack, sregs, fr)
        rc = e.real_calls
        if (len(rc) != 1 or rc[0]['name'] != n or rc[0]['a'] != args or rc[0]['stack'] != stack or rc[0]['s'] != sregs
                or rc[0]['ra'] != MAGIC or rc[0]['sp'] != STACK_TOP - 0x1000 or rc[0]['f'] != fr or v0 != e.real_ret[n]):
            bad.append(n)
        counts.add(e.icount - 2)                  # minus the fake callee's jr ra; nop
    check(not bad, '%d trampolines reach the right real function with a0-a3, stack args, sp, ra, s0-s8, '
          '$f12/$f14 intact and pass v0 back %s' % (len(e.exports) - len(INTERCEPT) - len(e.missing), bad[:5]))
    check(counts == {8}, 'trampoline cost: %s instructions' % sorted(counts))

    print('[C] unresolved function')
    e.log.clear()
    v1 = e.call(e.exports['hcge_ge_coeff'], [1, 2, 3, 4]); v2 = e.call(e.exports['hcge_ge_coeff'])
    check(v1 == 0 and v2 == 0 and sum('hcge_ge_coeff' in l for l in e.log) == 1, 'returns 0, logged once')

    print('[D] wrappers, no recorder')
    e.log.clear()
    bad, cost = [], []
    for k in range(130):
        n = INTERCEPT[k % 2]
        args = [rnd.getrandbits(32) for _ in range(4)]
        e.real_ret[n] = rnd.getrandbits(32)
        e.real_calls.clear()
        stack = [rnd.getrandbits(32) for _ in range(4)]
        v0 = e.call(e.exports[n], args, stack)
        rc = e.real_calls
        if (len(rc) != 1 or rc[0]['name'] != n or rc[0]['a'] != args or v0 != e.real_ret[n] or rc[0]['ra'] != MAGIC
                or rc[0]['sp'] != STACK_TOP - 0x1000 or rc[0]['stack'] != stack):
            bad.append((k, n))
        cost.append(e.icount - 2)
    opens = [l for l in e.log if l.startswith('open(')]
    check(not bad, '130 calls of disp_frame/playframe: tail jump to the driver with a0-a3, sp, ra and stack '
          'args unchanged, real v0 returned')
    check(opens == ['open(%s)' % CAP_PATH] * (130 // POLL), 'one open(%s) per %d hooked calls (%d opens)' % (CAP_PATH, POLL, len(opens)))
    fast = min(cost)
    print('     detached fast path: %d instructions from entry to the jump into the driver '
          '(every %dth call polls: %d)' % (fast, POLL, max(cost)))
    e.real_calls.clear()
    v = e.call(e.exports['sound_driver_init'], [0, 48000, 2, 0x1234])
    check(e.real_calls[0]['a'] == [0, 48000, 2, 0x1234], 'sound_driver_init forwards (dev, 48000, 2, a3)')

    print('[E] attach + capture')
    e.shm_init(fps=30)
    e.shm_present = True
    e.log.clear()
    W, Hh, P = 640, 480, 1280
    frames = [bytes(rnd.getrandbits(8) for _ in range(64)) * (W * Hh * 2 // 64) for _ in range(2)]
    fr_addr = [e.alloc(f) for f in frames]
    k = 0
    while e.h('attaches') == 0 and k < 70:
        e.call(e.exports['video_driver_disp_frame'], [fr_addr[0], W, Hh, P]); k += 1
        e.clock_ns += 16_666_667
    check(e.h('attaches') == 1 and e.h('shim_pid') == 4242, 'attached after %d calls (pid %d)' % (k, e.h('shim_pid')))
    check(e.h('a_rate') == 48000 and e.h('a_channels') == 2, 'rate/channels from sound_driver_init published')
    stored = []
    for i in range(8):
        e.w32(SHM + H['heartbeat'], e.h('heartbeat') + 1)
        before = e.h('vseq')
        e.real_calls.clear()
        e.call(e.exports['video_driver_disp_frame'], [fr_addr[i & 1], W, Hh, P])
        if e.h('vseq') != before:
            seq = e.h('vseq')
            slot = SHM + HDR + (seq % 3) * STRIDE
            sb, se, w, h, nb, pitch, tlo, thi = struct.unpack('<8I', e.uc.mem_read(slot, 32))
            data = bytes(e.uc.mem_read(slot + 64, nb))
            stored.append((i, seq, sb == se == seq and (w, h, nb, pitch) == (W, Hh, W * Hh * 2, P) and data == frames[i & 1]
                           and (thi << 32 | tlo) == e.clock_ns, e.icount))
        e.clock_ns += 16_666_667
    check(len(stored) == 4 and all(s[2] for s in stored), '60 Hz frames, 30 fps cap: %d of 8 stored, slots bit-exact '
          'with seq/size/pitch/timestamp' % len(stored))
    print('     capture cost per stored 640x480 frame: ~%d instructions (incl. memcpy stub)' % stored[0][3])
    # padded pitch
    small = bytes(rnd.getrandbits(8) for _ in range(704 * 240))
    sa = e.alloc(small)
    e.clock_ns += 40_000_000
    e.w32(SHM + H['heartbeat'], e.h('heartbeat') + 1)
    e.call(e.exports['video_driver_disp_frame'], [sa, 320, 240, 704])
    seq = e.h('vseq'); slot = SHM + HDR + (seq % 3) * STRIDE
    packed = b''.join(small[y * 704:y * 704 + 640] for y in range(240))
    check(bytes(e.uc.mem_read(slot + 64, 320 * 240 * 2)) == packed and e.r32(slot + 8) == 320,
          '320x240 frame with pitch 704 stored row-packed')
    # audio
    pcm = [bytes(rnd.getrandbits(8) for _ in range(1920)) for _ in range(5)]
    for i, p in enumerate(pcm):
        e.real_calls.clear()
        a = e.alloc(p)
        e.call(e.exports['sound_driver_playframe'], [a, 480, 0, 0])
        check(e.real_calls[0]['a'][:2] == [a, 480], 'playframe forwarded') if i == 0 else None
    ok = e.h('a_cidx') == 5 and e.h('a_wpos') == 5 * 1920
    ok = ok and bytes(e.uc.mem_read(SHM + RING_OFF, 5 * 1920)) == b''.join(pcm)
    d = struct.unpack('<6I', e.uc.mem_read(SHM + DESC_OFF + 32 * 4, 24))
    ok = ok and d[0] == d[1] == 4 and d[2] == 4 * 1920 and d[3] == 1920
    check(ok, '5 audio chunks (480 frames) in the ring with descriptors, bit-exact')
    e.call(e.exports['sound_driver_playframe'], [a, 100000, 0, 0])
    check(e.h('a_bad_len') == 1 and e.h('a_cidx') == 5, 'implausible frame count rejected (a_bad_len)')

    print('[F] detach')
    e.log.clear()
    e.w32(SHM + H['state'], 2)
    e.call(e.exports['video_driver_disp_frame'], [fr_addr[0], W, Hh, P])
    check(['munmap(0x%x, %d)' % (SHM, TOTAL)] == [l for l in e.log if l.startswith('munmap')], 'state CLOSED -> munmap')
    v = e.h('vseq'); e.clock_ns += 50_000_000
    e.call(e.exports['video_driver_disp_frame'], [fr_addr[0], W, Hh, P])
    check(e.h('vseq') == v, 'no capture after detach')
    # stale heartbeat
    e.shm_init(fps=0); e.shm_ino = 2; e.log.clear()
    for _ in range(70):
        e.call(e.exports['video_driver_disp_frame'], [fr_addr[0], W, Hh, P])
        if e.h('attaches'):
            break
    check(e.h('attaches') == 1, 're-attached to a new segment')
    e.clock_ns += 6 * 10 ** 9
    e.call(e.exports['video_driver_disp_frame'], [fr_addr[0], W, Hh, P])
    check(any(l.startswith('munmap') for l in e.log), 'heartbeat silent 6 s -> munmap')
    e.log.clear()
    for _ in range(130):
        e.call(e.exports['video_driver_disp_frame'], [fr_addr[0], W, Hh, P])
    check(sum(l.startswith('open') for l in e.log) == 130 // POLL and not any(l.startswith('mmap') for l in e.log),
          'same inode is not re-attached (%d opens, 0 mmaps)' % (130 // POLL))

    print('[G] real driver missing')
    g = Emu(shim, dbg, real_ok=False, quiet=True)
    g.run_ctor()
    check(any('cannot load real driver' in l for l in g.log), 'logged: ' + next((l.strip() for l in g.log if 'cannot' in l), '?'))
    r1 = g.call(g.exports['video_driver_disp_frame'], [0, 1, 2, 3])
    r2 = g.call(g.exports['video_drivers_init'])
    r3 = g.call(g.exports['sound_driver_init'], [0, 48000, 2, 0])
    check(r1 == 0 and r2 == 0 and r3 == 0xFFFFFFFF and not g.real_calls, 'calls return 0 (sound_driver_init -1), nothing jumps to NULL')

    print('[H] TFSHIM_REAL = the shim itself')
    hh = Emu(shim, dbg, env={'TFSHIM_REAL': SHIM_PATH}, same_inode=True, quiet=True)
    hh.run_ctor()
    check(any('is this shim itself' in l for l in hh.log) and not any(l.startswith('dlopen(%s, 0x2' % SHIM_PATH) for l in hh.log),
          'refused without dlopen')

    print('\n%s' % ('ALL EMULATION TESTS PASSED' if not fails else '%d FAILED' % len(fails)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
