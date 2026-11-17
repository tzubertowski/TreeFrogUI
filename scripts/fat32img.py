"""Read-only FAT32 reader for the raw SD image (MBR is broken, FS starts at sector 32).
usage:
  python -I fat32img.py IMAGE list  OUT.tsv
  python -I fat32img.py IMAGE get   "/path/in/fs" OUTFILE
"""
import struct, sys

class Fat32:
    def __init__(self, path, part_lba=32):
        self.f = open(path, 'rb')
        self.P = part_lba * 512
        self.f.seek(self.P); b = self.f.read(512)
        bps, spc, res, nf = struct.unpack('<HBHB', b[11:17])
        self.fatsz, = struct.unpack('<I', b[36:40]); self.rootc, = struct.unpack('<I', b[44:48])
        self.CS = bps * spc
        self.fat0 = self.P + res * bps
        self.data = self.P + (res + nf * self.fatsz) * bps
        self.f.seek(self.fat0); self.fat = self.f.read(self.fatsz * bps)

    def nxt(self, c): return struct.unpack_from('<I', self.fat, 4 * c)[0] & 0x0FFFFFFF

    def chain(self, c):
        out, seen = [], set()
        while 2 <= c < 0x0FFFFFF8 and c not in seen:
            seen.add(c); out.append(c); c = self.nxt(c)
        return out

    def read_clusters(self, c, size=None):
        parts = []
        for x in self.chain(c):
            self.f.seek(self.data + (x - 2) * self.CS); parts.append(self.f.read(self.CS))
        d = b''.join(parts)
        return d if size is None else d[:size]

    def readdir(self, c):
        raw = self.read_clusters(c); lfn = []; out = []
        for i in range(0, len(raw), 32):
            e = raw[i:i + 32]
            if e[0] == 0: break
            if e[0] == 0xE5: lfn = []; continue
            if e[11] == 0x0F:
                lfn.insert(0, (e[1:11] + e[14:26] + e[28:32]).decode('utf-16le', 'replace').split('\0')[0]); continue
            short = e[:8].decode('latin1').rstrip() + ('.' + e[8:11].decode('latin1').rstrip() if e[8:11].strip() else '')
            name = ''.join(lfn) or short; lfn = []
            if e[11] & 0x08 or name in ('.', '..'): continue
            cl = (struct.unpack('<H', e[20:22])[0] << 16) | struct.unpack('<H', e[26:28])[0]
            sz, = struct.unpack('<I', e[28:32])
            dt, = struct.unpack('<H', e[24:26]); tm, = struct.unpack('<H', e[22:24])
            date = f'{1980 + (dt >> 9):04}-{(dt >> 5) & 15:02}-{dt & 31:02} {tm >> 11:02}:{(tm >> 5) & 63:02}'
            out.append(dict(name=name, dir=bool(e[11] & 0x10), cl=cl, size=sz, date=date, attr=e[11]))
        return out

    def walk(self, c=None, path=''):
        for e in self.readdir(c or self.rootc):
            p = path + '/' + e['name']
            yield p, e
            if e['dir'] and e['cl']: yield from self.walk(e['cl'], p)

    def find(self, path):
        c = self.rootc; e = None
        for part in [x for x in path.split('/') if x]:
            e = next((x for x in self.readdir(c) if x['name'].lower() == part.lower()), None)
            if e is None: raise FileNotFoundError(path)
            c = e['cl']
        return e

if __name__ == '__main__':
    fs = Fat32(sys.argv[1])
    if sys.argv[2] == 'list':
        with open(sys.argv[3], 'w', encoding='utf-8') as o:
            for p, e in fs.walk():
                o.write(f"{'D' if e['dir'] else 'F'}\t{e['size']}\t{e['date']}\t{p}\n")
    elif sys.argv[2] == 'get':
        e = fs.find(sys.argv[3])
        open(sys.argv[4], 'wb').write(fs.read_clusters(e['cl'], e['size']))
