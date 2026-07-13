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

# 1) Refresh staging from latest build artifacts (only when content differs —
#    avoid rewriting identical files and bumping their mtime)
cp_if_diff() {
    [ -f "$1" ] || return 0
    cmp -s "$1" "$2" && return 0
    cp "$1" "$2" && echo "  updated $2"
}
cp_if_diff "$PICOARCH"    "$STAGE/cubegm/picoarch"
cp_if_diff "$PICOARCH_HI" "$STAGE/cubegm/picoarch_hi"
cp_if_diff "$FROGUI"      "$STAGE/cubegm/cores/frogui_libretro.so"
cp_if_diff "$TYRQUAKE"    "$STAGE/cubegm/cores/tyrquake_libretro.so"
echo "Staging refreshed from build outputs."

# 2) Find mounted SF3000 SD: only a card that already has cubegm/ (an existing
#    TreeFrogUI/stock card). NO blind fallback — deploying to "any vfat mount"
#    once dumped the payload onto an unrelated camera card. For a fresh card,
#    create cubegm/ on it manually (or pass the mount as $1) to opt in.
SD="${1:-}"
if [ -z "$SD" ]; then
    for m in /run/media/"$USER"/*; do
        [ -d "$m/cubegm" ] && SD="$m" && break
    done
fi

if [ -z "$SD" ]; then
    echo "No card with cubegm/ mounted under /run/media/$USER — staging updated only."
    echo "(fresh card? run: $0 /run/media/$USER/<card>)"
    exit 0
fi
[ -d "$SD" ] || { echo "not a directory: $SD"; exit 1; }

echo "Mirroring staging → $SD"
# -c: compare by checksum, not mtime — skip files whose content already matches
rsync -ac --info=progress2 "$STAGE"/cubegm "$STAGE"/frogui "$SD"/
sync
echo "Deployed to $SD"
