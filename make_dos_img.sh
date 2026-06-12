#!/bin/bash
# Pack a folder of DOS game files into a hard-disk image (C:) for pico286.
# pico286 boots the bundled FreeDOS floppy and auto-runs RUN.BAT (or the first
# .EXE/.COM/.BAT) found in the root of this image.
#
# Usage:  ./make_dos_img.sh <game_folder> <out.img> [size_MB]
#         (default size 32 MB)
#
# Then put <out.img> in  sdcard/roms/pico286/<name>/  and launch it.
# Tip: add a RUN.BAT in <game_folder> with the exact command, e.g.:
#        @echo off
#        cd \PRINCE
#        PRINCE.EXE
set -e
SRC="$1"; OUT="$2"; MB="${3:-32}"
[ -d "$SRC" ] && [ -n "$OUT" ] || { echo "usage: $0 <game_folder> <out.img> [size_MB]"; exit 1; }
command -v mformat >/dev/null || { echo "need mtools (mformat/mcopy/mpartition)"; exit 1; }

BYTES_PER_CYL=$((16*63*512))                 # heads*sects*512 = 516096
CYL=$(( MB*1024*1024 / BYTES_PER_CYL ))
[ "$CYL" -ge 1 ] || CYL=1
[ "$CYL" -le 1023 ] || CYL=1023              # CHS cylinder limit the emu enforces
SIZE=$(( CYL * BYTES_PER_CYL ))

dd if=/dev/zero of="$OUT" bs=512 count=$((SIZE/512)) status=none
export MTOOLS_SKIP_CHECK=1
RC=$(mktemp)
echo "drive z: file=\"$OUT\" partition=1 cylinders=$CYL heads=16 sectors=63 mformat_only" > "$RC"
MTOOLSRC="$RC" mpartition -I -c -t "$CYL" -h 16 -s 63 z:
MTOOLSRC="$RC" mformat -F z:
MTOOLSRC="$RC" mcopy -s "$SRC"/* z:
rm -f "$RC"
echo "Created $OUT  (${MB}MB, ${CYL} cyl, $(( SIZE/1024/1024 )) MB usable)."
echo "Drop it in sdcard/roms/pico286/<name>/ and launch from TreeFrogUI."
