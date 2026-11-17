"""Convert headerless BGRA raw UI images to PNG (width auto-detected unless given)."""
import zlib, struct
def png(fn, w, h, rgb):
    def ch(t, d): c = struct.pack('>I', len(d)) + t + d; return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    raw = b''.join(b'\0' + rgb[y*w*3:(y+1)*w*3] for y in range(h))
    open(fn, 'wb').write(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw, 6)) + ch(b'IEND', b''))
def best_w(d, bpp=4, prefer=(640, 320, 480, 1280, 800)):
    n = len(d) // bpp; cands = []
    for w in range(32, 2049):
        if n % w or n // w < 4: continue
        h = n // w; rows = min(h - 1, 80); s = 0
        for r in range(rows):
            a = d[r*w*bpp:(r+1)*w*bpp:bpp*3]; b = d[(r+1)*w*bpp:(r+2)*w*bpp:bpp*3]
            s += sum(abs(x - y) for x, y in zip(a, b)) / max(len(a), 1)
        cands.append((s / rows, w, h))
    cands.sort(); return cands[0][1], cands[0][2]
def bgra_to_rgb(d, bg=(40, 40, 40)):
    out = bytearray(len(d) // 4 * 3)
    for i in range(len(d) // 4):
        b, g, r, a = d[4*i:4*i+4]
        out[3*i] = (r*a + bg[0]*(255-a)) // 255; out[3*i+1] = (g*a + bg[1]*(255-a)) // 255; out[3*i+2] = (b*a + bg[2]*(255-a)) // 255
    return bytes(out)
