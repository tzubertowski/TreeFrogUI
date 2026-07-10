#!/bin/bash
# SF3000 multicore builder — produces libretro .so files for picoarch
# Comment/uncomment individual cores to control what gets built.
# Output: build/<name>_libretro.so  → copy to /mnt/sdcard/cubegm/cores/
#
# IMPORTANT — two wrapper scripts are used:
#   .toolchain/mips-gcc/g++   : full SF3000 flags (mips32r2, sysroot, Ofast) — most cores
#   .toolchain/gpsp-gcc/g++   : sysroot + fPIC only, no arch flags — gpsp picks its own
#
# The wrappers are in .toolchain/. Regenerate with make-wrappers target.

set -uo pipefail
cd "$(dirname "$0")"

# ── Apply patches for externally-owned repos ─────────────────────────────────
_apply_patch() {
    # Absolute patch path: git -C runs from the core dir, so a relative
    # "patches/..." would resolve inside the core (wrong) and silently skip.
    local patch="$(pwd)/patches/$1" dir="cores/$2"
    [ -f "$patch" ] || return
    if git -C "$dir" apply --check "$patch" 2>/dev/null; then
        git -C "$dir" apply "$patch" && echo "patched $2"
    else
        echo "patch already applied or conflict: $1 (skipping)"
    fi
}
_apply_patch geolith-no-lto.patch      libretro-geolith
_apply_patch uae-posix-fs.patch        sf2000-uae-amiga-emulator
_apply_patch uae-sf3000-fixes.patch    sf2000-uae-amiga-emulator
_apply_patch castaway-linux-build.patch sf2000-atarist-emulator
_apply_patch pcsx_rearmed-sf3000-lightrec.patch pcsx_rearmed
_apply_patch gpsp-upstream-sf3000.patch gpsp_upstream
_apply_patch ardens-sf3000.patch       Ardens
_apply_patch pico286-sf3000.patch      pico-286

TOOLCHAIN="$HOME/sf3000-work/sf3000toolchain/mipsel-buildroot-linux-gnu_sdk-buildroot"
MIPS="$TOOLCHAIN/opt/ext-toolchain/bin/mips-mti-linux-gnu-"
SYSROOT="$TOOLCHAIN/mipsel-buildroot-linux-gnu/sysroot"
OUT="$(pwd)/build"
CORES="$(pwd)/cores"
WRAP="$(pwd)/.toolchain"

mkdir -p "$OUT" "$WRAP"

# ── Compiler wrappers ─────────────────────────────────────────────────────────
# -mlong-calls is REQUIRED — removing it crashes cores that make far calls
# (e.g. snes9x2005 SuperFX / Yoshi's Island). Keep it.
# Device CPU is a MIPS 74Kc (dual-issue, out-of-order) with the DSP2 ASE
# (confirmed via /proc/cpuinfo). Tune for 74kc and enable -mdspr2 — 24kc tuning
# schedules for the wrong pipeline and leaves the DSP instructions unused.
SF3000_FLAGS="-mips32r2 -march=mips32r2 -mtune=74kc -mdspr2 -mfp32 -mhard-float -mlong-calls -EL --sysroot=$SYSROOT -Ofast -DNDEBUG"

