import sys, os, struct

CH = 512 * 4096  # 2 MB chunk size used by the device script

def load_chunks(d):
    out = {}
    i = 0
    while True:
        p = os.path.join(d, "kcore_%d.bin" % i)
        if not os.path.exists(p):
            break
        out[i] = open(p, "rb").read()
        i += 1
    return out

def read_file_off(chunks, off, n):
    buf = bytearray()
    while n > 0:
        i = off // CH
        loc = off % CH
        if i not in chunks:
            buf += b"\xff" * n
            break
        data = chunks[i]
        if loc >= len(data):
            buf += b"\xff" * n
            break
        take = min(n, len(data) - loc)
        buf += data[loc:loc + take]
        off += take
        n -= take
    return bytes(buf)

def phdrs(head):
    e_phoff, = struct.unpack_from("<I", head, 0x1c)
    e_phentsize, = struct.unpack_from("<H", head, 0x2a)
    e_phnum, = struct.unpack_from("<H", head, 0x2c)
    res = []
    for k in range(e_phnum):
        o = e_phoff + k * e_phentsize
        if o + 32 > len(head):
            break
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from("<8I", head, o)
        res.append(dict(type=t, off=off, vaddr=va, filesz=fsz, memsz=msz))
    return res

def main():
    d = sys.argv[1]
    head = open(os.path.join(d, "kcore_head.bin"), "rb").read()
    ph = phdrs(head)
    print("segments:", len(ph))
    for p in ph:
        if p["type"] == 1:
            print("  LOAD off=0x%08x vaddr=0x%08x filesz=0x%x memsz=0x%x end=0x%08x"
                  % (p["off"], p["vaddr"], p["filesz"], p["memsz"], p["vaddr"] + p["memsz"]))
    if len(sys.argv) < 4:
        return
    va = int(sys.argv[2], 16)
    n = int(sys.argv[3], 0)
    seg = None
    for p in ph:
        if p["type"] == 1 and p["vaddr"] <= va < p["vaddr"] + max(p["filesz"], p["memsz"]):
            seg = p
            break
    chunks = load_chunks(d)
    print("chunks:", sorted(chunks), "total", sum(len(v) for v in chunks.values()))
    if seg is None:
        print("vaddr 0x%08x not covered by any LOAD segment" % va)
        return
    off = seg["off"] + (va - seg["vaddr"])
    data = read_file_off(chunks, off, n)
    out = sys.argv[4] if len(sys.argv) > 4 else "out.bin"
    open(out, "wb").write(data)
    print("wrote %d bytes from file off 0x%x to %s" % (len(data), off, out))
    print("first 32:", data[:32].hex(" "))

main()
