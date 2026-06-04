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
    local patch="patches/$1" dir="cores/$2"
    [ -f "$patch" ] || return
    if git -C "$dir" apply --check "$patch" 2>/dev/null; then
        git -C "$dir" apply "$patch" && echo "patched $2"
    else
        echo "patch already applied or conflict: $1 (skipping)"
    fi
}
_apply_patch geolith-no-lto.patch      libretro-geolith
_apply_patch uae-posix-fs.patch        sf2000-uae-amiga-emulator
_apply_patch castaway-linux-build.patch sf2000-atarist-emulator
_apply_patch fake08-cpp17-gcc6.patch   fake-08
_apply_patch pcsx_rearmed-sf3000-lightrec.patch pcsx_rearmed

TOOLCHAIN="$HOME/sf3000-work/sf3000toolchain/mipsel-buildroot-linux-gnu_sdk-buildroot"
MIPS="$TOOLCHAIN/opt/ext-toolchain/bin/mips-mti-linux-gnu-"
SYSROOT="$TOOLCHAIN/mipsel-buildroot-linux-gnu/sysroot"
OUT="$(pwd)/build"
CORES="$(pwd)/cores"
WRAP="$(pwd)/.toolchain"

mkdir -p "$OUT" "$WRAP"

# ── Compiler wrappers ─────────────────────────────────────────────────────────
SF3000_FLAGS="-mips32r2 -march=mips32r2 -mtune=24kc -mfp32 -mhard-float -mlong-calls -EL --sysroot=$SYSROOT -Ofast -DNDEBUG"

cat > "$WRAP/mips-gcc" <<EOF
#!/bin/bash
exec ${MIPS}gcc $SF3000_FLAGS "\$@"
EOF
cat > "$WRAP/mips-g++" <<EOF
#!/bin/bash
exec ${MIPS}g++ $SF3000_FLAGS "\$@"
EOF
# gpsp wrapper — no arch flags (platform=mips32 sets them), only sysroot
cat > "$WRAP/gpsp-gcc" <<EOF
#!/bin/bash
exec ${MIPS}gcc --sysroot=$SYSROOT -isystem $SYSROOT/usr/include -fPIC "\$@"
EOF
cat > "$WRAP/gpsp-g++" <<EOF
#!/bin/bash
exec ${MIPS}g++ --sysroot=$SYSROOT -isystem $SYSROOT/usr/include -fPIC "\$@"
EOF
chmod +x "$WRAP"/mips-gcc "$WRAP"/mips-g++ "$WRAP"/gpsp-gcc "$WRAP"/gpsp-g++

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
    echo "-- $name make --"
    local full="$CORES/$dir"
    make -C "$full" $mk clean 2>/dev/null || true
    make -C "$full" $mk platform=unix \
        CC="$WRAP/mips-gcc" CXX="$WRAP/mips-g++" \
        AR="$AR" RANLIB="$RANLIB" LD="$WRAP/mips-g++" \
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
_b snes9x2005_plus   snes9x2005                ""

echo "-- snes9x2002 make --"
_b snes9x2002        snes9x2002                ""

echo "-- gambatte make --"
_b gambatte          libretro-gambatte         "-f Makefile.libretro"

# gpsp: pre-cpp branch, platform=sf3000 — tzubertowski's dedicated target with
# MMAP_JIT_CACHE + -fPIC + -nostdlib for the MIPS dynarec. (platform=unix used
# the generic config and produced a broken dynarec: bad memory base, EWRAM fault.)
echo "-- gpsp make --"
make -C "$CORES/gpsp" clean 2>/dev/null || true
make -C "$CORES/gpsp" platform=sf3000 \
    CC="$WRAP/gpsp-gcc" CXX="$WRAP/gpsp-g++" \
    AR="$AR" RANLIB="$RANLIB" LD="$WRAP/gpsp-gcc" \
    LDFLAGS="$LDFLAGS_C" -j$(nproc) 2>&1
[ -f "$CORES/gpsp/gpsp_libretro.so" ] && \
    cp "$CORES/gpsp/gpsp_libretro.so" "$OUT/" && \
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

echo "-- mame2000 make --"
_b mame2000          mame2000                  ""

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
  if [ -d "$AD" ]; then
    git -C "$AD" submodule update --init simavr >/dev/null 2>&1
    AINC="-I$AD/include -I$AD/simavr/simavr/sim -I$AD/simavr/simavr/cores -I$AD/examples/parts -I$AD/simavr/examples/parts -I$AD/src"
    AOBJ=""; n=0; ok=1
    SIM="avr_acomp avr_adc avr_bitbang avr_eeprom avr_extint avr_flash avr_ioport avr_lin avr_spi avr_timer avr_twi avr_uart avr_usb avr_watchdog sim_avr sim_cmds sim_core sim_cycle_timers sim_hex sim_interrupts sim_io sim_irq sim_utils sim_vcd_file"
    for f in $SIM; do o="$AD/_ao_$n.o"; "$WRAP/mips-gcc" $AINC -std=gnu99 -c "$AD/simavr/simavr/sim/$f.c" -o "$o" || ok=0; AOBJ="$AOBJ $o"; n=$((n+1)); done
    for f in "simavr/simavr/cores/sim_mega32u4.c" "simavr/examples/parts/ssd1306_virt.c" "src/sim_fake_gdb.c"; do o="$AD/_ao_$n.o"; "$WRAP/mips-gcc" $AINC -std=gnu99 -c "$AD/$f" -o "$o" || ok=0; AOBJ="$AOBJ $o"; n=$((n+1)); done
    for f in "src/arduous/arduous.cpp" "src/arduous/speaker.cpp" "src/libretro/libretro.cpp"; do o="$AD/_ao_$n.o"; "$WRAP/mips-g++" $AINC -std=c++11 -c "$AD/$f" -o "$o" || ok=0; AOBJ="$AOBJ $o"; n=$((n+1)); done
    if [ "$ok" = 1 ]; then
      "$WRAP/mips-g++" -fPIC -shared -Wl,--version-script="$AD/link.T" $AOBJ -o "$AD/arduous_libretro.so" -lc -lm && \
        cp "$AD/arduous_libretro.so" "$OUT/" && "$STRIP" "$OUT/arduous_libretro.so" && echo "→ $OUT/arduous_libretro.so"
    else
      echo "arduous: compile failed — skipped"
    fi
    rm -f "$AD"/_ao_*.o
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
_b fake08            fake-08/platform/libretro ""

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
# fs_posix.c shim provides POSIX fs_* implementations; needs -lz for zlib
make -C "$CORES/sf2000-uae-amiga-emulator" -f Makefile.libretro clean 2>/dev/null || true
make -C "$CORES/sf2000-uae-amiga-emulator" -f Makefile.libretro \
    CC="$WRAP/mips-gcc" CXX="$WRAP/mips-g++" \
    AR="$AR" RANLIB="$RANLIB" LD="$WRAP/mips-g++" \
    LDFLAGS="$LDFLAGS_SC -lz" -j$(nproc) 2>&1
[ -f "$CORES/sf2000-uae-amiga-emulator/uae4all_libretro.so" ] && \
    cp "$CORES/sf2000-uae-amiga-emulator/uae4all_libretro.so" "$OUT/uae_libretro.so" && \
    "$STRIP" "$OUT/uae_libretro.so" && echo "→ $OUT/uae_libretro.so"

echo "-- castaway atari-st make --"
_b_angree castaway    sf2000-atarist-emulator                "-f Makefile.libretro"

echo ""
echo "Done. Built cores:"
ls "$OUT"/*.so 2>/dev/null | xargs -I{} basename {}
