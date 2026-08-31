#!/usr/bin/env bash
# One-prompt guarded deployment of the TreeFrogUI USB-mode test payload.
set -Eeuo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
CORE=/home/tomaszz/sf3000-work/FrogUI/frogui_libretro.so
RUNTIME="$REPO/apps/usb_mode/usb_mode.sh"
MTP_ENTRY="$REPO/apps/usb_mode/usb_mtp.sh"
MTP_SERVER="$REPO/apps/usb_mode/mtp-server"
MODULE="$REPO/apps/usb_mode/modules/4.4.186-release/usb_f_mass_storage.ko"
MTP_MODULE="$REPO/apps/usb_mode/modules/4.4.186-release/usb_f_mtp.ko"
LAUNCHER="$REPO/release/latest/release/install_first/r36hd/cubegm/zhijack.sh"
MOUNT=/mnt/treefrog-usb-mode
EXPECTED_LABEL=R36HD

die() { echo "deploy-usb-mode: $*" >&2; exit 1; }

validate_sources() {
    [ -f "$CORE" ] || die "missing built FrogUI core: $CORE"
    [ -x "$RUNTIME" ] || die "missing executable runtime: $RUNTIME"
    [ -x "$MTP_ENTRY" ] || die "missing MTP entrypoint: $MTP_ENTRY"
    [ -x "$MTP_SERVER" ] || die "missing MTP responder: $MTP_SERVER"
    [ -f "$MODULE" ] || die "missing module: $MODULE"
    [ -f "$MTP_MODULE" ] || die "missing MTP module: $MTP_MODULE"
    [ -x "$LAUNCHER" ] || die "missing generated launcher: $LAUNCHER"
    file "$CORE" | grep -q 'ELF 32-bit LSB.*MIPS' || die "FrogUI core has wrong architecture"
    strings "$CORE" | grep -F '/mnt/sdcard/cubegm/usb_mtp.sh' >/dev/null || die "FrogUI core lacks USB mode"
    file "$MODULE" | grep -q 'ELF 32-bit LSB relocatable, MIPS, MIPS32 rel2' || die "module has wrong architecture"
    strings "$MODULE" | grep -F '4.4.186-release preempt MIPS32_R2 32BIT' >/dev/null || die "module vermagic mismatch"
    file "$MTP_MODULE" | grep -q 'ELF 32-bit LSB relocatable, MIPS, MIPS32 rel2' || die "MTP module has wrong architecture"
    grep -q '^TF_DEVICE=R36SX' "$LAUNCHER" || die "generated launcher is not the R36HD/R36SX profile"
    grep -q 'cd / || exit 1' "$LAUNCHER" || die "generated launcher lacks SD cwd fix"
}

resolve_card() {
    local dev
    # blkid may have a stale/empty cache while the desktop automounter has
    # already discovered the VFAT label; lsblk reads the kernel uevent data
    # directly and is a reliable fallback.
    dev="$(blkid -L "$EXPECTED_LABEL" 2>/dev/null || true)"
    if [ -z "$dev" ]; then
        dev="$(lsblk -nrpo NAME,LABEL | awk -v label="$EXPECTED_LABEL" '$2 == label {print $1; exit}')"
    fi
    [ -n "$dev" ] || die "card labelled $EXPECTED_LABEL not found"
    dev="$(readlink -f "$dev")"
    case "$dev" in /dev/sd[a-z][0-9]*|/dev/mmcblk[0-9]p[0-9]*) ;; *) die "refusing unexpected device: $dev";; esac
    [ "$(lsblk -dnro RM "$dev")" = 1 ] || die "$dev is not removable"
    [ "$(lsblk -dnro FSTYPE "$dev")" = vfat ] || die "$dev is not VFAT"
    [ "$(lsblk -dnro LABEL "$dev")" = "$EXPECTED_LABEL" ] || die "card label changed"
    printf '%s\n' "$dev"
}

if [ "${1:-}" != --root ]; then
    validate_sources
    DEV="$(resolve_card)"
    echo "Validated $EXPECTED_LABEL on $DEV. Requesting privilege once..."
    exec pkexec "$0" --root "$DEV"
fi

