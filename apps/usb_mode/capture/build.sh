#!/bin/sh
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Pavel Kotek
#
# Build the recording pipeline (tfshim, tfrec, tfcodec.dll). Needs Zig >= 0.17 and Python 3.
#
#   ./build.sh          build into build/ (uses the committed gen/<variant>/ trampolines)
#   DRV=/path/to/cubegm ./build.sh regen
#                       regenerate gen/ from the console's own driver_gb350.so /
#                       driver_sf3500.so first (only symbol names are read)
#   DRV=... ./build.sh test   regen + offline checks (needs pyelftools, unicorn, ffmpeg on Windows)
set -eu
cd "$(dirname "$0")"
export MSYS_NO_PATHCONV=1      # Git Bash: keep "/mnt/sdcard/..." in -D arguments as is
ZIG=${ZIG:-zig}
# python3 first, but skip the Windows Store stub that only prints "Python"
if [ -z "${PY:-}" ]; then
    for c in python3 python; do
        "$c" -c "import sys" >/dev/null 2>&1 && { PY=$c; break; }
    done
fi
: "${PY:?Python 3 not found}"
mkdir -p build

if [ "${1:-}" = regen ] || [ "${1:-}" = test ]; then
    : "${DRV:?set DRV to a folder with the console's driver_gb350.so and driver_sf3500.so}"
    $PY gen_tramp.py "$DRV/driver_sf3500.so" gen/sf3500
    $PY gen_tramp.py "$DRV/driver_gb350.so" gen/gb350
fi

# One shim per real driver: tfshim.c + the generated trampolines, linked for
# MIPS32r2 LE hard-float glibc 2.20 (only libc + libdl). picoarch on a
# TF_DEVICE=GB350 card loads driver_gb350.so (PICOARCH_DRIVER overrides);
# TF_DRIVER readers (image/video viewer) use driver_sf3500.so.
build_shim() {     # variant  real-driver-name  output
    for k in dbg rel; do
        if [ $k = rel ]; then o=build/$3; s=-Wl,--strip-debug; else o=build/$1.dbg.so; s=; fi
        "$ZIG" cc -target mipsel-linux-gnueabihf.2.20 -mcpu=mips32r2 -shared -fPIC -O2 \
            -fomit-frame-pointer -mllvm -mips-tail-calls=1 -fvisibility=hidden -Wall -Wextra \
            -DTFSHIM_DEFAULT_REAL=\"/mnt/sdcard/cubegm/$2\" -I. -Igen/$1 \
            -o $o tfshim.c gen/$1/tfshim_tramp.S -ldl -Wl,-soname,driver.so $s
        $PY postlink.py $o
    done
}
build_shim sf3500 driver_sf3500.so tfshim.so
build_shim gb350 driver_gb350.so tfshim_gb350.so

# tfrec: static musl (no dependency on the console's libc)
"$ZIG" cc -target mipsel-linux-musleabi -mcpu=mips32 -static -O2 -s -Wall -Wextra -I. \
    -o build/tfrec tfrec.c tfrec_core.c tfcodec.c

# PC side: decoder DLL for pc/r36rec.py and the synthetic-stream test harness
"$ZIG" cc -target x86_64-windows-gnu -O2 -shared -I. -o build/tfcodec.dll tfcodec.c
"$ZIG" cc -target x86_64-windows-gnu -O2 -Wall -Wextra -I. -o build/tfsynth.exe \
    tests/tfsynth.c tfrec_core.c tfcodec.c
rm -f build/*.lib build/*.pdb
ls -l build/tfshim.so build/tfshim_gb350.so build/tfrec build/tfcodec.dll

if [ "${1:-}" = test ]; then
    $PY tests/check_shim.py build/tfshim.so build/sf3500.dbg.so "$DRV/driver_sf3500.so" build/tfrec
    $PY tests/check_shim.py build/tfshim_gb350.so build/gb350.dbg.so "$DRV/driver_gb350.so"
    $PY tests/emu_shim.py build/tfshim.so build/sf3500.dbg.so
    $PY tests/emu_shim.py build/tfshim_gb350.so build/gb350.dbg.so
    $PY tests/test_pipeline.py
fi
