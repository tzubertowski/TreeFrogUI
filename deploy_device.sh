#!/usr/bin/env bash
#
# Guarded in-place TreeFrogUI deployment for supported device cards.
#
# Usage:
#   ./build_release.sh
#   pkexec ./deploy.sh <r36sx|sf3000|sf3500> [payload ...]
#
# With no payload, the complete release plus the selected install_first overlay
# is deployed. Optional development payloads:
#   release, picoarch, picoarch-hi, frogui, ebook, pcsx4all, pcsx4all-config
#
# This script never formats a card and never uses rsync --delete.
set -euo pipefail

readonly WORK=/home/tomaszz/sf3000-work
readonly REPO="$WORK/sf3000_treefrogui"
readonly RELEASE="$REPO/release"
readonly STAGE="$REPO/sdcard"
readonly OWNER_UID=1000
readonly OWNER_GID=1000

die() {
    echo "deploy-device: $*" >&2
    exit 1
}

usage() {
    cat >&2 <<EOF
usage: $0 <r36sx|sf3000|sf3500> [payload ...]
payloads: release picoarch picoarch-hi frogui ebook pcsx4all pcsx4all-config
default:  release
EOF
    exit 2
}

[ "$#" -ge 1 ] || usage

readonly PROFILE="$1"
shift

case "$PROFILE" in
    r36sx)
        readonly EXPECTED_LABEL=R36SX
        readonly EXPECTED_TF_DEVICE=R36SX
        readonly CLEAR_FORCE_SW=0
        ;;
    sf3000)
        readonly EXPECTED_LABEL=SF3000
        readonly EXPECTED_TF_DEVICE=SF3000
        readonly CLEAR_FORCE_SW=1
        ;;
    sf3500)
        readonly EXPECTED_LABEL=SF3500
        readonly EXPECTED_TF_DEVICE=SF3500
        readonly CLEAR_FORCE_SW=1
        ;;
    *) usage ;;
esac

readonly MOUNT="/mnt/treefrog-$PROFILE"
readonly OVERLAY="$RELEASE/install_first/$PROFILE"

if [ "$#" -eq 0 ]; then
    set -- release
fi
readonly -a PAYLOADS=("$@")

for payload in "${PAYLOADS[@]}"; do
    case "$payload" in
        release|picoarch|picoarch-hi|frogui|ebook|pcsx4all|pcsx4all-config) ;;
        *) usage ;;
    esac
done

[ "$EUID" -eq 0 ] || die "run through pkexec"

for tool in blkid dirname findmnt fsck.vfat grep lsblk mkdir mount mountpoint \
    readlink rm rsync sed sha256sum sync umount; do
    command -v "$tool" >/dev/null || die "required command is missing: $tool"
done

validate_release() {
    local path
    for path in \
        "$RELEASE/cubegm" \
        "$RELEASE/frogui" \
        "$RELEASE/roms" \
        "$RELEASE/MD" \
        "$OVERLAY/cubegm/setting.xml" \
        "$OVERLAY/cubegm/cores/libemu_md.so" \
        "$OVERLAY/cubegm/zhijack.sh"; do
        [ -e "$path" ] ||
            die "release is incomplete; missing $path (run ./build_release.sh)"
    done

    grep -q "TF_DEVICE=$EXPECTED_TF_DEVICE" \
        "$OVERLAY/cubegm/zhijack.sh" ||
        die "$PROFILE launcher identity is invalid"
    grep -q 'file="/mnt/sdcard/MD/dummy.md" driver=""' \
        "$OVERLAY/cubegm/setting.xml" ||
        die "$PROFILE autorun overlay is invalid"
}

for payload in "${PAYLOADS[@]}"; do
    [ "$payload" != release ] || validate_release
done

# Resolve only by the selected profile's exact volume label. Both whole-disk
# VFAT images and partitioned replacement cards are supported.
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
        echo "Unmounted $DEV; the $EXPECTED_LABEL card is safe to remove."
    fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# Clear desktop/udisks mounts of this exact validated device.
while IFS= read -r old_mount; do
    [ -z "$old_mount" ] || umount "$old_mount"
done < <(findmnt -rn -S "$DEV" -o TARGET)

