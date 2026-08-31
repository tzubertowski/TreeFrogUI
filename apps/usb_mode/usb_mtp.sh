#!/bin/sh
# TreeFrogUI's user-facing USB mode entry point.  MTP keeps the SD mounted.
exec "$(dirname "$0")/usb_mode.sh" mtp
