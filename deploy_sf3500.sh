#!/usr/bin/env bash
#
# Root-only, guarded full-release deploy helper for an SF3500 card.
#
# Build the release as the normal user, then run this through polkit:
#   ./build_release.sh
#   pkexec /home/tomaszz/sf3000-work/sf3000_treefrogui/deploy_sf3500.sh
#
# The SF3500 stock boot files are fingerprinted before deployment and verified
# unchanged afterward. The universal payload is merged first, followed by the
# required SF3500 install_first overlay. Nothing is mirrored with --delete.
set -euo pipefail

readonly REPO=/home/tomaszz/sf3000-work/sf3000_treefrogui
readonly RELEASE="$REPO/release"
readonly OVERLAY="$RELEASE/install_first/sf3500"
readonly MOUNT=/mnt/sf3500
readonly EXPECTED_LABEL=SF3500
readonly OWNER_UID=1000
readonly OWNER_GID=1000

die() {
    echo "deploy-sf3500: $*" >&2
    exit 1
}

[ "$EUID" -eq 0 ] || die "run through pkexec"

for tool in blkid findmnt fsck.vfat lsblk mount mountpoint readlink rsync sha256sum sync umount; do
    command -v "$tool" >/dev/null || die "required command is missing: $tool"
done

for path in \
    "$RELEASE/cubegm" \
    "$RELEASE/frogui" \
    "$RELEASE/roms" \
    "$RELEASE/MD" \
    "$OVERLAY/cubegm/setting.xml" \
    "$OVERLAY/cubegm/cores/libemu_md.so" \
    "$OVERLAY/cubegm/zhijack.sh"; do
    [ -e "$path" ] || die "release is incomplete; missing $path (run ./build_release.sh)"
done

grep -q 'TF_DEVICE=SF3500' "$OVERLAY/cubegm/zhijack.sh" ||
    die "SF3500 launcher identity is missing"
grep -q 'file="/mnt/sdcard/MD/dummy.md" driver=""' \
    "$OVERLAY/cubegm/setting.xml" ||
    die "SF3500 autorun overlay is invalid"

# Resolve only by the exact volume label. SF3500 images use a whole-disk VFAT
# filesystem, although a partitioned replacement card is accepted too.
DEV="$(blkid -L "$EXPECTED_LABEL" 2>/dev/null || true)"
[ -n "$DEV" ] || die "card labelled $EXPECTED_LABEL not found"
DEV="$(readlink -f "$DEV")"
case "$DEV" in
    /dev/sd[a-z]|/dev/sd[a-z][0-9]*|/dev/mmcblk[0-9]|/dev/mmcblk[0-9]p[0-9]*) ;;
    *) die "refusing unexpected device path: $DEV" ;;
esac
[ "$(lsblk -dnro RM "$DEV")" = "1" ] || die "$DEV is not removable"
case "$(lsblk -dnro TYPE "$DEV")" in
    disk|part) ;;
    *) die "$DEV is neither a disk nor a partition" ;;
esac
[ "$(lsblk -dnro FSTYPE "$DEV")" = "vfat" ] || die "$DEV is not VFAT"
[ "$(lsblk -dnro LABEL "$DEV")" = "$EXPECTED_LABEL" ] ||
    die "$DEV label changed"

[ ! -L "$MOUNT" ] || die "refusing symlink mountpoint: $MOUNT"
mkdir -p "$MOUNT"

mounted_here=0
cleanup() {
    if [ "$mounted_here" -eq 1 ] && mountpoint -q "$MOUNT"; then
        sync
        umount "$MOUNT"
        mounted_here=0
        echo "Unmounted $DEV; the SF3500 card is safe to remove."
    fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# Clear any desktop/udisks mount of this exact validated device.
while IFS= read -r old_mount; do
    [ -z "$old_mount" ] || umount "$old_mount"
done < <(findmnt -rn -S "$DEV" -o TARGET)

check_filesystem() {
    local fsck_rc
    echo "Checking the unmounted SF3500 FAT filesystem..."
    set +e
    fsck.vfat -a "$DEV"
    fsck_rc=$?
    set -e
    [ "$fsck_rc" -le 1 ] || die "fsck.vfat failed with status $fsck_rc"
}

mount_card() {
    if ! mount -t vfat \
        -o rw,uid="$OWNER_UID",gid="$OWNER_GID",fmask=0022,dmask=0022,flush \
        "$DEV" "$MOUNT"; then
        return 1
    fi
    mounted_here=1
}

repair_and_mount() {
    if mountpoint -q "$MOUNT"; then
        umount "$MOUNT"
        mounted_here=0
    fi
    check_filesystem
    mount_card
}

# A damaged FAT volume can initially report rw and only flip read-only during a
# large transfer. Check it while unmounted before putting any release files on it.
check_filesystem

if ! mount_card; then
    echo "Initial mount failed; repairing the validated SF3500 FAT filesystem."
    repair_and_mount
fi

mount_opts="$(findmnt -rn -S "$DEV" -o OPTIONS)"
case ",$mount_opts," in
    *,rw,*) ;;
    *)
        echo "Card mounted read-only; repairing the validated SF3500 FAT filesystem."
        repair_and_mount
        mount_opts="$(findmnt -rn -S "$DEV" -o OPTIONS)"
        case ",$mount_opts," in
            *,rw,*) ;;
            *) die "$DEV remained read-only after fsck" ;;
        esac
        ;;
