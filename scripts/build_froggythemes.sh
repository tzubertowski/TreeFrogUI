#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK_ROOT=${WORK_ROOT:-$(dirname "$ROOT")}
SOURCE=${FROGGYTHEMES_ROOT:-$WORK_ROOT/TreeFrogUI-Froggythemes}
SDK=${TOOLCHAIN_ROOT:-$WORK_ROOT/sf3000toolchain/mipsel-buildroot-linux-gnu_sdk-buildroot}
TOOLCHAIN=${FROGGYTHEMES_TOOLCHAIN_ROOT:-$SDK/opt/ext-toolchain}
SYSROOT=${FROGGYTHEMES_SYSROOT:-$SDK/mipsel-buildroot-linux-gnu/sysroot}
PREFIX=$TOOLCHAIN/bin/mips-mti-linux-gnu-
OUT=${FROGGYTHEMES_BIN:-$ROOT/build/froggythemes.mipsel}

[[ -f "$SOURCE/Makefile" ]] || {
    echo "Missing FroggyThemes source: $SOURCE" >&2
    exit 1
}
[[ -x "${PREFIX}gcc" ]] || {
    echo "Missing MIPS compiler: ${PREFIX}gcc" >&2
    exit 1
}

mkdir -p "$(dirname "$OUT")"
make -C "$SOURCE" TOOLCHAIN="$TOOLCHAIN" SYSROOT="$SYSROOT"
cp "$SOURCE/froggythemes.mipsel" "$OUT"
"${PREFIX}strip" "$OUT"
file "$OUT"