cat > "$WRAP/mips-gcc" <<EOF
#!/bin/bash
exec ${MIPS}gcc $SF3000_FLAGS "\$@"
EOF
cat > "$WRAP/mips-g++" <<EOF
#!/bin/bash
exec ${MIPS}g++ $SF3000_FLAGS "\$@"
EOF
# gpsp wrapper — no arch flags (platform=mips32 sets them), only sysroot.
# -EL forces little-endian: this toolchain's g++ defaults to big-endian (gcc to
# LE), which silently produced BE objects for upstream gpsp's C++ video.cc.
cat > "$WRAP/gpsp-gcc" <<EOF
#!/bin/bash
exec ${MIPS}gcc --sysroot=$SYSROOT -isystem $SYSROOT/usr/include -fPIC -EL "\$@"
EOF
cat > "$WRAP/gpsp-g++" <<EOF
#!/bin/bash
exec ${MIPS}g++ --sysroot=$SYSROOT -isystem $SYSROOT/usr/include -fPIC -EL "\$@"
EOF
# -O3 variants: a trailing -O3 wins over a core Makefile that hardcodes a lower
# -O after our flags (fake08's libretro Makefile appends -O2 on platform=unix,
# which otherwise overrides the wrapper's -Ofast → the core builds at -O2). Use
# -O3 (not -Ofast) so -ffast-math doesn't alter audio synthesis.
cat > "$WRAP/mips-gcc-O3" <<EOF
#!/bin/bash
exec ${MIPS}gcc $SF3000_FLAGS "\$@" -O3
EOF
cat > "$WRAP/mips-g++-O3" <<EOF
#!/bin/bash
exec ${MIPS}g++ $SF3000_FLAGS "\$@" -O3
EOF
# fba wrapper — FBA2012 family needs:
#  -fsigned-char       MIPS chars are unsigned by default; FBA's old code assumes
#                      signed. (Crash/wrong behaviour without it.)
#  -fno-strict-aliasing  its CPU cores type-pun heavily.
#  NO -mdspr2          the DSP ASE codegen makes FBA's fixed-point sound/blit emit
#                      an instruction this device faults on (SIGILL a few frames
#                      into a game). Drop it for FBA only; -Ofast is kept.
# Flags appended AFTER "$@" so the core Makefile's trailing -O2 can't re-enable
# strict aliasing.
FBA_FLAGS="$(echo "$SF3000_FLAGS" | sed 's/-mdspr2 //')"
FBA_FIX="-fno-strict-aliasing -fsigned-char"
cat > "$WRAP/fba-gcc" <<EOF
#!/bin/bash
exec ${MIPS}gcc $FBA_FLAGS "\$@" $FBA_FIX
EOF
cat > "$WRAP/fba-g++" <<EOF
#!/bin/bash
exec ${MIPS}g++ $FBA_FLAGS "\$@" $FBA_FIX
EOF
chmod +x "$WRAP"/mips-gcc "$WRAP"/mips-g++ "$WRAP"/gpsp-gcc "$WRAP"/gpsp-g++ \
         "$WRAP"/mips-gcc-O3 "$WRAP"/mips-g++-O3 "$WRAP"/fba-gcc "$WRAP"/fba-g++

AR="${MIPS}ar"
RANLIB="${MIPS}ranlib"
STRIP="${MIPS}strip"
LDFLAGS="-mips32r2 -mhard-float -mfp32 -EL --sysroot=$SYSROOT -L$SYSROOT/usr/lib -lm -lc -lstdc++"
LDFLAGS_C="-mips32r2 -mhard-float -mfp32 -EL --sysroot=$SYSROOT -L$SYSROOT/usr/lib -lm -lc"
# LDFLAGS_S: for cores whose Makefile uses $(LDFLAGS) for the link rule and don't add -shared themselves
LDFLAGS_S="-shared -Wl,--no-undefined -mips32r2 -mhard-float -mfp32 -EL --sysroot=$SYSROOT -L$SYSROOT/usr/lib -lm -lc -lstdc++"
LDFLAGS_SC="-shared -Wl,--no-undefined -mips32r2 -mhard-float -mfp32 -EL --sysroot=$SYSROOT -L$SYSROOT/usr/lib -lm -lc"

_b() {
    local name="$1" dir="$2" mk="${3:-}" extra="${4:-}"
    # CC_WRAP lets a caller swap the compiler wrapper (e.g. fba-g++); default mips.
    local cw="${CC_WRAP:-mips}"
    echo "-- $name make --"
    local full="$CORES/$dir"
    make -C "$full" $mk clean 2>/dev/null || true
    make -C "$full" $mk platform=unix \
        CC="$WRAP/$cw-gcc" CXX="$WRAP/$cw-g++" \
        AR="$AR" RANLIB="$RANLIB" LD="$WRAP/$cw-g++" \
        LDFLAGS="$LDFLAGS" $extra -j$(nproc) 2>&1
    local so
    for so in \
        "$full/${name}_libretro.so" \
        "$full/$(basename "$dir")_libretro.so"; do
        [ -f "$so" ] && cp "$so" "$OUT/${name}_libretro.so" && \
            "$STRIP" "$OUT/${name}_libretro.so" && \
            echo "→ $OUT/${name}_libretro.so" && return
    done
    echo "WARNING: .so not found for $name"
}

# ── tzubertowski forks ────────────────────────────────────────────────────────
echo "-- fceumm make --"
_b fceumm            fceumm                    "-f Makefile.libretro"

echo "-- quicknes make --"
_b quicknes          QuickNES_Core             ""

