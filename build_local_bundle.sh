#!/bin/bash
# Rebuild every component formerly compiled by release.yml, assemble the full
# release tree, and emit the immutable archive consumed by GitHub Actions.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)
WORK_ROOT=${WORK_ROOT:-$(dirname "$ROOT")}
FROGUI_ROOT=${FROGUI_ROOT:-$WORK_ROOT/FrogUI}
PICOARCH_ROOT=${PICOARCH_ROOT:-$WORK_ROOT/picoarch}
FROGGYCRAFT_ROOT=${FROGGYCRAFT_ROOT:-$WORK_ROOT/FroggyCraft}
FROGGYPE_ROOT=${FROGGYPE_ROOT:-$WORK_ROOT/FroggyPE}
EBOOK_ROOT=${EBOOK_ROOT:-$WORK_ROOT/ebook}
MUPDF_ROOT=${MUPDF_ROOT:-$WORK_ROOT/mupdf}
DSPERATE_ROOT=${DSPERATE_ROOT:-$WORK_ROOT/dsperate/build/sf3000-package}
TOOLCHAIN=$WORK_ROOT/sf3000toolchain/mipsel-buildroot-linux-gnu_sdk-buildroot
PREFIX=$TOOLCHAIN/opt/ext-toolchain/bin/mips-mti-linux-gnu-
SYSROOT=$TOOLCHAIN/mipsel-buildroot-linux-gnu/sysroot
DSPERATE_SHA256=${DSPERATE_SHA256:-705d8af897d7c8b5ca968bd8171497fc0f4099e8c9c24b62a0acbdabb2ce3419}
J2ME_HEAP_BYTES=${J2ME_HEAP_BYTES:-8388608}
SOURCE_ID=$(git -C "$ROOT" rev-parse --short=7 HEAD)
OUTPUT=${1:-/tmp/TreeFrogUI-local-build-$SOURCE_ID.tar.gz}

for file in \
  "$PREFIX"gcc \
  "$FROGUI_ROOT/build_libretro.sh" \
  "$PICOARCH_ROOT/build_sf3000.sh" \
  "$FROGGYCRAFT_ROOT/source/classicube_sf2000/Makefile" \
  "$FROGGYPE_ROOT/Makefile.sf2000" \
  "$EBOOK_ROOT/build_reader_sf.sh" \
  "$DSPERATE_ROOT/dsperate"; do
  [[ -e "$file" ]] || { echo "Missing local build input: $file" >&2; exit 1; }
done

echo "$DSPERATE_SHA256  $DSPERATE_ROOT/dsperate" | sha256sum -c -
echo 'fca3e514b635a21789d4224e84865d2954a2a914d46b64aa8219ddb565c44869  '"$ROOT/cores/scummvm/dists/soundfonts/Roland_SC-55.sf2" | sha256sum -c -

echo 'Building FrogUI...'
rm -rf "$FROGUI_ROOT/out"
"$FROGUI_ROOT/build_libretro.sh"

echo 'Building picoarch frontends...'
"$PICOARCH_ROOT/build_sf3000.sh"
"$PICOARCH_ROOT/build_picoarch_hi.sh"

echo 'Building QPSX...'
mkdir -p "$ROOT/build"
make -C "$ROOT/cores/qpsx" -f Makefile.libretro clean platform=sf3000
make -C "$ROOT/cores/qpsx" -f Makefile.libretro platform=sf3000 \
  CC="${PREFIX}gcc" CXX="${PREFIX}g++" AR="${PREFIX}ar" RANLIB="${PREFIX}ranlib" \
  LDFLAGS="-shared -Wl,--no-undefined -mips32r2 -mhard-float -mfp32 -EL --sysroot=$SYSROOT -L$SYSROOT/usr/lib -lm -lc -lstdc++" \
  -j"$(nproc)"
cp "$ROOT/cores/qpsx/pcsx4all_libretro.so" "$ROOT/build/qpsx_libretro.so"
"${PREFIX}strip" "$ROOT/build/qpsx_libretro.so"

echo 'Building FroggyKVM...'
make -C "$ROOT/cores/FroggyKVM" clean
make -C "$ROOT/cores/FroggyKVM" platform=sf3000 \
  J2ME_MAX_HEAP_BYTES="$J2ME_HEAP_BYTES" \
  CC="${PREFIX}gcc" CXX="${PREFIX}g++" AR="${PREFIX}ar" RANLIB="${PREFIX}ranlib" LD="${PREFIX}g++" \
  LDFLAGS="-mhard-float -mfp32 -EL --sysroot=$SYSROOT -L$SYSROOT/usr/lib -lm -lc -lstdc++" \
  -j1
cp "$ROOT/cores/FroggyKVM/j2me_libretro.so" "$ROOT/build/j2me_libretro.so"
"${PREFIX}strip" "$ROOT/build/j2me_libretro.so"

echo 'Building ClassiCube...'
make -C "$FROGGYCRAFT_ROOT/source/classicube_sf2000" SF2000_PLATFORM=sf3000 clean
make -C "$FROGGYCRAFT_ROOT/source/classicube_sf2000" SF2000_PLATFORM=sf3000 -j2

echo 'Building Minecraft PE...'
make -C "$FROGGYPE_ROOT" -f Makefile.sf2000 platform=sf3000 clean
make -C "$FROGGYPE_ROOT" -f Makefile.sf2000 platform=sf3000 \
  MIPS="$PREFIX" SYSROOT="$SYSROOT" -j2
"${PREFIX}strip" "$FROGGYPE_ROOT/mcpe_libretro.so"

echo 'Building MuPDF and ebook reader...'
make -C "$MUPDF_ROOT" clean
"$EBOOK_ROOT/build_mupdf_sf.sh"
"$EBOOK_ROOT/build_reader_sf.sh"

echo 'Assembling release tree...'
FROGUI_ROOT="$FROGUI_ROOT" \
FROGGYCRAFT_ROOT="$FROGGYCRAFT_ROOT" \
FROGGYPE_ROOT="$FROGGYPE_ROOT" \
DSPERATE="$DSPERATE_ROOT" \
  "$ROOT/build_release.sh"

bundle_dir=$(mktemp -d /tmp/treefrog-local-bundle.XXXXXX)
trap 'rm -rf "$bundle_dir"' EXIT
mkdir -p "$bundle_dir/release"
rsync -a "$ROOT/release/latest/release/" "$bundle_dir/release/"
(
  cd "$bundle_dir/release"
  find . -type f -print0 | sort -z | xargs -0 sha256sum
) > "$bundle_dir/SHA256SUMS"
(
  cd "$bundle_dir/release"
  sha256sum -c ../SHA256SUMS >/dev/null
)
tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner \
  -czf "$OUTPUT" -C "$bundle_dir" SHA256SUMS release

echo "Local release bundle ready: $OUTPUT"
sha256sum "$OUTPUT"
