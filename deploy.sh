#!/bin/bash
# Deploy: refresh staging from build outputs, then mirror staging → physical SD.
# Run from sf3000_treefrogui root.
set -e
cd "$(dirname "$0")"

STAGE="sdcard"
PICOARCH=/home/tomaszz/sf3000-work/picoarch/picoarch
PICOARCH_HI=/home/tomaszz/sf3000-work/picoarch/picoarch_hi
FROGUI=/home/tomaszz/sf3000-work/FrogUI/frogui_libretro.so
TYRQUAKE=/home/tomaszz/sf3000-work/tyrquake-og/tyrquake_libretro.so

# 1) Refresh staging from latest build artifacts
[ -f "$PICOARCH" ]    && cp "$PICOARCH"    "$STAGE/cubegm/picoarch"
[ -f "$PICOARCH_HI" ] && cp "$PICOARCH_HI" "$STAGE/cubegm/picoarch_hi"
[ -f "$FROGUI" ]      && cp "$FROGUI"      "$STAGE/cubegm/cores/frogui_libretro.so"
[ -f "$TYRQUAKE" ]    && cp "$TYRQUAKE"    "$STAGE/cubegm/cores/tyrquake_libretro.so"
echo "Staging refreshed from build outputs."

# 2) Find mounted SF3000 SD (vfat under /run/media/$USER with a cubegm/ dir)
SD=""
for m in /run/media/"$USER"/*; do
    [ -d "$m/cubegm" ] && SD="$m" && break
done
# Fresh-formatted SD won't have cubegm yet — fall back to any vfat mount
if [ -z "$SD" ]; then
    for m in /run/media/"$USER"/*; do
        [ -d "$m" ] && SD="$m" && break
    done
fi

if [ -z "$SD" ]; then
    echo "No SD card mounted under /run/media/$USER — staging updated only."
    exit 0
fi

echo "Mirroring staging → $SD"
rsync -a --info=progress2 "$STAGE"/cubegm "$STAGE"/frogui "$SD"/
sync
echo "Deployed to $SD"
