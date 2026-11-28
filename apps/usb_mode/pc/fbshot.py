"""Screenshot of the R36S screen: fb0 (RGB565, current pan page) + fb1 overlay (ARGB8888)."""
import struct, sys, zlib, time
from r36 import R36

def png(path, w, h, rgb):
    raw = b''.join(b'\0' + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))
    def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))

def grab(r):
    W, H = 640, 480
    cmd = ('set -- $(tr , " " < /sys/class/graphics/fb0/pan); y0=$2; '
           'dd if=/dev/fb0 bs=1280 skip=$y0 count=480 2>/dev/null; '
           'dd if=/dev/fb1 bs=2560 count=480 2>/dev/null')
    code, data = r.run(cmd)
    fb0, fb1 = data[:W * H * 2], data[W * H * 2:W * H * 2 + W * H * 4]
    out = bytearray(W * H * 3)
    for i in range(W * H):
        v = fb0[2 * i] | fb0[2 * i + 1] << 8
        R, G, B = (v >> 11) << 3, ((v >> 5) & 63) << 2, (v & 31) << 3
        if len(fb1) == W * H * 4:
            b, g, rr, a = fb1[4 * i:4 * i + 4]
            if a:
                R = (rr * a + R * (255 - a)) // 255; G = (g * a + G * (255 - a)) // 255; B = (b * a + B * (255 - a)) // 255
        out[3 * i:3 * i + 3] = bytes((R, G, B))
    return W, H, bytes(out)

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'r36_%s.png' % time.strftime('%Y%m%d_%H%M%S')
    r = R36()
    try:
        t = time.time(); w, h, rgb = grab(r)
        png(path, w, h, rgb); print('%s (%.1fs)' % (path, time.time() - t))
    finally:
        r.close()