echo "-- snes9x2005 make --"
# snes9x2005's unix Makefile path hardcodes -O2 (the -Ofast block is ARM-only),
# overriding our wrapper's -Ofast. Build with the -O3 wrappers so -O3 wins.
_b snes9x2005_plus   snes9x2005                "" "CC=$WRAP/mips-gcc-O3 CXX=$WRAP/mips-g++-O3"

echo "-- snes9x2002 make --"
_b snes9x2002        snes9x2002                ""

echo "-- gambatte make --"
_b gambatte          libretro-gambatte         "-f Makefile.libretro"

# gpsp: pre-cpp branch, platform=sf3000 — tzubertowski's dedicated target with
# MMAP_JIT_CACHE + -fPIC + -nostdlib for the MIPS dynarec. (platform=unix used
# the generic config and produced a broken dynarec: bad memory base, EWRAM fault.)
# gpsp (multicore fork) → gpsp_multicore_libretro.so  (used by the `gbac` folder)
echo "-- gpsp (multicore) make --"
make -C "$CORES/gpsp" clean 2>/dev/null || true
make -C "$CORES/gpsp" platform=sf3000 \
    CC="$WRAP/gpsp-gcc" CXX="$WRAP/gpsp-g++" \
    AR="$AR" RANLIB="$RANLIB" LD="$WRAP/gpsp-gcc" \
    LDFLAGS="$LDFLAGS_C" -j$(nproc) 2>&1
[ -f "$CORES/gpsp/gpsp_libretro.so" ] && \
    cp "$CORES/gpsp/gpsp_libretro.so" "$OUT/gpsp_multicore_libretro.so" && \
    "$STRIP" "$OUT/gpsp_multicore_libretro.so" && echo "→ $OUT/gpsp_multicore_libretro.so"

# gpsp (upstream libretro/gpsp) → gpsp_libretro.so  (default, used by `gba`).
# video.cc is C++ so the final link must use g++ (+libstdc++); the Makefile link
# rule uses $(CC), so we compile with gcc/g++ then relink the target with g++.
echo "-- gpsp (upstream) make --"
make -C "$CORES/gpsp_upstream" clean 2>/dev/null || true
make -C "$CORES/gpsp_upstream" platform=sf3000 \
    CC="$WRAP/gpsp-gcc" CXX="$WRAP/gpsp-g++" \
    AR="$AR" RANLIB="$RANLIB" -j$(nproc) 2>&1 || true
rm -f "$CORES/gpsp_upstream/gpsp_libretro.so"
make -C "$CORES/gpsp_upstream" platform=sf3000 \
    CC="$WRAP/gpsp-g++" CXX="$WRAP/gpsp-g++" \
    AR="$AR" RANLIB="$RANLIB" \
    LDFLAGS="$LDFLAGS_C -lstdc++" gpsp_libretro.so 2>&1
[ -f "$CORES/gpsp_upstream/gpsp_libretro.so" ] && \
    cp "$CORES/gpsp_upstream/gpsp_libretro.so" "$OUT/gpsp_libretro.so" && \
    "$STRIP" "$OUT/gpsp_libretro.so" && echo "→ $OUT/gpsp_libretro.so"

# ── standard cores ────────────────────────────────────────────────────────────
echo "-- picodrive make --"
_b picodrive         picodrive                 "-f Makefile.libretro"

echo "-- mgba make --"
_b mgba              mgba                      "-f Makefile.libretro"

echo "-- genesis-plus-gx make --"
_b genesis_plus_gx   Genesis-Plus-GX           "-f Makefile.libretro"

echo "-- tyrquake make --"
_b tyrquake          tyrquake                  ""

echo "-- prboom make --"
_b prboom            libretro-prboom           ""

echo "-- pico286 standalone DOS/PC make --"
# Standalone binary (not a libretro .so). Builds with its own self-locating
# script; output is cores/pico-286/pico286 -> copy to cubegm/ on the SD card.
if [ -d "$CORES/pico-286/port_sf3000" ]; then
    bash "$CORES/pico-286/port_sf3000/build.sh" 2>&1 | tail -2
    [ -f "$CORES/pico-286/pico286" ] && cp "$CORES/pico-286/pico286" "$OUT/pico286" && echo "→ $OUT/pico286"
else
    echo "WARNING: cores/pico-286/port_sf3000 missing (run clone_cores.sh + _apply_patch)"
fi

