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
#   release/cubegm,frogui,roms,MD  universal payload (zero stock files) — copy to SD
#   release/install_first/<dev>/ per-device: rkgame setting.xml autorun, hijack
#                                core override, boot logo, and the device's
#                                GENERATED zhijack.sh (hardcoded device facts,
#                                no runtime detection) — user copies THEIR device's
#   release/INSTALL.md           guide
set -e
cd "$(dirname "$0")"

STAGE=sdcard
HIJACK=hijack
OUT=release
# WORKING autoboot recipe (confirmed on SF3500 hardware, see project_sf3500_hijack):
#   - autorun rom path must be ABSOLUTE (relative is silently ignored by rkgame)
#   - driver="" → rkgame resolves the core by the rom's EXTENSION via config.xml
#   - so we OVERRIDE the stock core for that extension with our hijack core.
# .md → libemu_md.so (picodrive) on every stock config.xml → override that one.
HIJACK_CORE="$HIJACK/libemu_tfhijack.so"  # built libretro stub that execl's zhijack
OVERRIDE_CORE="libemu_md.so"              # stock MD core we replace (.md extension)
DUMMY_REL="MD/dummy.md"                   # dummy rom (extension picks the core)
DUMMY_ABS="/mnt/sdcard/$DUMMY_REL"        # rkgame needs the ABSOLUTE path

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

# Per-device zhijack.sh facts (generated from hijack/zhijack.tpl.sh — NO runtime
# device detection on the SD). Geometry from the stock dtbs. RKGAME policy:
#   kill = killall before frogui/game (proven on SF-class disp_frame devices)
#   stop = SIGSTOP once at boot (R36SX: killing → icube respawns rkgame which
#          redraws over fb-write = flicker; leaving it RUNNING → it reacts to
#          SELECT+START (stock exit-game hotkey) and draws over the screen)
#            TF_DEVICE W   H   ASPECT ROT PRESENT   DRIVER            RKGAME
declare -A HJ=(
  [r36sx]="   R36SX    640 480 4  3   0   fbwrite   driver_r36sx.so   stop"
  [sf3000]="  SF3000   854 480 16 9   90  dispframe driver_sf3000.so  kill"
  [sf3500]="  SF3500   854 480 16 9   90  dispframe driver_sf3500.so  kill"
  [sf3000hd]="SF3500   854 480 16 9   90  dispframe driver_sf3500.so  kill"
  [sf3100]="  SF3500   854 480 16 9   90  dispframe driver_sf3500.so  kill"
  [gb350]="   GB350    640 480 4  3   0   dispframe driver_gb350.so   kill"
)

# 0) Refresh staging + build hijack core.
# Guard: picoarch_hi (gpsp/pcsx dynarec build of the SAME source) must not be older
# than picoarch — a stale hi carries old device detection → SF3500/HD mis-detect →
# wrong driver → gpsp/pcsx audio crash. build_sf3000.sh builds ONLY picoarch.
if [ "$PICOARCH" -nt "$PICOARCH_HI" ]; then
    echo "WARN: picoarch is newer than picoarch_hi — rebuild it: (cd ../picoarch && sh build_picoarch_hi.sh)"
fi
cp_if_diff() { [ -f "$1" ] || return 0; cmp -s "$1" "$2" && return 0; cp "$1" "$2"; }
cp_if_diff "$PICOARCH"    "$STAGE/cubegm/picoarch"
cp_if_diff "$PICOARCH_HI" "$STAGE/cubegm/picoarch_hi"
cp_if_diff "$FROGUI"      "$STAGE/cubegm/cores/frogui_libretro.so"
cp_if_diff "$TYRQUAKE"    "$STAGE/cubegm/cores/tyrquake_libretro.so"
sh "$HIJACK/build_tfhijack.sh" >/dev/null

rm -rf "$OUT"
mkdir -p "$OUT/cubegm/cores" "$OUT/cubegm/lib" "$OUT/$(dirname "$DUMMY_REL")"

# 1) Universal payload — our files only, NO stock, NO icube.
cp -a "$STAGE/cubegm/cores/." "$OUT/cubegm/cores/"
for f in picoarch picoarch_hi driver_r36sx.so driver_r36sx27.so driver_sf3000.so driver_sf3500.so driver_gb350.so; do
    cp "$STAGE/cubegm/$f" "$OUT/cubegm/$f"