esac

[ -d "$MOUNT/cubegm" ] || die "not an SF3500 system card: cubegm/ is missing"

readonly -a STOCK_FILES=(
    cubegm/icube
    cubegm/rkgame
    cubegm/driver.so
)
declare -A stock_hashes=()
for rel in "${STOCK_FILES[@]}"; do
    [ -f "$MOUNT/$rel" ] || die "stock file is missing: $rel"
    hash_line="$(sha256sum "$MOUNT/$rel")"
    stock_hashes["$rel"]="${hash_line%% *}"
done

echo "Deploying the complete TreeFrogUI release to $DEV..."

# Merge the universal payload. Do not delete ROMs, saves, settings, or stock OS
# files that are not present in the release.
for dir in cubegm frogui roms MD; do
    rsync -rltc "$RELEASE/$dir" "$MOUNT/"
done

# User-facing release files are useful on the card too. install_first itself is
# deliberately excluded; only the selected SF3500 overlay belongs at the root.
for name in README.md theme.md LICENSE.md INSTALL.md picoarch.cfg; do
    [ ! -f "$RELEASE/$name" ] || rsync -tc "$RELEASE/$name" "$MOUNT/"
done
[ ! -d "$RELEASE/docs" ] || rsync -rltc "$RELEASE/docs" "$MOUNT/"

# The overlay supplies the device-specific autorun, hijack core, boot logo, and
# launcher. It must be applied after the universal payload.
rsync -rltc "$OVERLAY/" "$MOUNT/"

# This watchdog marker requests the old software-render fallback. It is generated
# at runtime if hardware presentation actually fails and must not survive a full
# deployment of the fixed SF3500 renderer.
if [ -e "$MOUNT/cubegm/force_sw.flag" ]; then
    rm -f -- "$MOUNT/cubegm/force_sw.flag"
    echo "Removed stale cubegm/force_sw.flag."
fi

sync

verify_tree() {
    local src="$1" dst="$2" description="$3" remaining
    remaining="$(rsync -rcni "$src" "$dst" | sed '/^$/d')"
    [ -z "$remaining" ] ||
        die "$description verification found differences: $remaining"
}

for dir in cubegm frogui roms MD; do
    verify_tree "$RELEASE/$dir" "$MOUNT/" "$dir"
done
verify_tree "$OVERLAY/" "$MOUNT/" "SF3500 overlay"

for name in README.md theme.md LICENSE.md INSTALL.md picoarch.cfg; do
    [ ! -f "$RELEASE/$name" ] ||
        verify_tree "$RELEASE/$name" "$MOUNT/" "$name"
done
[ ! -d "$RELEASE/docs" ] ||
    verify_tree "$RELEASE/docs" "$MOUNT/" "docs"

for rel in "${STOCK_FILES[@]}"; do
    hash_line="$(sha256sum "$MOUNT/$rel")"
    deployed_hash="${hash_line%% *}"
    [ "$deployed_hash" = "${stock_hashes[$rel]}" ] ||
        die "protected stock file changed: $rel"
    echo "Stock preserved: $rel  $deployed_hash"
done

for rel in \
    cubegm/picoarch \
    cubegm/picoarch_hi \
    cubegm/cores/frogui_libretro.so \
    cubegm/cores/libemu_md.so \
    cubegm/zhijack.sh; do
    hash_line="$(sha256sum "$MOUNT/$rel")"
    echo "Verified: $rel  ${hash_line%% *}"
done

echo "Complete SF3500 TreeFrogUI release deployed and verified."