echo "-- TIC-80 fantasy console (cmake) make --"
# CMake cross-build. Needs cmake (set $CMAKE, default 'cmake') + the vendor
# submodules. Output: tic80_libretro.so.
if [ -d "$CORES/TIC-80" ]; then
    CMAKE="${CMAKE:-cmake}"
    if command -v "$CMAKE" >/dev/null; then
        git -C "$CORES/TIC-80" submodule update --init --depth 1 --recursive 2>&1 | tail -1
        cat > /tmp/tic80_mips.cmake <<EOF
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR mips)
set(CMAKE_C_COMPILER   ${MIPS}gcc)
set(CMAKE_CXX_COMPILER ${MIPS}g++)
set(CMAKE_SYSROOT ${SYSROOT})
set(FL "-mips32r2 -march=mips32r2 -mtune=74kc -mdspr2 -mfp32 -mhard-float -mlong-calls -EL")
set(CMAKE_C_FLAGS_INIT   "\${FL}")
set(CMAKE_CXX_FLAGS_INIT "\${FL}")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
EOF
        rm -rf /tmp/tic80_build
        "$CMAKE" -S "$CORES/TIC-80" -B /tmp/tic80_build \
            -DCMAKE_TOOLCHAIN_FILE=/tmp/tic80_mips.cmake -DCMAKE_BUILD_TYPE=Release \
            -DBUILD_LIBRETRO=ON -DBUILD_SDL=OFF -DBUILD_PLAYER=OFF -DBUILD_EDITORS=OFF \
            -DBUILD_PRO=OFF -DBUILD_WITH_ALL=OFF >/dev/null 2>&1
        "$CMAKE" --build /tmp/tic80_build --target tic80_libretro -j$(nproc) 2>&1 | tail -1
        [ -f /tmp/tic80_build/bin/tic80_libretro.so ] && \
            cp /tmp/tic80_build/bin/tic80_libretro.so "$OUT/tic80_libretro.so" && \
            "$STRIP" "$OUT/tic80_libretro.so" && echo "→ $OUT/tic80_libretro.so"
    else
        echo "WARNING: cmake not found ($CMAKE); skipping TIC-80"
    fi
fi

echo "-- mame2000 make --"
_b mame2000          mame2000                  ""

echo "-- FB Alpha 2012 arcade (CPS-1 / CPS-2 / Neo Geo) make --"
# CC_WRAP=fba → -fsigned-char + -fno-strict-aliasing (else segfault at game load)
CC_WRAP=fba _b fbalpha2012_cps1   fbalpha2012_cps1   ""
CC_WRAP=fba _b fbalpha2012_cps2   fbalpha2012_cps2   ""
# CPS-3 is experimental on this CPU: SH-2 interpreter, expect low fps on heavy titles.
# Repo layout differs from the other splits: source in svn-current/trunk, explicit makefile.
CC_WRAP=fba _b fbalpha2012_cps3   fbalpha2012_cps3/svn-current/trunk   "-f makefile.libretro"
CC_WRAP=fba _b fbalpha2012_neogeo fbalpha2012_neogeo ""

echo "-- mame2003-plus make (modern MAME, much bigger library) --"
# Makefile adds -shared via LDFLAGS+=; our command-line LDFLAGS would override
# and kill it (links as exe → undefined `main`), so pass the -shared variant.
_b mame2003_plus     mame2003-plus-libretro    "" "LDFLAGS=$LDFLAGS_S"

echo "-- FBNeo make (modern CPS/NeoGeo, heavier; fba wrapper for signed-char) --"
# Needs -lpthread (Cave CV1000 epic12 threaded blitter uses sem_*/pthread_*);
# this sysroot's glibc keeps them in a separate libpthread. Our command-line
# LDFLAGS overrides the Makefile's own += -lpthread, so re-add it here.
CC_WRAP=fba _b fbneo FBNeo/src/burner/libretro  "" "LDFLAGS=$LDFLAGS_S -lpthread"

echo "-- stella2014 make --"
_b stella2014        stella2014                "" "LDFLAGS=$LDFLAGS_S"

echo "-- prosystem make --"
_b prosystem         prosystem                 "" "LDFLAGS=$LDFLAGS_S"

echo "-- nestopia make --"
_b nestopia          nestopia/libretro         ""

echo "-- tgbdual make --"
_b tgbdual           libretro-tgbdual          ""

echo "-- gearboy make --"
_b gearboy           Gearboy/platforms/libretro ""

echo "-- pokemini make --"
_b pokemini          PokeMini                  ""

echo "-- vba-next make --"
_b vba_next          vba-next                  ""

echo "-- cannonball make --"
_b cannonball        cannonball                "" "LDFLAGS=$LDFLAGS_S"