done
# zhijack.sh is per-device (generated into install_first/<dev>/cubegm/ below) —
# the universal payload deliberately ships NO launcher and NO device detection.
# only libs no stock device ships (SDL, png12). SD is FAT32 → NO symlinks: ship a
# REAL libSDL-1.2.so.0 (the soname the binaries link), cp -L dereferences the
# staging symlink. The .0.11.4 target name is not needed by anything.
cp -L "$STAGE/cubegm/lib/libSDL-1.2.so.0" "$OUT/cubegm/lib/libSDL-1.2.so.0"
cp    "$STAGE/cubegm/lib/libpng12.so.0"   "$OUT/cubegm/lib/libpng12.so.0"
# ppsspp_libretro.so links libpng16 (not the png12 the rest of the world uses);
# its assets ride along automatically via the cubegm/bios/PPSSPP staging copy.
cp    "$STAGE/cubegm/lib/libpng16.so.16"  "$OUT/cubegm/lib/libpng16.so.16"
[ -d "$STAGE/frogui" ] && cp -a "$STAGE/frogui" "$OUT/frogui"
# roms/ folder structure (the system subfolders FrogUI expects: gba, nes, snes…).
# Ships empty folders + their .res/filelist scaffolding; users drop ROMs in.
[ -d "$STAGE/roms" ] && cp -a "$STAGE/roms" "$OUT/roms"

# 1b) Our extra assets the old release shipped (these are OURS, not stock OS):
#     standalone frontends, BIOS, boot logos. NOT shipped: icube/icube_start
#     (retired boot), cubevol + generic driver.so (stock), *.bak / test bins (junk).
# (boot logos are NOT shipped here — install_first/<dev>/ provides the device-correct
#  xgame-logo.bmp, so no fix_bootlogo script is needed.)
for x in lgpt lgpt.elf pcsx4all pico286; do
    [ -e "$STAGE/cubegm/$x" ] && cp -a "$STAGE/cubegm/$x" "$OUT/cubegm/$x"
done
[ -d "$STAGE/cubegm/bios" ] && cp -a "$STAGE/cubegm/bios" "$OUT/cubegm/bios"

# 1c) Top-level docs + user-facing files the old release had (authoritative
#     install steps live in the generated INSTALL.md below; old install.md is
#     dropped as it documents the retired icube method).
# User-facing docs come from the REPO ROOT (canonical, maintained) — the sdcard/
# copies are stale stubs. Assets (picoarch.cfg) come from staging.
for x in README.md install.md theme.md LICENSE.md; do
    [ -f "$x" ] && cp "$x" "$OUT/$x"
done
mkdir -p "$OUT/docs"
for x in cores.md release-notes.md onionos_gap.md ARCADE_CORES.md; do
    [ -f "$x" ] && cp "$x" "$OUT/docs/$x"
done
for x in picoarch.cfg; do
    [ -e "$STAGE/$x" ] && cp -a "$STAGE/$x" "$OUT/$x"
done

# Dummy autorun rom at the absolute path rkgame loads, + its folder catalog entry
# (filename,Display Name,SHORTCODE). The .md extension makes rkgame pick libemu_md.so
# — which install_first overrides with our hijack core.
printf 'TF' > "$OUT/$DUMMY_REL"
printf 'dummy.md,TreeFrogUI,MD\n' > "$OUT/$(dirname "$DUMMY_REL")/filelist.csv"

