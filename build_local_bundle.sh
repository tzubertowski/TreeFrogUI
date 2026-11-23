#!/bin/bash
# Rebuild every component formerly compiled by release.yml, assemble the full
# release tree, and emit the immutable archive consumed by GitHub Actions.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)
WORK_ROOT=${WORK_ROOT:-$(dirname "$ROOT")}
FROGUI_ROOT=${FROGUI_ROOT:-$ROOT/frogui}
PICOARCH_ROOT=${PICOARCH_ROOT:-$WORK_ROOT/picoarch}
PICANTE8_ROOT=${PICANTE8_ROOT:-$WORK_ROOT/picante8}
EBOOK_ROOT=${EBOOK_ROOT:-$WORK_ROOT/ebook}
MUPDF_ROOT=${MUPDF_ROOT:-$WORK_ROOT/mupdf}
DSPERATE_ROOT=${DSPERATE_ROOT:-$WORK_ROOT/dsperate/build/sf3000-package}
TOOLCHAIN=$WORK_ROOT/sf3000toolchain/mipsel-buildroot-linux-gnu_sdk-buildroot
PREFIX=$TOOLCHAIN/opt/ext-toolchain/bin/mips-mti-linux-gnu-
SYSROOT=$TOOLCHAIN/mipsel-buildroot-linux-gnu/sysroot
if [[ -z "${FROGGYTHEMES_ROOT:-}" ]]; then
  for candidate in "$WORK_ROOT/TreeFrogUI-Froggythemes" "$WORK_ROOT/froggythemes"; do
    if [[ -f "$candidate/Makefile" ]]; then
      FROGGYTHEMES_ROOT=$candidate
      break
    fi
  done
fi
FROGGYTHEMES_ROOT=${FROGGYTHEMES_ROOT:-$WORK_ROOT/TreeFrogUI-Froggythemes}
FROGGYTHEMES_TOOLCHAIN_ROOT=${FROGGYTHEMES_TOOLCHAIN_ROOT:-$TOOLCHAIN/opt/ext-toolchain}
FROGGYHWPROBE_ROOT=${FROGGYHWPROBE_ROOT:-$WORK_ROOT/froggyhwprobe}
FROGGYBENCHMARK_ROOT=${FROGGYBENCHMARK_ROOT:-$WORK_ROOT/froggybenchmark}
FROGGY_DIAGNOSTICS_TC=${FROGGY_DIAGNOSTICS_TC:-${SF3500_TC:-$WORK_ROOT/buildroot/output/host}}
FROGGY_DIAGNOSTICS_REBUILD=${FROGGY_DIAGNOSTICS_REBUILD:-1}
DSPERATE_SHA256=${DSPERATE_SHA256:-39c080709be1dca0056613b4f548aaffb1f0aaf18c1c988cdad3f37251e206a8}
J2ME_HEAP_BYTES=${J2ME_HEAP_BYTES:-8388608}
SOURCE_ID=$(git -C "$ROOT" rev-parse --short=7 HEAD)
OUTPUT=${1:-/tmp/TreeFrogUI-local-build-$SOURCE_ID.tar.gz}

for file in \
  "$PREFIX"gcc \
  "$FROGUI_ROOT/build_libretro.sh" \
  "$ROOT/hijack/build_tfhijack.sh" \
  "$PICOARCH_ROOT/build_sf3000.sh" \
  "$ROOT/patches/snes9x-z-mips.patch" \
  "$ROOT/scripts/build_snes9x_z.sh" \
  "$ROOT/scripts/build_pokket.sh" \
  "$ROOT/scripts/build_froggyreader.sh" \
  "$ROOT/scripts/build_froggythemes.sh" \
  "$ROOT/scripts/build_froggyhwprobe.sh" \
  "$ROOT/scripts/build_froggybenchmark.sh" \
  "$PICANTE8_ROOT/Makefile" \
  "$EBOOK_ROOT/build_reader_sf.sh" \
  "$DSPERATE_ROOT/dsperate" \
  "$FROGGYTHEMES_ROOT/Makefile" \
  "$FROGGYTHEMES_ROOT/pack/Froggythemes-app.sh" \
  "$FROGGYTHEMES_ROOT/pack/active-frog.rgba" \
  "$FROGGYTHEMES_ROOT/pack/run.sh" \
  "$FROGGYTHEMES_ROOT/pack/README.txt" \
  "$FROGGYTHEMES_ROOT/LICENSE" \
  "$FROGGYTHEMES_ROOT/NOTICE.md" \
  "$FROGGYHWPROBE_ROOT/build.sh" \
  "$FROGGYHWPROBE_ROOT/pack/FroggyHWProbe-app.sh" \
  "$FROGGYHWPROBE_ROOT/pack/run.sh" \
  "$FROGGYHWPROBE_ROOT/pack/README.txt" \
  "$FROGGYHWPROBE_ROOT/LICENSE" \
  "$FROGGYHWPROBE_ROOT/NOTICE.md" \
  "$FROGGYBENCHMARK_ROOT/build.sh" \
  "$FROGGYBENCHMARK_ROOT/pack/FroggyBenchmark-app.sh" \
  "$FROGGYBENCHMARK_ROOT/pack/run.sh" \
  "$FROGGYBENCHMARK_ROOT/pack/README.txt" \
  "$FROGGYBENCHMARK_ROOT/LICENSE" \
  "$FROGGYBENCHMARK_ROOT/NOTICE.md"; do
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