check_filesystem() {
    local fsck_rc
    echo "Checking the unmounted $EXPECTED_LABEL FAT filesystem..."
    set +e
    fsck.vfat -a "$DEV"
    fsck_rc=$?
    set -e
    [ "$fsck_rc" -le 1 ] ||
        die "fsck.vfat failed with status $fsck_rc"
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

# Dirty FAT can initially report rw and only flip read-only under a large copy.
# Check it while unmounted before every deployment.
check_filesystem

if ! mount_card; then
    echo "Initial mount failed; repairing the validated $EXPECTED_LABEL card."
    repair_and_mount
fi

mount_opts="$(findmnt -rn -S "$DEV" -o OPTIONS)"
case ",$mount_opts," in
    *,rw,*) ;;
    *)
        echo "Card mounted read-only; repairing the validated $EXPECTED_LABEL card."
        repair_and_mount
        mount_opts="$(findmnt -rn -S "$DEV" -o OPTIONS)"
        case ",$mount_opts," in
            *,rw,*) ;;
            *) die "$DEV remained read-only after fsck" ;;
        esac
        ;;
esac

[ -d "$MOUNT/cubegm" ] ||
    die "not a $EXPECTED_LABEL system card: cubegm/ is missing"

# Every supported stock image has these boot files. TreeFrogUI must never alter
# them; only setting.xml, the hijack core, logo, and our own files are replaced.
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

verify_tree() {
    local src="$1" dst="$2" description="$3" remaining
    remaining="$(rsync -rcni "$src" "$dst" | sed '/^$/d')"
    [ -z "$remaining" ] ||
        die "$description verification found differences: $remaining"
}

deploy_release() {
    local dir name rel hash_line

    echo "Deploying the complete $PROFILE TreeFrogUI release to $DEV..."

    # Merge only: preserve ROMs, saves, settings, and stock files not present in
    # the release.
    for dir in cubegm frogui roms MD; do
        rsync -rltc "$RELEASE/$dir" "$MOUNT/"
    done

    # install_first itself stays out of the card root. Only this profile's
    # selected overlay is applied.
    for name in README.md theme.md LICENSE.md INSTALL.md picoarch.cfg; do
        [ ! -f "$RELEASE/$name" ] ||
            rsync -tc "$RELEASE/$name" "$MOUNT/"
    done
    [ ! -d "$RELEASE/docs" ] ||
        rsync -rltc "$RELEASE/docs" "$MOUNT/"
    rsync -rltc "$OVERLAY/" "$MOUNT/"

    # SF-class devices use the hardware presentation watchdog. A marker from an
    # older failed test must not pin a newly fixed build to software rendering.
    if [ "$CLEAR_FORCE_SW" -eq 1 ] &&
        [ -e "$MOUNT/cubegm/force_sw.flag" ]; then
        rm -f -- "$MOUNT/cubegm/force_sw.flag"
        echo "Removed stale cubegm/force_sw.flag."
    fi

    sync

    for dir in cubegm frogui roms MD; do
        verify_tree "$RELEASE/$dir" "$MOUNT/" "$dir"
    done
    verify_tree "$OVERLAY/" "$MOUNT/" "$PROFILE overlay"

    for name in README.md theme.md LICENSE.md INSTALL.md picoarch.cfg; do
        [ ! -f "$RELEASE/$name" ] ||
            verify_tree "$RELEASE/$name" "$MOUNT/" "$name"
    done
    [ ! -d "$RELEASE/docs" ] ||
        verify_tree "$RELEASE/docs" "$MOUNT/" "docs"

    for rel in \
        cubegm/picoarch \
        cubegm/picoarch_hi \
        cubegm/cores/frogui_libretro.so \
        cubegm/cores/libemu_md.so \
        cubegm/zhijack.sh; do
        hash_line="$(sha256sum "$MOUNT/$rel")"
        echo "Verified: $rel  ${hash_line%% *}"
    done

    echo "Complete $PROFILE TreeFrogUI release deployed and verified."
}

deploy_one() {
    local name="$1" src dst src_hash dst_hash hash_line
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
    mkdir -p "$(dirname "$dst")"

    hash_line="$(sha256sum "$src")"
    src_hash="${hash_line%% *}"
    if [ -f "$dst" ]; then
        hash_line="$(sha256sum "$dst")"
        dst_hash="${hash_line%% *}"
        if [ "$src_hash" = "$dst_hash" ]; then
            echo "$name already current: $src_hash"
            return
        fi
    fi

    rsync -tc "$src" "$dst"
    sync
    hash_line="$(sha256sum "$dst")"
    dst_hash="${hash_line%% *}"
    [ "$src_hash" = "$dst_hash" ] || die "$name verification failed"
    echo "$name deployed: $dst_hash"
}

for payload in "${PAYLOADS[@]}"; do
    case "$payload" in
        release) deploy_release ;;
        *) deploy_one "$payload" ;;
    esac
done

for rel in "${STOCK_FILES[@]}"; do
    hash_line="$(sha256sum "$MOUNT/$rel")"
    deployed_hash="${hash_line%% *}"
    [ "$deployed_hash" = "${stock_hashes[$rel]}" ] ||
        die "protected stock file changed: $rel"
    echo "Stock preserved: $rel  $deployed_hash"
done
