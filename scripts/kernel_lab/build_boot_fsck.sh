#!/bin/bash
set -euo pipefail
SRC=${1:?pass staged dosfstools source directory}
OUT=${2:?pass a NEW build directory}
test -f "$SRC/src/fsck.fat.c"
test ! -e "$OUT"
mkdir "$OUT"
cd "$OUT"
env CC='mipsel-linux-gnu-gcc -wrapper /usr/bin/env' \
    CFLAGS='-Os -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE' LDFLAGS=-static \
    sh "$SRC/configure" --host=mipsel-linux-gnu --without-iconv --without-udev > configure.log 2>&1
make -j2 > build.log 2>&1
mipsel-linux-gnu-readelf -l src/fsck.fat > elf-program-headers.txt
if grep -q INTERP elf-program-headers.txt; then exit 51; fi
printf 'R36_BOOT_FSCK_BUILD_COMPLETE\n'
