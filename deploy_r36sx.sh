#!/usr/bin/env bash
#
# Root-only, guarded deploy helper for the R36SX development card.
#
# Run through polkit so Codex needs one reusable approval:
#   pkexec /home/tomaszz/sf3000-work/sf3000_treefrogui/deploy_r36sx.sh picoarch
#
# Accepted payloads:
#   picoarch, picoarch-hi, frogui, ebook, pcsx4all, pcsx4all-config, release
#
set -euo pipefail

readonly WORK=/home/tomaszz/sf3000-work
readonly REPO="$WORK/sf3000_treefrogui"
readonly STAGE="$REPO/sdcard"
readonly MOUNT=/mnt/r36sx

die() {
    echo "deploy-r36sx: $*" >&2
    exit 1
}

usage() {
    echo "usage: $0 {picoarch|picoarch-hi|frogui|ebook|pcsx4all|pcsx4all-config|release} [...]"
    exit 2
}

[ "$EUID" -eq 0 ] || die "run through pkexec"
[ "$#" -gt 0 ] || usage

# Resolve by the exact volume label, then reject anything that is not a
# removable VFAT partition. Never fall back to an arbitrary disk or mount.
DEV="$(blkid -L R36SX 2>/dev/null || true)"
[ -n "$DEV" ] || die "card labelled R36SX not found"
DEV="$(readlink -f "$DEV")"
case "$DEV" in
    /dev/sd[a-z][0-9]*|/dev/mmcblk[0-9]p[0-9]*) ;;
    *) die "refusing unexpected device path: $DEV" ;;
esac
[ "$(lsblk -dnro RM "$DEV")" = "1" ] || die "$DEV is not removable"
[ "$(lsblk -dnro TYPE "$DEV")" = "part" ] || die "$DEV is not a partition"
[ "$(lsblk -dnro FSTYPE "$DEV")" = "vfat" ] || die "$DEV is not VFAT"
[ "$(lsblk -dnro LABEL "$DEV")" = "R36SX" ] || die "$DEV label changed"

[ ! -L "$MOUNT" ] || die "refusing symlink mountpoint: $MOUNT"
mkdir -p "$MOUNT"

mounted_here=0
cleanup() {
    if [ "$mounted_here" -eq 1 ] && mountpoint -q "$MOUNT"; then
        sync
        umount "$MOUNT"
        echo "Unmounted $DEV; card is safe to remove."
    fi
}
trap cleanup EXIT INT TERM

# Clear an existing desktop/udisks mount of this exact validated card.
old_mount="$(findmnt -rn -S "$DEV" -o TARGET | head -n1 || true)"
if [ -n "$old_mount" ]; then
    umount "$DEV"
fi

mount_card() {
    mount -t vfat \
        -o rw,uid=1000,gid=1000,fmask=0022,dmask=0022,flush \
        "$DEV" "$MOUNT"
    mounted_here=1
}

mount_card
mount_opts="$(findmnt -rn -S "$DEV" -o OPTIONS)"
case ",$mount_opts," in
    *,rw,*) ;;
    *)
        # A dirty FAT volume may be mounted read-only. Repair only this already
        # validated, unmounted R36SX partition, then retry once.
        umount "$MOUNT"
        mounted_here=0
        set +e
        fsck.vfat -a "$DEV"
        fsck_rc=$?
        set -e
        [ "$fsck_rc" -le 1 ] || die "fsck.vfat failed with status $fsck_rc"
        mount_card
        mount_opts="$(findmnt -rn -S "$DEV" -o OPTIONS)"
        case ",$mount_opts," in
            *,rw,*) ;;
            *) die "$DEV remained read-only after fsck" ;;
        esac
        ;;
esac

[ -d "$MOUNT/cubegm" ] || die "not a TreeFrogUI card: cubegm/ is missing"

copy_one() {
    local name="$1" src dst src_hash dst_hash
    case "$name" in
        picoarch)
            src="$WORK/picoarch/picoarch"
            dst="$MOUNT/cubegm/picoarch"
            ;;
        picoarch-hi)
            src="$WORK/picoarch/picoarch_hi"
            dst="$MOUNT/cubegm/picoarch_hi"
            ;;
        frogui)
            src="$WORK/FrogUI/frogui_libretro.so"
            dst="$MOUNT/cubegm/cores/frogui_libretro.so"
            ;;
        ebook)
            src="$WORK/ebook/ebook"
            dst="$MOUNT/cubegm/ebook"
            ;;
        pcsx4all)
            src="$STAGE/cubegm/pcsx4all"
            dst="$MOUNT/cubegm/pcsx4all"
            ;;
        pcsx4all-config)
            src="$STAGE/cubegm/cores/.pcsx4all/pcsx4all.cfg"
            dst="$MOUNT/cubegm/cores/.pcsx4all/pcsx4all.cfg"
            ;;
        *) usage ;;
    esac

    [ -f "$src" ] || die "source missing: $src"
    [ -d "$(dirname "$dst")" ] || die "destination directory missing: $(dirname "$dst")"

    src_hash="$(sha256sum "$src" | cut -d' ' -f1)"
    if [ -f "$dst" ]; then
        dst_hash="$(sha256sum "$dst" | cut -d' ' -f1)"
        if [ "$src_hash" = "$dst_hash" ]; then
            echo "$name already current: $src_hash"
            return
        fi
    fi

    cp "$src" "$dst"
    sync "$dst"
    dst_hash="$(sha256sum "$dst" | cut -d' ' -f1)"
    [ "$src_hash" = "$dst_hash" ] || die "$name verification failed"
    echo "$name deployed: $dst_hash"
}

for payload in "$@"; do
    case "$payload" in
        release)
            [ -d "$STAGE/cubegm" ] || die "release staging missing"
            rsync -ac "$STAGE/cubegm" "$MOUNT/"
            [ ! -d "$STAGE/frogui" ] || rsync -ac "$STAGE/frogui" "$MOUNT/"
            sync
            remaining="$(
                {
                    rsync -rcni "$STAGE/cubegm" "$MOUNT/"
                    [ ! -d "$STAGE/frogui" ] || rsync -rcni "$STAGE/frogui" "$MOUNT/"
                } | sed '/^$/d'
            )"
            [ -z "$remaining" ] || die "release verification found differences: $remaining"
            echo "release staging deployed and verified"
            ;;
        picoarch|picoarch-hi|frogui|ebook|pcsx4all|pcsx4all-config)
            copy_one "$payload"
            ;;
        *) usage ;;
    esac
done
