#!/bin/sh
# PID1 on the new kernel. Use the existing SD userspace, never the old kernel.
b() { /rootfs/lib/ld.so.1 --library-path /rootfs/lib /rootfs/bin/busybox "$@"; }
original=/cubegm/__STOCK_BACKUP__
bootfile=/cubegm/__STOCK_FILE__
staged=/cubegm/r36-stock-restore.staged
proof=/cubegm/r36-direct-proof.txt
progress=/cubegm/r36-direct-progress.txt
expected=__STOCK_MD5__

id=unavailable
IFS= read -r id < /cubegm/r36-direct-run-id.txt
printf 'R36 DIRECT PROGRESS\nrun_id=%s\npid=%s\nstage=pid1_shell_started\n' "$id" "$$" > "$progress"
stage() {
    printf 'stage=%s\n' "$1" >> "$progress"
    b sync
}

fail() {
    stage "failed: $1"
    printf 'R36 DIRECT COLD BOOT FAILED\nreason=%s\nrelease=%s\npid=%s\n' "$1" "$(b uname -r)" "$$" > "$proof"
    b sync
    while :; do b sleep 1; done
}

case "$(b uname -r)" in 7.2.0-rc5-r36lab) ;; *) fail 'unexpected kernel release' ;; esac
stage kernel_release_verified
b mkdir -p /dev /proc
b mount -t devtmpfs devtmpfs /dev 2>/dev/null
b mount -t proc proc /proc 2>/dev/null
set -- $(b md5sum "$original")
[ "$1" = "$expected" ] || fail 'stock backup checksum mismatch'
stage stock_backup_verified

# Refresh the fallback timer before disk writes; never truncate the boot file.
b devmem 0x18818500 32 4289342296 2>/dev/null
b cat "$original" > "$staged" || fail 'backup copy failed'
b sync
set -- $(b md5sum "$staged")
[ "$1" = "$expected" ] || fail 'staged restoration checksum mismatch'
stage restoration_staged
b mv -f "$staged" "$bootfile" || fail 'atomic restoration failed'
b sync
set -- $(b md5sum "$bootfile")
[ "$1" = "$expected" ] || fail 'restored boot file checksum mismatch'
stage stock_boot_file_restored

printf 'R36 DIRECT COLD BOOT\nrun_id=%s\nrelease=%s\nversion=%s\nmachine=%s\npid=%s\nstock_kernel_restored=1\n' \
    "$id" "$(b uname -r)" "$(b uname -v)" "$(b uname -m)" "$$" > "$proof"
b cat /proc/cmdline > /cubegm/r36-direct-cmdline.txt
b cat /proc/meminfo > /cubegm/r36-direct-meminfo.txt
b devmem 0x02f91010 32 6 2>/dev/null
b sync
b mount -t vfat -o remount,ro /dev/mmcblk0p1 / 2>/dev/null
b sync
# Original encrypted stock kernel is already back in place; return promptly.
b devmem 0x18818500 32 4294029796 2>/dev/null
while :; do b sleep 1; done
