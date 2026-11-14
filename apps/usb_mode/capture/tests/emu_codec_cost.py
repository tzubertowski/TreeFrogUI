#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Pavel Kotek
"""Count MIPS instructions of tfc_encode / tfc_downscale2 (the code tfrec runs)
under Unicorn, on reference frames written by test_pipeline.py.

    python emu_codec_cost.py build/tfcodec_mips.so build/test

The codec is built for MIPS32 with the same flags as tfrec (-Os) but as a
shared object so the emu_shim loader can host it. Output is instructions per
frame; divide by the console's clock (and an IPC < 1 for cache misses) for a
time estimate. Results are verified against the PC build via the frame bytes.
"""
import os, struct, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emu_shim import Emu, HEAP  # noqa: E402


def frames(path, want):
    out = []
    with open(path, 'rb') as f:
        while True:
            hd = f.read(12)
            if len(hd) < 12:
                break
            seq, w, h = struct.unpack('<III', hd)
            px = np.frombuffer(f.read(w * h * 2), '<u2').reshape(h, w)
            out.append(px)
    return [out[i] for i in want if i < len(out)]


def main():
    so, tdir = sys.argv[1], sys.argv[2]
    e = Emu(so, so, quiet=True)
    enc, ds = e.exports['tfc_encode'], e.exports['tfc_downscale2']
    cur, prev, out, small = HEAP, HEAP + 0x100000, HEAP + 0x200000, HEAP + 0x300000
    cases = [('2D platformer 2x (s1, t~1-3 s)', 's1_ref.vid', (40, 41)),
             ('menu 320x240 (s1, t~4.5 s)', 's1_ref.vid', (136, 137)),
             ('flat 3D 640x480 (s1, t~5.5 s)', 's1_ref.vid', (166, 167)),
             ('dithered 3D 640x480 (s1hard)', 's1hard_ref.vid', (200, 201))]
    print('%-32s %9s %14s %11s %12s %14s' % ('content', 'size', 'encode insns', 'insns/px', 'bytes out', 'downscale2'))
    for name, fn, idx in cases:
        a, b = frames(os.path.join(tdir, fn), idx)
        h, w = b.shape
        n = w * h
        e.uc.mem_write(prev, a.tobytes())
        e.uc.mem_write(cur, b.tobytes())
        nbytes = e.call(enc, [cur, prev, w, h], [out, n * 3])
        ins = e.icount
        newprev = np.frombuffer(bytes(e.uc.mem_read(prev, n * 2)), '<u2').reshape(h, w)
        assert np.array_equal(newprev, b), 'prev not updated to cur'
        e.call(ds, [cur, w, h, small])
        dsi = e.icount
        print('%-32s %4dx%-4d %14d %11.1f %12d %14d' % (name, w, h, ins, ins / n, nbytes, dsi))
    return 0


if __name__ == '__main__':
    sys.exit(main())
