import os, sys

PC = r"D:\r36s-\release\upstream-TreeFrogUI\apps\usb_mode\pc"
sys.path.insert(0, PC)
os.chdir(PC)
import r36

CHUNK = 1 << 20


def main():
    base = int(sys.argv[1], 16)
    total = int(sys.argv[2], 16) if len(sys.argv) > 2 else CHUNK
    out = sys.argv[3]
    dev = r36.R36()
    done = 0
    try:
        with open(out, "wb") as f:
            while done < total:
                n = min(CHUNK, total - done)
                addr = base + done
                code, _ = dev.run("/mnt/sdcard/cubegm/mdump 0x%08x 0x%x" % (addr, n), out=f)
                if code != 0:
                    print("rc=%d at 0x%08x" % (code, addr))
                    break
                done += n
                f.flush()
                print("  0x%08x (%d/%d)" % (addr, done, total))
    finally:
        dev.close()
    print("total=%d -> %s" % (done, out))


main()
