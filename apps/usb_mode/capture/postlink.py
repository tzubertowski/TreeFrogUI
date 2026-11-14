#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Pavel Kotek
"""Remove DT_INIT / DT_FINI from a 32-bit LE shared object, in place.

lld points DT_INIT/DT_FINI at any symbol named _init/_fini. tfshim exports
trampolines with those names (the real driver exports them), and they must
not run at load/unload. Our constructor runs through DT_INIT_ARRAY instead.
The remaining entries are shifted down and the tail padded with DT_NULL.

    python postlink.py tfshim.so
"""
import struct, sys

DT_NULL, DT_INIT, DT_FINI = 0, 12, 13


def main(path):
    d = bytearray(open(path, 'rb').read())
    assert d[:4] == b'\x7fELF' and d[4] == 1 and d[5] == 1, 'need ELF32 LE'
    phoff, = struct.unpack_from('<I', d, 0x1c)
    phentsize, phnum = struct.unpack_from('<HH', d, 0x2a)
    for i in range(phnum):
        p_type, p_off, _, _, p_filesz = struct.unpack_from('<IIIII', d, phoff + i * phentsize)
        if p_type != 2:                      # PT_DYNAMIC
            continue
        ents = [struct.unpack_from('<iI', d, p_off + 8 * k) for k in range(p_filesz // 8)]
        end = next(k for k, (t, _) in enumerate(ents) if t == DT_NULL)
        live = ents[:end]
        keep = [e for e in live if e[0] not in (DT_INIT, DT_FINI)]
        removed = len(live) - len(keep)
        out = keep + [(DT_NULL, 0)] * (len(ents) - len(keep))
        for k, (t, v) in enumerate(out):
            struct.pack_into('<iI', d, p_off + 8 * k, t, v)
        open(path, 'wb').write(d)
        print('postlink: removed %d DT_INIT/DT_FINI entr%s from %s' % (removed, 'y' if removed == 1 else 'ies', path))
        return 0
    raise SystemExit('no PT_DYNAMIC in ' + path)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
