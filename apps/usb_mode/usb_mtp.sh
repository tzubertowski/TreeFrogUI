#!/bin/sh
# TreeFrogUI's user-facing USB mode entry point.  MTP keeps the SD mounted.
# tfusbd already serves MTP in the background: nothing to do here.
if [ -f /tmp/tfusbd.pid ] && kill -0 "$(cat /tmp/tfusbd.pid)" 2>/dev/null; then exit 0; fi
exec "$(dirname "$0")/usb_mode.sh" mtp
