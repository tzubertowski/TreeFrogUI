#!/bin/sh
# TreeFrogUI OTG-storage hotplug integration.
#
# Stock mdev invokes this for both MMC and USB block events. Only USB SCSI
# disks (sdX) belong here: mounting mmcblk0 would hide the system card under
# the OTG mountpoint. A connected drive is mounted once at /media/hdd; FrogUI
# exposes it as the "OTG" ROM source when /media/hdd/roms exists.

LOCK=/var/lock/treefrog-otg-mount.lock
MOUNTPOINT=/media/hdd
LOG=/mnt/sdcard/log.txt

log() {
    [ -f "$LOG" ] || return 0
    printf 'OTG: %s\n' "$*" >> "$LOG"
}

name=${MDEV:-${DEVNAME##*/}}
case "$name" in
    sd[a-z]|sd[a-z][0-9]|sd[a-z][0-9][0-9]) ;;
    *) exit 0 ;;
esac

mkdir -p /var/lock "$MOUNTPOINT" 2>/dev/null || exit 0
exec 200>"$LOCK"
flock -n 200 || exit 0

mounted_device() {
    awk -v mountpoint="$MOUNTPOINT" '$2 == mountpoint { print $1; exit }' /proc/mounts
}

case "${ACTION:-add}" in
    add|"")
        # mdev announces the disk before its partitions. Wait for sdX1 so a
        # normal partitioned drive is never mounted through the whole disk.
        case "$name" in
            sd[a-z]) [ -d "/sys/block/$name/${name}1" ] && exit 0 ;;
        esac
        dev="/dev/$name"
        [ -b "$dev" ] || exit 0
        current=$(mounted_device)
        [ -z "$current" ] || exit 0
        if mount -t auto -o rw,iocharset=utf8,usefree "$dev" "$MOUNTPOINT" 2>/dev/null; then
            log "mounted device=$dev path=$MOUNTPOINT"
        else
            log "mount failed device=$dev"
        fi
        ;;
    remove)
        current=$(mounted_device)
        [ -n "$current" ] || exit 0
        base=${name%%[0-9]*}
        case "$current" in
            "/dev/$name"|"/dev/$base"|"/dev/$base"[0-9]*)
                umount -l "$MOUNTPOINT" 2>/dev/null || true
                log "unmounted device=$current"
                ;;
        esac
        ;;
esac