# 2) Per-device install_first — the WORKING hijack recipe:
#   a) setting.xml autorun -> ABSOLUTE dummy path, driver="" (extension-resolved)
#   b) cores/libemu_md.so OVERRIDDEN with our hijack core (so .md -> our core)
# We do NOT touch config.xml/filelist.xml — stock already maps .md -> libemu_md.so,
# and the override + driver="" is what actually boots (explicit driver=, relative
# paths, and a new core name all silently failed on hardware).
for dev in "${!STOCK[@]}"; do
    src="${STOCK[$dev]}"; dst="$OUT/install_first/$dev"
    [ -d "$src" ] || { echo "WARN: no stock for $dev ($src) — skipping"; continue; }
    mkdir -p "$dst/cubegm/cores"
    cp "$src/setting.xml" "$dst/cubegm/setting.xml"
    ST="$dst/cubegm/setting.xml"
    sed -i "s#<autorun file=\"[^\"]*\" driver=\"[^\"]*\" />#<autorun file=\"$DUMMY_ABS\" driver=\"\" />#" "$ST"
    grep -q "file=\"$DUMMY_ABS\" driver=\"\"" "$ST" || echo "  WARN[$dev]: autorun not patched"
    cp "$HIJACK_CORE" "$dst/cubegm/cores/$OVERRIDE_CORE"
    #   c) device-correct boot logo (cubegm/xgame-logo.bmp). 640x480 panels (R36SX,
    #      GB350) use the original; 854x480 panels (SF3000/HD/SF3100/SF3500) use the
    #      SF3000-format one. Shipping it here replaces the old fix_bootlogo script.
    case "$dev" in
        r36sx|gb350) logo="$STAGE/cubegm/xgame-logo.bmp" ;;
        *)           logo="$STAGE/cubegm/xgame-logo-sf3000.bmp" ;;
    esac
    [ -f "$logo" ] && cp "$logo" "$dst/cubegm/xgame-logo.bmp"
    #   d) the device's zhijack.sh, generated from the template with everything
    #      hardcoded (device, panel, driver, rkgame-kill policy). No DT probing.
    read -r DEV PW PH ASPN ASPD ROT PRESENT DRIVER KILL <<< "${HJ[$dev]}"
    [ -n "$DEV" ] || { echo "  WARN[$dev]: no HJ entry — no zhijack generated"; continue; }
    sed -e "s/@DEV_LABEL@/$dev/g" -e "s/@DEV@/$DEV/g" -e "s/@PW@/$PW/g" \
        -e "s/@PH@/$PH/g" -e "s/@ASPN@/$ASPN/g" -e "s/@ASPD@/$ASPD/g" \
        -e "s/@ROT@/$ROT/g" -e "s/@PRESENT@/$PRESENT/g" -e "s/@DRIVER@/$DRIVER/g" \
        "$HIJACK/zhijack.tpl.sh" > "$dst/cubegm/zhijack.sh"
    # Boot block (freeze icube + kill rkgame) is universal. Loop killalls stay
    # only on kill-policy devices (harmless no-op belt on SF-class); r36sx runs
    # the tested no-loop-kill config.
    if [ "$KILL" = stop ]; then
        sed -i '/#@KILL@/d' "$dst/cubegm/zhijack.sh"
    else
        sed -i 's/ #@KILL@//' "$dst/cubegm/zhijack.sh"
    fi
    # R36SX-only block (@R36@: driver self-selection). Non-R36SX-only block
    # (@HW@: HW-render watchdog → force SW). R36SX renders via fb-write and has
    # no SW-transpose fallback tuned for its panel, so it never force-SWs.
    if [ "$dev" = r36sx ]; then
        sed -i -e 's/ #@R36@//' -e '/#@HW@/d' "$dst/cubegm/zhijack.sh"
    else
        sed -i -e '/#@R36@/d' -e 's/ #@HW@//' "$dst/cubegm/zhijack.sh"
    fi
    grep -q '@' "$dst/cubegm/zhijack.sh" && grep -o '@[A-Z_]*@' "$dst/cubegm/zhijack.sh" | sort -u | sed "s/^/  WARN[$dev]: unfilled /"
    chmod +x "$dst/cubegm/zhijack.sh"
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
2. Copy `cubegm/`, `frogui/`, `roms/`, `MD/` onto the SD root (merge/overwrite).
3. Copy the contents of **`install_first/<your-device>/`** onto the SD root too
   (REQUIRED: it carries the launcher script and autorun setup for your device):
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

# 5) Release sanity checks — fail loudly instead of shipping a broken package.
fail() { echo "ERROR: $1"; exit 1; }
[ -f "$OUT/cubegm/zhijack.sh" ] && fail "payload must not ship a generic zhijack.sh"
[ -f "$OUT/cubegm/tf_detect.sh" ] && fail "payload must not ship tf_detect.sh (detection retired)"
# every device: boot block = freeze icube + kill rkgame (STOP no-ops without icube)
for dev in "${!STOCK[@]}"; do
    grep -q 'kill -STOP $(pidof icube)' "$OUT/install_first/$dev/cubegm/zhijack.sh" \
        || fail "$dev zhijack must SIGSTOP icube at boot"
done
# r36sx: boot killall only, no loop kills (tested config)
[ "$(grep -c 'killall rkgame' "$OUT/install_first/r36sx/cubegm/zhijack.sh")" = 1 ] \
    || fail "r36sx zhijack must contain exactly 1 killall rkgame (boot block only)"
for dev in sf3000 sf3500 sf3000hd sf3100 gb350; do
    [ "$(grep -c 'killall rkgame' "$OUT/install_first/$dev/cubegm/zhijack.sh")" = 3 ] \
        || fail "$dev zhijack must contain 3 killall rkgame (boot + 2 loop)"
done
for dev in "${!STOCK[@]}"; do
    [ -x "$OUT/install_first/$dev/cubegm/zhijack.sh" ] || fail "missing zhijack for $dev"
    [ -f "$OUT/install_first/$dev/cubegm/cores/$OVERRIDE_CORE" ] || fail "missing hijack core for $dev"
done
[ -f "$OUT/$DUMMY_REL" ] || fail "missing autorun dummy rom $DUMMY_REL"

echo
echo "=== $OUT ready (FAT32-safe, no symlinks, sanity checks passed) ==="
du -sh "$OUT"
find "$OUT" -maxdepth 3 -type d | sort
echo
last=$(ls TreeFrogUI_v*_?.zip 2>/dev/null | sort | tail -1)
echo "To package: zip -qr TreeFrogUI_vX.Y.Z_?.zip $OUT   (latest existing: ${last:-none})"
