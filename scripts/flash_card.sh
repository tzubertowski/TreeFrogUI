#!/bin/sh
# Clean TreeFrogUI install onto an SD card:
#   format FAT32  ->  device stock backup  ->  TreeFrogUI payload + install_first/<dev>
#
# Usage:   sudo sh scripts/flash_card.sh <r36sx|sf3000|sf3500>  [/dev/sdX]
#          (device defaults to /dev/sda)
#
# Stock backups are user-supplied full card dumps (rootfs + stock cubegm + media
# folders), NOT in this repo. They live under $WORK (default ~/sf3000-work);
# override with:  WORK=/path sudo -E sh scripts/flash_card.sh r36sx
#
# Run build_release.sh first so release/ exists.
set -e

DEV="${2:-/dev/sda}"
# Resolve paths from the script's own location (survives sudo, where $HOME=/root):
# scripts/ -> repo root -> workspace root.
SELF=$(readlink -f "$0")
REPO=$(dirname "$(dirname "$SELF")")
WORK="${WORK:-$(dirname "$REPO")}"
REL="$REPO/release"

case "$1" in
  r36sx)  BK="$WORK/R36SX_sdcard";                INST=r36sx;  LABEL=R36SX  ;;
  sf3000) BK="$WORK/SF3000_sdcard/SF3000_sdcard"; INST=sf3000; LABEL=SF3000 ;;
  sf3500) BK="$WORK/SF3500_sdcard_v1.1";          INST=sf3500; LABEL=SF3500 ;;
  *) echo "usage: sudo sh $0 <r36sx|sf3000|sf3500> [/dev/sdX]"; exit 1 ;;
esac

[ -d "$BK" ]                        || { echo "ABORT: stock backup not found: $BK"; exit 1; }
[ -d "$REL/install_first/$INST" ]   || { echo "ABORT: $REL/install_first/$INST missing (run build_release.sh)"; exit 1; }

# ---- safety: never touch a system disk ----
SZ=$(lsblk -bdno SIZE "$DEV") || { echo "ABORT: $DEV not found"; exit 1; }
[ "$SZ" -lt 64000000000 ] || { echo "ABORT: $DEV is $SZ bytes (>64G) - not an SD card"; exit 1; }
ROOTSRC=$(findmnt -no SOURCE / 2>/dev/null || true)
case "$ROOTSRC" in "$DEV"*) echo "ABORT: $DEV hosts the running root filesystem"; exit 1 ;; esac
echo ">> $1: target $DEV ($SZ bytes), backup $BK"

# ---- unmount every mountpoint of the device, then hard-verify ----
echo ">> unmounting $DEV ..."
fuser -km "$DEV" 2>/dev/null || true
umount -A "$DEV" 2>/dev/null || true
umount "$DEV"    2>/dev/null || true
if grep -q "^$DEV " /proc/mounts; then
    echo "ABORT: $DEV still mounted:"; grep "^$DEV " /proc/mounts; exit 1
fi

# ---- format ----
echo ">> formatting FAT32 ($LABEL) ..."
mkfs.vfat -F 32 -n "$LABEL" "$DEV"

MNT=/mnt/tf_install
mkdir -p "$MNT"
mount "$DEV" "$MNT"
echo ">> mounted at $MNT"

# cp -r (not -a): FAT has no Unix owner/perms, so -a's --preserve fails per-file
# and, under set -e, would abort. Backups are FAT-sourced (no symlinks) so -r is
# a faithful copy.
echo ">> [1/4] stock backup (rootfs + boot + stock cubegm) ..." ; cp -r "$BK/." "$MNT/"
echo ">> [2/4] TreeFrogUI cubegm + frogui overlay ..."          ; cp -r "$REL/cubegm/." "$MNT/cubegm/"; rm -rf "$MNT/frogui"; cp -r "$REL/frogui" "$MNT/frogui"
echo ">> [3/4] roms + MD ..."                                   ; cp -r "$REL/roms/." "$MNT/roms/"; cp -r "$REL/MD/." "$MNT/MD/"
echo ">> [4/4] install_first/$INST (autorun xml, hijack core, logo, zhijack) ..." ; cp -r "$REL/install_first/$INST/." "$MNT/"

sync
umount "$MNT"
echo ">> DONE. $LABEL card ready and unmounted - safe to remove."
