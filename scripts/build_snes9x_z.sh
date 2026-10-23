#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK_ROOT=${WORK_ROOT:-$(dirname "$ROOT")}
TOOLCHAIN=$WORK_ROOT/sf3000toolchain/mipsel-buildroot-linux-gnu_sdk-buildroot
PREFIX=$TOOLCHAIN/opt/ext-toolchain/bin/mips-mti-linux-gnu-
SYSROOT=$TOOLCHAIN/mipsel-buildroot-linux-gnu/sysroot
PATCH=$ROOT/patches/snes9x-z-mips.patch
SOURCE_REV=c3c6710f9efcfec4c2c513baeb602cf17dd7d909
FLAGS="-mips32r2 -march=mips32r2 -mtune=74kc -mfp32 -mhard-float -mlong-calls -EL --sysroot=$SYSROOT -fPIC -Ofast -O3 -DNDEBUG"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/snes9x-z.XXXXXX")
CORE=$WORK/src
trap 'rm -rf "$WORK"' EXIT

git init -q "$CORE"
git -C "$CORE" fetch --depth=1 https://github.com/andrezaiats/snes9x-Z.git "$SOURCE_REV"
git -C "$CORE" checkout --quiet --detach FETCH_HEAD
[[ "$(git -C "$CORE" rev-parse HEAD)" == "$SOURCE_REV" ]] || {
    echo "Snes9x-Z upstream changed; review and update SOURCE_REV and its MIPS patch" >&2
    exit 1
}

if git -C "$CORE" apply --check "$PATCH" 2>/dev/null; then
    git -C "$CORE" apply "$PATCH"
elif ! git -C "$CORE" apply --reverse --check "$PATCH" 2>/dev/null; then
    echo "Snes9x-Z MIPS patch does not match the checked-out source" >&2
    exit 1
fi

make -C "$CORE/libretro" clean LTO=
make -C "$CORE/libretro" platform=unix \
    CC="${PREFIX}gcc" CXX="${PREFIX}g++" \
    AR="${PREFIX}ar" RANLIB="${PREFIX}ranlib" \
    CFLAGS="$FLAGS" CXXFLAGS="$FLAGS -std=gnu++14" \
    LDFLAGS="-EL -mips32r2 -march=mips32r2 -mtune=74kc -mfp32 -mhard-float -mlong-calls --sysroot=$SYSROOT -L$SYSROOT/usr/lib -latomic" \
    LTO= -j"$(nproc)"

mkdir -p "$ROOT/build"
cp "$CORE/libretro/snes9x-Z_libretro.so" "$ROOT/build/snes9x-Z_libretro.so"
cp "$CORE/LICENSE" "$ROOT/build/Snes9x-Z.LICENSE"
"${PREFIX}strip" "$ROOT/build/snes9x-Z_libretro.so"
