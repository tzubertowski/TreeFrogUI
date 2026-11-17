"""Minimal FAT32 writer for the dump card image (partition at LBA 32).
Operates on a COPY of the image. Supports: overwrite existing file content
(<= cluster), truncate its chain; create a new small file (<= cluster) with an
8.3 entry. Enough for: setting.xml edit, libemu_md.so swap, add zhijack.sh,
add MD/dummy.md. Not general-purpose. Verify result with fat32img.py afterwards.
"""
import struct, sys, os

PART_LBA = 32

class Fat32W:
    def __init__(self, path):
        self.f = open(path, 'r+b')
        self.P = PART_LBA * 512
        self.f.seek(self.P); b = self.f.read(512)
        self.bps, self.spc, self.res, self.nf = struct.unpack('<HBHB', b[11:17])
        self.fatsz, = struct.unpack('<I', b[36:40]); self.rootc, = struct.unpack('<I', b[44:48])
        self.CS = self.bps * self.spc
        self.fat0 = self.P + self.res * self.bps
        self.fatN = [self.fat0 + i * self.fatsz * self.bps for i in range(self.nf)]
        self.data = self.P + (self.res + self.nf * self.fatsz) * self.bps
        self.total_clusters = (self.fatsz * self.bps) // 4
        self.f.seek(self.fat0); self.fat = bytearray(self.f.read(self.fatsz * self.bps))
        self.writes = []  # (abs_offset, length)

    # ---- low level ----
    def _w(self, off, data):
        self.f.seek(off); self.f.write(data); self.writes.append((off, len(data)))

    def cl_off(self, c): return self.data + (c - 2) * self.CS

    def get_fat(self, c): return struct.unpack_from('<I', self.fat, 4 * c)[0] & 0x0FFFFFFF

    def set_fat(self, c, val):
        cur = struct.unpack_from('<I', self.fat, 4 * c)[0]
        new = (cur & 0xF0000000) | (val & 0x0FFFFFFF)
        struct.pack_into('<I', self.fat, 4 * c, new)
        for base in self.fatN:
            self._w(base + 4 * c, struct.pack('<I', new))

    def chain(self, c):
        out = []
        while 2 <= c < 0x0FFFFFF8 and c not in out:
            out.append(c); c = self.get_fat(c)
        return out

    def find_free(self, n=1):
        res = []
        for c in range(3, self.total_clusters):
            if self.get_fat(c) == 0:
                res.append(c)
                if len(res) == n: return res
        raise RuntimeError('no free clusters')

    def write_cluster(self, c, data):
        assert len(data) <= self.CS
        self._w(self.cl_off(c), data)

    # ---- directory ----
    def read_dir_entries(self, start_c):
        """yield (abs_offset_of_entry, 32-byte entry) across the dir chain."""
        for c in self.chain(start_c):
            base = self.cl_off(c)
            self.f.seek(base); raw = self.f.read(self.CS)
            for i in range(0, self.CS, 32):
                yield base + i, raw[i:i + 32]

    def iter_dir(self, dir_c):
        """yield dict(off, entry, name, is_dir, first) with LFN reconstruction."""
        lfn = []
        for off, e in self.read_dir_entries(dir_c):
            if e[0] == 0x00:
                return
            if e[0] == 0xE5:
                lfn = []; continue
            if e[11] == 0x0F:
                lfn.insert(0, (e[1:11] + e[14:26] + e[28:32]).decode('utf-16le', 'replace').split('\0')[0])
                continue
            short = e[:8].decode('latin1').rstrip() + ('.' + e[8:11].decode('latin1').rstrip() if e[8:11].strip() else '')
            name = ''.join(lfn) if lfn else short
            lfn = []
            first = (struct.unpack('<H', e[20:22])[0] << 16) | struct.unpack('<H', e[26:28])[0]
            yield dict(off=off, entry=bytearray(e), name=name, short=short,
                       is_dir=bool(e[11] & 0x10), first=first)

    def find_entry(self, dir_c, target):
        """match by full name (case-insensitive, LFN or short). return (off, entry) or None."""
        t = target.lower()
        for d in self.iter_dir(dir_c):
            if d['name'].lower() == t or d['short'].lower() == t:
                return d['off'], d['entry']
        return None

    def find_dir_cluster(self, path):
        c = self.rootc
        for part in [x for x in path.strip('/').split('/') if x]:
            hit = None
            for d in self.iter_dir(c):
                if d['is_dir'] and (d['name'].lower() == part.lower() or d['short'].lower() == part.lower()):
                    hit = d; break
            if hit is None: raise FileNotFoundError(path)
            c = hit['first']
        return c

    @staticmethod
    def _name83(name):
        name = name.upper()
        if '.' in name:
            b, x = name.rsplit('.', 1)
        else:
            b, x = name, ''
        return (b[:8].ljust(8) + x[:3].ljust(3)).encode('ascii')

    def locate_file_entry(self, path):
        d, fn = path.rsplit('/', 1)
        dir_c = self.find_dir_cluster(d if d else '/')
        r = self.find_entry(dir_c, fn)
        if r is None: raise FileNotFoundError(path)
        return dir_c, r[0], r[1]

    def set_entry_size(self, entry_off, entry, size, first_cluster=None):
        if first_cluster is not None:
            struct.pack_into('<H', entry, 20, (first_cluster >> 16) & 0xFFFF)
            struct.pack_into('<H', entry, 26, first_cluster & 0xFFFF)
        struct.pack_into('<I', entry, 28, size)
        self._w(entry_off, bytes(entry))

    # ---- high level ops ----
    def overwrite_file(self, path, data, truncate_extra=True):
        """Overwrite existing file; data must fit in its first cluster (<=CS)."""
        assert len(data) <= self.CS, 'overwrite only supports <= 1 cluster'
        dir_c, eoff, e = self.locate_file_entry(path)
        first = (struct.unpack('<H', e[20:22])[0] << 16) | struct.unpack('<H', e[26:28])[0]
        ch = self.chain(first)
        self.write_cluster(first, data)
        if truncate_extra and len(ch) > 1:
            for c in ch[1:]:
                self.set_fat(c, 0)
            self.set_fat(first, 0x0FFFFFFF)
        self.set_entry_size(eoff, e, len(data), first)
        return first

    def create_file(self, dir_path, name, data, lowercase=True):
        """Create a new <=1 cluster file with an 8.3 entry in dir_path."""
        assert len(data) <= self.CS
        dir_c = self.find_dir_cluster(dir_path)
        n = self._name83(name)
        # find a free slot (0xE5 or 0x00)
        slot = None
        for off, e in self.read_dir_entries(dir_c):
            if e[0] in (0x00, 0xE5):
                slot = off; was_zero = (e[0] == 0x00); break
        if slot is None:
            raise RuntimeError('dir full; extension not implemented')
        cl = self.find_free(1)[0]
        self.set_fat(cl, 0x0FFFFFFF)
        self.write_cluster(cl, data)
        ent = bytearray(32)
        ent[0:11] = n
        ent[11] = 0x20  # archive
        ent[12] = 0x18 if lowercase else 0x00  # low base+ext (display only)
        # date 2026-01-01 00:00
        d = ((2026 - 1980) << 9) | (1 << 5) | 1
        struct.pack_into('<H', ent, 14, 0); struct.pack_into('<H', ent, 16, d)
        struct.pack_into('<H', ent, 18, d); struct.pack_into('<H', ent, 22, 0)
        struct.pack_into('<H', ent, 24, d)
        struct.pack_into('<H', ent, 20, (cl >> 16) & 0xFFFF)
        struct.pack_into('<H', ent, 26, cl & 0xFFFF)
        struct.pack_into('<I', ent, 28, len(data))
        self._w(slot, bytes(ent))
        # keep a terminator after if we consumed a 0x00 slot and the next isn't guaranteed 0
        return cl

    def close(self):
        self.f.flush(); self.f.close()


if __name__ == '__main__':
    img = sys.argv[1]
    base = sys.argv[2]  # dir with input files
    w = Fat32W(img)
    # 1) setting.xml (overwrite in place)
    w.overwrite_file('/CUBEGM/SETTING.XML', open(os.path.join(base, 'setting.xml.new'), 'rb').read())
    # 2) libemu_md.so -> hijack core (overwrite + truncate chain)
    w.overwrite_file('/CUBEGM/CORES/libemu_md.so', open(os.path.join(base, 'libemu_md.so.new'), 'rb').read())
    # 3) new zhijack.sh in /CUBEGM
    w.create_file('/CUBEGM', 'zhijack.sh', open(os.path.join(base, 'zhijack.sh'), 'rb').read())
    # 4) new dummy.md in /MD
    w.create_file('/MD', 'dummy.md', open(os.path.join(base, 'dummy.md'), 'rb').read())
    # merge write ranges, emit patch (4096-aligned blocks) vs nothing here; caller diffs.
    ranges = sorted(w.writes)
    total = sum(l for _, l in ranges)
    print(f'writes: {len(ranges)} ranges, {total} bytes, span {ranges[0][0]}..{ranges[-1][0]+ranges[-1][1]}')
    w.close()
