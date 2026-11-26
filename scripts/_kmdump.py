import os, sys

PC = r"D:\r36s-\release\upstream-TreeFrogUI\apps\usb_mode\pc"
sys.path.insert(0, PC)
os.chdir(PC)
import r36


def main():
    addr = sys.argv[1]
    length = sys.argv[2]
    out = sys.argv[3]
    dev = r36.R36()
    try:
        with open(out, "wb") as f:
            code, _ = dev.run("/mnt/sdcard/cubegm/mdump %s %s" % (addr, length), out=f)
    finally:
        dev.close()
    print("rc=%d size=%d -> %s" % (code, os.path.getsize(out), out))


main()