[ "$EUID" -eq 0 ] || die "privileged phase is not root"
[ "$#" -eq 2 ] || die "invalid privileged invocation"
DEV="$2"
validate_sources
[ "$(resolve_card)" = "$DEV" ] || die "card changed during authorization"

mounted=0
cleanup() {
    if [ "$mounted" -eq 1 ] && mountpoint -q "$MOUNT"; then
        sync
        umount "$MOUNT"
        mounted=0
    fi
}
trap cleanup EXIT INT TERM

while IFS= read -r old_mount; do
    [ -z "$old_mount" ] || umount "$old_mount"
done < <(findmnt -rn -S "$DEV" -o TARGET)

echo "Repairing/checking FAT..."
set +e
fsck.vfat -a "$DEV"
fsck_rc=$?
set -e
[ "$fsck_rc" -le 1 ] || die "FAT repair failed with status $fsck_rc"
mkdir -p "$MOUNT"
mount -t vfat -o rw,uid=1000,gid=1000,utf8,flush "$DEV" "$MOUNT"
mounted=1
opts="$(findmnt -nro OPTIONS -T "$MOUNT")"
case ",$opts," in *,rw,*) ;; *) die "card did not mount read-write: $opts";; esac

[ -f "$MOUNT/cubegm/zhijack.sh" ] || die "not a TreeFrogUI card"
grep -q '^TF_DEVICE=R36SX' "$MOUNT/cubegm/zhijack.sh" || die "card is not using the R36SX profile"
[ -f "$MOUNT/cubegm/cores/frogui_libretro.so" ] || die "installed FrogUI core missing"
[ -f "$MOUNT/cubegm/zhijack.sh" ] || die "installed launcher missing"

BACKUP="$MOUNT/cubegm/cores/frogui_libretro.so.pre_usb_mode"
if [ ! -f "$BACKUP" ]; then
    cp -p "$MOUNT/cubegm/cores/frogui_libretro.so" "$BACKUP"
    echo "Created backup: cubegm/cores/$(basename "$BACKUP")"
fi

mkdir -p "$MOUNT/cubegm/modules/4.4.186-release"
install -m 0755 "$RUNTIME" "$MOUNT/cubegm/usb_mode.sh"
install -m 0755 "$MTP_ENTRY" "$MOUNT/cubegm/usb_mtp.sh"
install -m 0755 "$MTP_SERVER" "$MOUNT/cubegm/mtp-server"
install -m 0644 "$MODULE" "$MOUNT/cubegm/modules/4.4.186-release/usb_f_mass_storage.ko"
install -m 0644 "$MTP_MODULE" "$MOUNT/cubegm/modules/4.4.186-release/usb_f_mtp.ko"
install -m 0644 "$CORE" "$MOUNT/cubegm/cores/frogui_libretro.so"
install -m 0755 "$LAUNCHER" "$MOUNT/cubegm/zhijack.sh"
sync

verify_equal() {
    local src="$1" dst="$2" name="$3"
    [ "$(sha256sum "$src" | awk '{print $1}')" = "$(sha256sum "$dst" | awk '{print $1}')" ] ||
        die "$name verification failed"
    echo "Verified: $name"
}
verify_equal "$CORE" "$MOUNT/cubegm/cores/frogui_libretro.so" FrogUI
verify_equal "$RUNTIME" "$MOUNT/cubegm/usb_mode.sh" usb_mode.sh
verify_equal "$MTP_ENTRY" "$MOUNT/cubegm/usb_mtp.sh" usb_mtp.sh
verify_equal "$MTP_SERVER" "$MOUNT/cubegm/mtp-server" mtp-server
verify_equal "$MODULE" "$MOUNT/cubegm/modules/4.4.186-release/usb_f_mass_storage.ko" usb_f_mass_storage.ko
verify_equal "$MTP_MODULE" "$MOUNT/cubegm/modules/4.4.186-release/usb_f_mtp.ko" usb_f_mtp.ko
verify_equal "$LAUNCHER" "$MOUNT/cubegm/zhijack.sh" zhijack.sh

umount "$MOUNT"
mounted=0
fsck.vfat -n "$DEV"
echo "USB mode deployed. $EXPECTED_LABEL is clean, unmounted, and safe to remove."