echo 'Building Snes9x-Z...'
WORK_ROOT="$WORK_ROOT" "$ROOT/scripts/build_snes9x_z.sh"

echo 'Building Pokket...'
WORK_ROOT="$WORK_ROOT" "$ROOT/scripts/build_pokket.sh"

echo 'Building ScummVM...'
WORK_ROOT="$WORK_ROOT" bash "$ROOT/scripts/build_scummvm.sh"

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

echo 'Building Picante8...'
make -C "$PICANTE8_ROOT" clean
PICANTE8_FLAGS="-O3 -fPIC -fomit-frame-pointer -ffast-math -march=mips32 -mtune=mips32r2 -mhard-float -mfp32 -EL -isystem $TOOLCHAIN/opt/ext-toolchain/sysroot/mipsel-r2-hard/usr/include -Isrc -Isrc/io -Isrc/lua -Isrc/libretro -Isrc/vm -D__LIBRETRO__"
make -C "$PICANTE8_ROOT" platform=retrofw \
  CC="${PREFIX}gcc" CXX="${PREFIX}g++" AR="${PREFIX}ar" RANLIB="${PREFIX}ranlib" \
  CFLAGS="$PICANTE8_FLAGS" CXXFLAGS="$PICANTE8_FLAGS -std=c++14" \
  LDFLAGS="-EL -L$TOOLCHAIN/opt/ext-toolchain/sysroot/mipsel-r2-hard/usr/lib" -j2
mkdir -p "$ROOT/build"
cp "$PICANTE8_ROOT/picante8_libretro.so" "$ROOT/build/picante8_libretro.so"
"${PREFIX}strip" "$ROOT/build/picante8_libretro.so"

echo 'Building MuPDF and ebook reader...'
make -C "$MUPDF_ROOT" clean
"$EBOOK_ROOT/build_mupdf_sf.sh"
"$EBOOK_ROOT/build_reader_sf.sh"

echo 'Building FroggyReader...'
WORK_ROOT="$WORK_ROOT" "$ROOT/scripts/build_froggyreader.sh"

echo 'Building FroggyThemes...'
WORK_ROOT="$WORK_ROOT" \
FROGGYTHEMES_ROOT="$FROGGYTHEMES_ROOT" \
FROGGYTHEMES_TOOLCHAIN_ROOT="$FROGGYTHEMES_TOOLCHAIN_ROOT" \
  "$ROOT/scripts/build_froggythemes.sh"

echo 'Building FroggyHWProbe...'
WORK_ROOT="$WORK_ROOT" \
FROGGYHWPROBE_ROOT="$FROGGYHWPROBE_ROOT" \
FROGGYHWPROBE_BIN="$ROOT/build/froggyhwprobe.mipsel" \
FROGGYHWPROBE_TC="$FROGGY_DIAGNOSTICS_TC" \
FROGGYHWPROBE_REBUILD="$FROGGY_DIAGNOSTICS_REBUILD" \
  "$ROOT/scripts/build_froggyhwprobe.sh"

echo 'Building FroggyBenchmark...'
WORK_ROOT="$WORK_ROOT" \
FROGGYBENCHMARK_ROOT="$FROGGYBENCHMARK_ROOT" \
FROGGYBENCHMARK_BIN="$ROOT/build/froggybenchmark.mipsel" \
FROGGYBENCHMARK_TC="$FROGGY_DIAGNOSTICS_TC" \
FROGGYBENCHMARK_REBUILD="$FROGGY_DIAGNOSTICS_REBUILD" \
  "$ROOT/scripts/build_froggybenchmark.sh"

echo 'Building TreeFrogUI hijack helpers...'
"$ROOT/hijack/build_tfhijack.sh"

echo 'Assembling release tree...'
FROGUI_ROOT="$FROGUI_ROOT" \
DSPERATE="$DSPERATE_ROOT" \
FROGGYTHEMES_ROOT="$FROGGYTHEMES_ROOT" \
FROGGYTHEMES_BIN="$ROOT/build/froggythemes.mipsel" \
FROGGYHWPROBE_ROOT="$FROGGYHWPROBE_ROOT" \
FROGGYHWPROBE_BIN="$ROOT/build/froggyhwprobe.mipsel" \
FROGGYBENCHMARK_ROOT="$FROGGYBENCHMARK_ROOT" \
FROGGYBENCHMARK_BIN="$ROOT/build/froggybenchmark.mipsel" \
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