echo "-- ecwolf make --"
git -C "$CORES/ecwolf" submodule update --init --depth=1 src/libretro/libretro-common 2>/dev/null || true
_b ecwolf            ecwolf/src/libretro       "" "LDFLAGS=$LDFLAGS_S"

# ecwolf needs its own engine resource pack (fonts/UI, not id Software's game
# data) at runtime or it fails with "Could not open ecwolf.pk3!". It's just
# wadsrc/static zipped with a .pk3 extension - build it here instead of
# needing ecwolf's full CMake build.
if [ -d "$CORES/ecwolf/wadsrc/static" ]; then
    python3 -c "
import zipfile, os
os.chdir('$CORES/ecwolf/wadsrc/static')
with zipfile.ZipFile('$OUT/ecwolf.pk3', 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk('.'):
        for f in files:
            full = os.path.join(root, f)
            zf.write(full, os.path.relpath(full, '.'))
"
    [ -f "$OUT/ecwolf.pk3" ] && echo "→ $OUT/ecwolf.pk3"
fi

echo "-- pocketcdg make --"
_b pocketcdg         libretro-pocketcdg        ""

echo "-- race make --"
_b race              RACE                      ""

echo "-- beetle-pce-fast make --"
_b mednafen_pce_fast libretro-beetle-pce-fast  "" "LDFLAGS=$LDFLAGS_S"

echo "-- beetle-wswan make --"
_b mednafen_wswan    libretro-beetle-wswan     "" "LDFLAGS=$LDFLAGS_S"

echo "-- beetle-lynx make --"
_b mednafen_lynx     libretro-beetle-lynx      "" "LDFLAGS=$LDFLAGS_S"

echo "-- beetle-vb make --"
_b mednafen_vb       libretro-beetle-vb        "" "LDFLAGS=$LDFLAGS_S"

echo "-- beetle-supergrafx make --"
_b mednafen_supergrafx libretro-beetle-supergrafx "" "LDFLAGS=$LDFLAGS_S"

echo "-- beetle-pcfx make --"
_b mednafen_pcfx     libretro-beetle-pcfx      "" "LDFLAGS=$LDFLAGS_S -lpthread"

echo "-- handy make --"
_b handy             libretro-handy            ""

echo "-- a5200 make --"
_b a5200             a5200                     ""

echo "-- 81 make --"
_b 81                libretro-81               ""

echo "-- fuse make --"
_b fuse              libretro-fuse             ""

# vecx needs OpenGL — skip on SF3000
# _b vecx              libretro-vecx             ""

echo "-- potator make --"
_b potator           potator/platform/libretro ""

echo "-- theodore make --"
_b theodore          theodore                  ""

echo "-- gearcoleco make --"
_b gearcoleco        Gearcoleco/platforms/libretro ""

echo "-- gearsystem make --"
_b gearsystem        Gearsystem/platforms/libretro ""

echo "-- freechaf make --"
git -C "$CORES/FreeChaF" submodule update --init --depth=1 src/deps/libretro-common 2>/dev/null || true
_b freechaf          FreeChaF                  "" "LDFLAGS=$LDFLAGS_SC"

echo "-- freeintv make --"
_b freeintv          FreeIntv                  ""

echo "-- gme make --"
_b gme               libretro-gme              ""

echo "-- cap32 make --"
_b cap32             libretro-cap32            ""

echo "-- crocods make --"
_b crocods           libretro-crocods          ""

# arduous (Arduboy): cmake project, but built directly here (no cmake on host).
# Bundles simavr (git submodule) + arduous + libretro glue into one .so.
echo "-- arduous make --"
(
  AD="$CORES/arduous"
  # simavr's per-instruction interpreter is call-heavy → drop -mlong-calls (the
  # call thunks dominate its hot loop) and add -fomit-frame-pointer for speed.
  ADFLAGS="-mips32r2 -march=mips32r2 -mtune=74kc -mdspr2 -mfp32 -mhard-float -EL --sysroot=$SYSROOT -fPIC -Ofast -fomit-frame-pointer -DNDEBUG"
  ACC="${MIPS}gcc $ADFLAGS"
  ACXX="${MIPS}g++ $ADFLAGS"
  if [ -d "$AD" ]; then
    git -C "$AD" submodule update --init simavr >/dev/null 2>&1
    AINC="-I$AD/include -I$AD/simavr/simavr/sim -I$AD/simavr/simavr/cores -I$AD/examples/parts -I$AD/simavr/examples/parts -I$AD/src"
    AOBJ=""; n=0; ok=1
    SIM="avr_acomp avr_adc avr_bitbang avr_eeprom avr_extint avr_flash avr_ioport avr_lin avr_spi avr_timer avr_twi avr_uart avr_usb avr_watchdog sim_avr sim_cmds sim_core sim_cycle_timers sim_hex sim_interrupts sim_io sim_irq sim_utils sim_vcd_file"
    for f in $SIM; do o="$AD/_ao_$n.o"; $ACC $AINC -std=gnu99 -c "$AD/simavr/simavr/sim/$f.c" -o "$o" || ok=0; AOBJ="$AOBJ $o"; n=$((n+1)); done
    for f in "simavr/simavr/cores/sim_mega32u4.c" "simavr/examples/parts/ssd1306_virt.c" "src/sim_fake_gdb.c"; do o="$AD/_ao_$n.o"; $ACC $AINC -std=gnu99 -c "$AD/$f" -o "$o" || ok=0; AOBJ="$AOBJ $o"; n=$((n+1)); done
    for f in "src/arduous/arduous.cpp" "src/arduous/speaker.cpp" "src/libretro/libretro.cpp"; do o="$AD/_ao_$n.o"; $ACXX $AINC -std=c++11 -c "$AD/$f" -o "$o" || ok=0; AOBJ="$AOBJ $o"; n=$((n+1)); done
    if [ "$ok" = 1 ]; then
      ${MIPS}g++ -EL --sysroot=$SYSROOT -fPIC -shared -Wl,--version-script="$AD/link.T" $AOBJ -o "$AD/arduous_libretro.so" -lc -lm && \
        cp "$AD/arduous_libretro.so" "$OUT/" && "$STRIP" "$OUT/arduous_libretro.so" && echo "→ $OUT/arduous_libretro.so"
    else
      echo "arduous: compile failed — skipped"
    fi
    rm -f "$AD"/_ao_*.o
  fi
)

# Ardens (Arduboy FX): custom fast AVR core (not simavr) — much faster than
# arduous. CMake project, but built directly here (no cmake on host). libretro
# target is C++14 (GCC 6.3 OK). Header-only deps come from submodules.
echo "-- ardens make --"
(
  AR_DIR="$CORES/Ardens"
  if [ -d "$AR_DIR" ]; then
    git -C "$AR_DIR" submodule update --init --depth=1 deps/bitsery deps/miniz deps/yyjson >/dev/null 2>&1 || true
    ARARCH="-mips32r2 -march=mips32r2 -mtune=74kc -mdspr2 -mfp32 -mhard-float -EL --sysroot=$SYSROOT -fPIC -O3 -fomit-frame-pointer -DNDEBUG"
    ARDEFS="-DMINIZ_NO_STDIO=1 -DMINIZ_NO_TIME=1 -DARDENS_PLAYER -DARDENS_NO_DEBUGGER -DARDENS_NO_GUI -DARDENS_NO_SAVED_SETTINGS -DARDENS_NO_SCALING -DARDENS_VERSION_MAJOR=1 -DARDENS_VERSION_MINOR=0 -DARDENS_VERSION_PATCH=0 -DARDENS_VERSION=\"1.0.0-sf3000\""
    ARINC="-I$AR_DIR/src -I$AR_DIR/src/libretro_core -I$AR_DIR/deps -I$AR_DIR/deps/miniz -I$AR_DIR/deps/bitsery/include"
    arobj=""; k=0; arok=1
    ARCPP="absim_cpu_data absim_dwarf absim_dwarf_expr absim_arduboy absim_decode absim_merge_instrs absim_execute absim_disassemble absim_load_file absim_reset absim_snapshot absim_led"
    for f in $ARCPP; do o="$AR_DIR/_ar_$k.o"; ${MIPS}g++ $ARARCH -std=gnu++14 $ARDEFS $ARINC -c "$AR_DIR/src/$f.cpp" -o "$o" || arok=0; arobj="$arobj $o"; k=$((k+1)); done
    o="$AR_DIR/_ar_$k.o"; ${MIPS}g++ $ARARCH -std=gnu++14 $ARDEFS $ARINC -c "$AR_DIR/src/libretro_core/libretro_impl.cpp" -o "$o" || arok=0; arobj="$arobj $o"; k=$((k+1))
    for f in deps/yyjson/yyjson deps/miniz/miniz deps/miniz/miniz_tdef deps/miniz/miniz_tinfl deps/miniz/miniz_zip \
             src/boot/boot_flashcart src/boot/boot_game_d1 src/boot/boot_game_d2 src/boot/boot_game_e2 \
             src/boot/boot_menu_d1 src/boot/boot_menu_d2 src/boot/boot_menu_e2; do
      o="$AR_DIR/_ar_$k.o"; ${MIPS}gcc $ARARCH -std=gnu11 $ARDEFS $ARINC -c "$AR_DIR/$f.c" -o "$o" || arok=0; arobj="$arobj $o"; k=$((k+1))
    done
    if [ "$arok" = 1 ]; then
      ${MIPS}g++ $ARARCH -shared -Wl,--version-script="$AR_DIR/src/libretro_core/link.T" $arobj -o "$AR_DIR/ardens_libretro.so" -lc -lm && \
        cp "$AR_DIR/ardens_libretro.so" "$OUT/" && "$STRIP" "$OUT/ardens_libretro.so" && echo "→ $OUT/ardens_libretro.so"
    else
      echo "ardens: compile failed — skipped"
    fi
    rm -f "$AR_DIR"/_ar_*.o
  fi
)

echo "-- gw make --"
_b gw                libretro-gw               ""

echo "-- xrick make --"
_b xrick             libretro-xrick            ""

echo "-- reminiscence make --"
_b reminiscence      REminiscence              ""

# o2em not included (clone skipped)
# _b o2em              libretro-o2em             ""

echo "-- nxengine make --"
_b nxengine          libretro-nxengine         ""

echo "-- jumpnbump make --"
_b jumpnbump         libretro-jumpnbump        ""

echo "-- lowres-nx make --"
_b lowresnx          lowres-nx/platform/LibRetro ""

echo "-- retro8 make --"
_b retro8            retro8                    ""

echo "-- fake08 make --"
git -C "$CORES/fake-08" submodule update --init --recursive 2>/dev/null || true
# fake08's Makefile appends -O2 (platform=unix) which would override our -Ofast.
# Build with the -O3 wrappers so the trailing -O3 wins (PICO-8 is a hot Lua VM).
_b fake08            fake-08/platform/libretro "" "CC=$WRAP/mips-gcc-O3 CXX=$WRAP/mips-g++-O3"

echo "-- pcsx_rearmed make (PS1, lightrec JIT) --"
# Needs libpicofe submodule; lightrec JIT enabled (patched: GNU lightning MIPS
# function-restart fix + old-kernel mmap fallbacks — see patches/).
git -C "$CORES/pcsx_rearmed" submodule update --init --depth=1 frontend/libpicofe 2>/dev/null || true
make -C "$CORES/pcsx_rearmed" -f Makefile.libretro clean 2>/dev/null || true
make -C "$CORES/pcsx_rearmed" -f Makefile.libretro platform=unix \
    CC="$WRAP/mips-gcc" CXX="$WRAP/mips-g++" CC_AS="$WRAP/mips-gcc" CC_LINK="$WRAP/mips-g++" \
    AR="$AR" ARCH=mips DYNAREC=lightrec HAVE_NEON=0 BUILTIN_GPU=unai -j"$(nproc)" 2>&1
if [ -f "$CORES/pcsx_rearmed/pcsx_rearmed_libretro.so" ]; then
    cp "$CORES/pcsx_rearmed/pcsx_rearmed_libretro.so" "$OUT/pcsx_rearmed_libretro.so"
    "$STRIP" "$OUT/pcsx_rearmed_libretro.so"
    echo "→ $OUT/pcsx_rearmed_libretro.so"
else
    echo "WARNING: .so not found for pcsx_rearmed"
fi

echo "-- gong make --"
_b gong              gong                      "-f Makefile.libretro"

echo "-- quasi88 make --"
_b quasi88           libretro-quasi88          ""

echo "-- geolith make --"
# LTO disabled in libretro-geolith/libretro/Makefile (R_MIPS_HI16 PIC issue with GCC 6.3 LTO)
_b geolith           libretro-geolith/libretro "" "LDFLAGS=$LDFLAGS_S"

echo "-- xmil make --"
_b x68k              libretro-xmil/libretro    ""

echo "-- atari800 make --"
_b atari800          libretro-atari800         "-f Makefile.libretro"

# echo "-- vice x64 make --"
# _b vice_x64          libretro-vice             "" "EMUTYPE=x64"

# echo "-- vice x64sc make --"
# _b vice_x64sc        libretro-vice             "" "EMUTYPE=x64sc"

# echo "-- vice xvic make --"
# _b vice_xvic         libretro-vice             "" "EMUTYPE=xvic"

# frodo (C64, folders c64f / c64fc): needs Src/libretro-common submodule, NOLIBCO=1
# (libco path leaves ThePrefs undeclared), and --allow-multiple-definition (gui .cpp
# redefine strdup/strncasecmp). The bundled Src/zlib has no committed objects, but
# the toolchain defaults to big-endian — the -EL in $WRAP fixes that.
echo "-- frodo make --"
git -C "$CORES/libretro-frodo" submodule update --init --recursive 2>/dev/null || true
# Apply local fixes (idempotent): RGB565-shared autoload guard + auto-LOAD on boot.
git -C "$CORES/libretro-frodo" apply --check "$(pwd)/patches/frodo-sf3000-autoload-r36sx.patch" 2>/dev/null \
    && git -C "$CORES/libretro-frodo" apply "$(pwd)/patches/frodo-sf3000-autoload-r36sx.patch" \
    && echo "  applied frodo-sf3000-autoload-r36sx.patch"
make -C "$CORES/libretro-frodo" clean 2>/dev/null || true
find "$CORES/libretro-frodo" -name "*.o" -delete 2>/dev/null || true
make -C "$CORES/libretro-frodo" platform=unix NOLIBCO=1 \
    CC="$WRAP/mips-gcc" CXX="$WRAP/mips-g++" \
    AR="$AR" RANLIB="$RANLIB" LD="$WRAP/mips-g++" \
    LDFLAGS="$LDFLAGS_S -Wl,--allow-multiple-definition" -j$(nproc) 2>&1
[ -f "$CORES/libretro-frodo/frodo_libretro.so" ] && \
    cp "$CORES/libretro-frodo/frodo_libretro.so" "$OUT/" && \
    "$STRIP" "$OUT/frodo_libretro.so" && echo "→ $OUT/frodo_libretro.so" || \
    echo "WARNING: .so not found for frodo"

# ── angree SF2000 ports (Amiga/Mac/AtariST) — libretro .so build ──────────────
_b_angree() {
    local name="$1" dir="$2" mk="$3"
    echo "-- $name make --"
    local full="$CORES/$dir"
    make -C "$full" $mk clean 2>/dev/null || true
    make -C "$full" $mk \
        CC="$WRAP/mips-gcc" CXX="$WRAP/mips-g++" \
        AR="$AR" RANLIB="$RANLIB" LD="$WRAP/mips-g++" \
        LDFLAGS="$LDFLAGS_SC" -j$(nproc) 2>&1
    local so
    for so in \
        "$full/${name}_libretro.so" \
        "$full/$(basename "$dir")_libretro.so"; do
        [ -f "$so" ] && cp "$so" "$OUT/${name}_libretro.so" && \
            "$STRIP" "$OUT/${name}_libretro.so" && \
            echo "→ $OUT/${name}_libretro.so" && return
    done
    echo "WARNING: .so not found for $name"
}

echo "-- uae amiga make --"
# fs_posix.c shim provides POSIX fs_* implementations; needs -lz for zlib.
# Makefile.libretro links the final .so with $(CC) not $(CXX), so the C++
# object files (disk.cpp etc, std::string) need -lstdc++ added explicitly.
make -C "$CORES/sf2000-uae-amiga-emulator" -f Makefile.libretro clean 2>/dev/null || true
make -C "$CORES/sf2000-uae-amiga-emulator" -f Makefile.libretro \
    CC="$WRAP/mips-gcc" CXX="$WRAP/mips-g++" \
    AR="$AR" RANLIB="$RANLIB" LD="$WRAP/mips-g++" \
    LDFLAGS="$LDFLAGS_SC -lz -lstdc++" -j$(nproc) 2>&1
[ -f "$CORES/sf2000-uae-amiga-emulator/uae4all_libretro.so" ] && \
    cp "$CORES/sf2000-uae-amiga-emulator/uae4all_libretro.so" "$OUT/uae_libretro.so" && \
    "$STRIP" "$OUT/uae_libretro.so" && echo "→ $OUT/uae_libretro.so"

echo "-- castaway atari-st make --"
_b_angree castaway    sf2000-atarist-emulator                "-f Makefile.libretro"

echo ""
echo "Done. Built cores:"
ls "$OUT"/*.so 2>/dev/null | xargs -I{} basename {}
