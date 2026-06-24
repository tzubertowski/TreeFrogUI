#!/bin/sh
# Build libemu_tfhijack.so — the SF3500 boot-hijack libretro core.
# Output: libemu_tfhijack.so  → copy to SD cubegm/cores/
set -e
cd "$(dirname "$0")"

MIPS="$HOME/sf3000-work/sf3000toolchain/mipsel-buildroot-linux-gnu_sdk-buildroot/opt/ext-toolchain/bin/mips-mti-linux-gnu-"
SYSROOT="$HOME/sf3000-work/sf3000toolchain/mipsel-buildroot-linux-gnu_sdk-buildroot/mipsel-buildroot-linux-gnu/sysroot"
CC="${MIPS}gcc"

[ -x "${CC}" ] || { echo "toolchain not found: ${CC}"; exit 1; }

CFLAGS="-mips32r2 -march=mips32r2 -mtune=74kc -mfp32 -mhard-float -mlong-calls -EL \
        --sysroot=$SYSROOT -fPIC -G0 -Wall -O2 -DNDEBUG"

# Normal libc-linked shared lib (rkgame's process has libc). proper PIC relocs.
$CC $CFLAGS -shared -Wl,--gc-sections -EL --sysroot="$SYSROOT" \
    -o libemu_tfhijack.so tfhijack.c

"${MIPS}strip" libemu_tfhijack.so 2>/dev/null || true
ls -la libemu_tfhijack.so
file libemu_tfhijack.so
echo "=== exported retro_* symbols ==="
"${MIPS}readelf" --dyn-syms libemu_tfhijack.so 2>/dev/null \
    | awk '$4=="FUNC"{print $8}' | grep '^retro_' | sort | tr '\n' ' '; echo
