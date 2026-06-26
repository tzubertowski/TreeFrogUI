#!/bin/bash
# Build the unified TreeFrogUI release: release/
#
# ONE package for R36SX / SF3000 / SF3500. Boot is unified on the rkgame autorun
# hijack — the stock boot chain (icube + rkgame, both verified on SF3500) is
# NEVER touched on any device:
#
#   stock boot -> rkgame -> setting.xml <autorun> -> libemu_tfhijack.so
#     -> retro_load_game() execl's zhijack.sh -> picoarch/frogui
#
# Layout:
#   release/cubegm,frogui,MAME   universal payload (zero stock files) — copy to SD
#   release/install_first/<dev>/ per-device rkgame xml (setting/config/filelist)
#                                + the autorun trigger — user copies THEIR device's
#   release/INSTALL.md           guide
set -e
cd "$(dirname "$0")"

STAGE=sdcard
HIJACK=hijack
OUT=release
CORE_FILE="libemu_tfhijack.so"
ROM_REL="MAME/treefrogui.zip"

PICOARCH=/home/tomaszz/sf3000-work/picoarch/picoarch
PICOARCH_HI=/home/tomaszz/sf3000-work/picoarch/picoarch_hi
FROGUI=/home/tomaszz/sf3000-work/FrogUI/frogui_libretro.so
TYRQUAKE=/home/tomaszz/sf3000-work/tyrquake-og/tyrquake_libretro.so

# device name -> stock cubegm path (for generating per-device xml)
declare -A STOCK=(
  [r36sx]=/home/tomaszz/sf3000-work/R36SX_sdcard/cubegm
  [sf3000]=/home/tomaszz/sf3000-work/SF3000_sdcard/SF3000_sdcard/cubegm
  [sf3500]=/home/tomaszz/sf3000-work/SF3500_sdcard_v1.1/cubegm
  # SF3000_HD = HDMI-out variant. Same SoC/panel(854x480)/disp_frame as SF3500,
  # byte-identical encrypted driver.so, identical config/filelist. It even detects
  # AS SF3500 at runtime (has /panel) and loads driver_sf3500.so — correct. This
  # folder just gives HD owners a labelled, ready-to-copy xml set.
  [sf3000hd]=/home/tomaszz/sf3000-work/SF3000_HD_sdcard_v1.1/cubegm
  # SF3100 = yet another SF3500-clone. Encrypted driver.so is BYTE-IDENTICAL to
  # SF3500/HD (same md5), config/filelist identical, 854x480 panel. Detects AS
  # SF3500 (has /panel, no multiple_init) and loads driver_sf3500.so — correct.
  [sf3100]=/home/tomaszz/sf3000-work/SF3100_sdcard/cubegm
  # GB350 = 640x480 4:3 device. /panel present but, alone among /panel devices,
  # lacks both multiple_init and uart@1 → detected as its own device. Plain-ELF
  # driver (NOT encrypted, unique) shipped as driver_gb350.so. config/filelist
  # identical to R36SX. Rides the SF3000 disp_frame path at 640x480.
  [gb350]=/home/tomaszz/sf3000-work/GB350_sdcard/cubegm
)

# 0) Refresh staging + build hijack core.
cp_if_diff() { [ -f "$1" ] || return 0; cmp -s "$1" "$2" && return 0; cp "$1" "$2"; }
cp_if_diff "$PICOARCH"    "$STAGE/cubegm/picoarch"
cp_if_diff "$PICOARCH_HI" "$STAGE/cubegm/picoarch_hi"
cp_if_diff "$FROGUI"      "$STAGE/cubegm/cores/frogui_libretro.so"
cp_if_diff "$TYRQUAKE"    "$STAGE/cubegm/cores/tyrquake_libretro.so"
sh "$HIJACK/build_tfhijack.sh" >/dev/null

rm -rf "$OUT"
mkdir -p "$OUT/cubegm/cores" "$OUT/cubegm/lib" "$OUT/$(dirname "$ROM_REL")"

# 1) Universal payload — our files only, NO stock, NO icube.
cp -a "$STAGE/cubegm/cores/." "$OUT/cubegm/cores/"
cp "$HIJACK/$CORE_FILE" "$OUT/cubegm/cores/$CORE_FILE"
for f in picoarch picoarch_hi driver_r36sx.so driver_sf3000.so driver_sf3500.so driver_gb350.so; do
    cp "$STAGE/cubegm/$f" "$OUT/cubegm/$f"
done
cp "$HIJACK/tf_detect.sh" "$OUT/cubegm/tf_detect.sh"   # tracked source (sdcard/ is gitignored)
cp "$HIJACK/zhijack.sh" "$OUT/cubegm/zhijack.sh"; chmod +x "$OUT/cubegm/zhijack.sh"
# only libs no stock device ships (SDL, png12). SD is FAT32 → NO symlinks: ship a
# REAL libSDL-1.2.so.0 (the soname the binaries link), cp -L dereferences the
# staging symlink. The .0.11.4 target name is not needed by anything.
cp -L "$STAGE/cubegm/lib/libSDL-1.2.so.0" "$OUT/cubegm/lib/libSDL-1.2.so.0"
cp    "$STAGE/cubegm/lib/libpng12.so.0"   "$OUT/cubegm/lib/libpng12.so.0"
[ -d "$STAGE/frogui" ] && cp -a "$STAGE/frogui" "$OUT/frogui"

