import os, sys

PC = r"D:\r36s-\release\upstream-TreeFrogUI\apps\usb_mode\pc"
sys.path.insert(0, PC)
os.chdir(PC)
import r36


def main():
    path = sys.argv[1]
    out = sys.argv[2]
    dev = r36.R36()
    try:
        with open(out, "wb") as f:
            code, _ = dev.run("/bin/cat '%s'" % path, out=f)
    finally:
        dev.close()
    print("rc=%d size=%d -> %s" % (code, os.path.getsize(out), out))


main()