# 1b) Our extra assets the old release shipped (these are OURS, not stock OS):
#     standalone frontends, BIOS, boot logos. NOT shipped: icube/icube_start
#     (retired boot), cubevol + generic driver.so (stock), *.bak / test bins (junk).
for x in lgpt lgpt.elf pcsx4all pico286 xgame-logo.bmp xgame-logo-sf3000.bmp; do
    [ -e "$STAGE/cubegm/$x" ] && cp -a "$STAGE/cubegm/$x" "$OUT/cubegm/$x"
done
[ -d "$STAGE/cubegm/bios" ] && cp -a "$STAGE/cubegm/bios" "$OUT/cubegm/bios"

# 1c) Top-level docs + user-facing files the old release had (authoritative
#     install steps live in the generated INSTALL.md below; old install.md is
#     dropped as it documents the retired icube method).
# User-facing docs come from the REPO ROOT (canonical, maintained) — the sdcard/
# copies are stale stubs. Assets (cfg, boot-logo fixers) come from staging.
for x in README.md install.md theme.md LICENSE.md; do
    [ -f "$x" ] && cp "$x" "$OUT/$x"
done
mkdir -p "$OUT/docs"
for x in cores.md release-notes.md onionos_gap.md ARCADE_CORES.md; do
    [ -f "$x" ] && cp "$x" "$OUT/docs/$x"
done
for x in picoarch.cfg fix_bootlogo_sf3000.sh fix_bootlogo_sf3000.bat; do
    [ -e "$STAGE/$x" ] && cp -a "$STAGE/$x" "$OUT/$x"
done

# dummy autorun rom (valid 22-byte empty zip; never read)
printf 'PK\x05\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' > "$OUT/$ROM_REL"

# 2) Per-device rkgame xml (stock base + our autorun/core/rom patches).
for dev in "${!STOCK[@]}"; do
    src="${STOCK[$dev]}"; dst="$OUT/install_first/$dev"
    [ -d "$src" ] || { echo "WARN: no stock for $dev ($src) — skipping"; continue; }
    mkdir -p "$dst/cubegm/cores"
    cp "$src/setting.xml"        "$dst/cubegm/setting.xml"
    cp "$src/cores/config.xml"   "$dst/cubegm/cores/config.xml"
    cp "$src/cores/filelist.xml" "$dst/cubegm/cores/filelist.xml"
    ST="$dst/cubegm/setting.xml"; CFG="$dst/cubegm/cores/config.xml"; FL="$dst/cubegm/cores/filelist.xml"
    sed -i "s#<autorun file=\"[^\"]*\" driver=\"[^\"]*\" />#<autorun file=\"$ROM_REL\" driver=\"$CORE_FILE\" />#" "$ST"
    grep -q "driver=\"$CORE_FILE\"" "$ST" || echo "  WARN[$dev]: autorun not patched"
    grep -q "$CORE_FILE" "$CFG" || sed -i "0,/<core>/s##<core>\n<emucore name=\"$CORE_FILE\" file=\"$CORE_FILE\" />\n<supported_extensions>ZIP</supported_extensions>\n</core>\n\n<core>#" "$CFG"
    grep -q "$ROM_REL"   "$FL"  || sed -i "1a <file name=\"$ROM_REL\" core=\"$CORE_FILE\" />" "$FL"
    echo "  install_first/$dev ready"
done

# 3) Guide.
cat > "$OUT/INSTALL.md" <<'EOF'
# TreeFrogUI — install (R36SX / SF3000 / SF3500)

Unified boot: the stock menu (rkgame) auto-launches TreeFrogUI via a hijack core.
The stock boot files (icube, rkgame) are never modified, so SF3500's boot verifier
stays happy.

## Steps
1. Start from a **stock card** for your device (if your card has an older TreeFrogUI
   that replaced `cubegm/icube`, restore the stock `icube` first).
2. Copy `cubegm/`, `frogui/`, `MAME/` onto the SD root (merge/overwrite).
3. Copy the contents of **`install_first/<your-device>/`** onto the SD root too:
   - `install_first/r36sx/`    → R36SX (v2.6 and v2.7 — same xml)
   - `install_first/sf3000/`   → SF3000
   - `install_first/sf3500/`   → SF3500
   - `install_first/sf3000hd/` → SF3000 HD (HDMI-out variant)
   - `install_first/sf3100/`   → SF3100
   - `install_first/gb350/`    → GB350
   (This sets the rkgame autorun + registers the hijack core for YOUR device.)
4. Eject, boot. The stock menu loads, then jumps straight into TreeFrogUI.

Diagnostics: `/mnt/sdcard/log.txt` (look for `=== zhijack boot`).
EOF

# 4) FAT32 guard — the SD has no symlink support; fail loudly if any slipped in.
syms=$(find "$OUT" -type l)
if [ -n "$syms" ]; then echo "ERROR: symlinks in release (FAT32 can't store these):"; echo "$syms"; exit 1; fi

echo
echo "=== $OUT ready (FAT32-safe, no symlinks) ==="
du -sh "$OUT"
find "$OUT" -maxdepth 3 -type d | sort
