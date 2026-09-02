#!/bin/sh
# Expose the TreeFrogUI SD partition to a USB host through Linux USB gadget.
# `run` is deliberately blocking: unplug the USB cable to restore the SD mount.

set -u

SYS_ROOT=${TF_USB_SYS_ROOT:-/sys}
CONFIG_ROOT=${TF_USB_CONFIG_ROOT:-$SYS_ROOT/kernel/config}
PROC_MOUNTS=${TF_USB_PROC_MOUNTS:-/proc/mounts}
MOUNTPOINT=${TF_USB_MOUNTPOINT:-/mnt/sdcard}
BLOCK_DEVICE=${TF_USB_BLOCK_DEVICE:-}
PROC_SWAPS=${TF_USB_PROC_SWAPS:-/proc/swaps}
SWAPFILE=${TF_USB_SWAPFILE:-$MOUNTPOINT/cubegm/pagefile.sys}
PERSIST_LOG=${TF_USB_LOG:-$MOUNTPOINT/USB_MODE_ERROR.log}
LOG=$PERSIST_LOG
RAM_LOG=/tmp/treefrog-usb-mode.log
MODULE_DIR=${TF_USB_MODULE_DIR:-$MOUNTPOINT/cubegm/modules/$(uname -r)}
MTP_RESPONDER=${TF_USB_MTP_RESPONDER:-$MOUNTPOINT/cubegm/mtp-server}
MTP_EXIT_FLAG=/tmp/treefrog_mtp_exit
MTP_EXIT_WATCHER=${TF_USB_MTP_EXIT_WATCHER:-$MOUNTPOINT/cubegm/usb_exit_watcher}
mtp_pid=
exit_watcher_pid=
MTP_MODULE=${TF_USB_MTP_MODULE:-$MODULE_DIR/usb_f_mtp.ko}
GADGET=$CONFIG_ROOT/usb_gadget/treefrog_storage
ROLE_PATH=${TF_USB_ROLE_PATH:-$SYS_ROOT/devices/platform/soc/18844000.usb/musb-hdrc.0.auto/mode}
UDC_NAME=${TF_USB_UDC_NAME:-musb-hdrc.0.auto}

mounted=0
bound=0
configured_once=0
role_changed=0
original_role=
mount_device=
mount_type=
mount_options=
swap_was_active=0
mtp_mode=0

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo time-unknown)" "$*" >> "$LOG"; }
fail() {
    log "ERROR $*"
    # Preserve failures that happen after logging moves to RAM (e.g. umount
    # busy), so the next PC insertion contains the actionable reason.
    if [ "$LOG" != "$PERSIST_LOG" ]; then
        # Preserve the complete RAM trace, not just the final error.  This is
        # essential when the console reboots before the card can be inspected.
        cat "$LOG" >> "$PERSIST_LOG" 2>/dev/null || true
        printf '%s ERROR %s\n' "$(date 2>/dev/null || echo time-unknown)" "$*" >> "$PERSIST_LOG" 2>/dev/null || true
    fi
    printf 'USB mode error: %s\n' "$*" >&2
    exit 1
}

mount_record() {
    awk -v mp="$MOUNTPOINT" '$2 == mp { print $1 " " $3 " " $4; exit }' "$PROC_MOUNTS" 2>/dev/null
}

read_mount() {
    rec=$(mount_record)
    [ -n "$rec" ] || return 1
    mount_device=${rec%% *}
    rest=${rec#* }
    mount_type=${rest%% *}
    mount_options=${rest#* }
    case "$mount_device$MOUNTPOINT" in *'\\040'*|*'\\011'*) return 2;; esac
    [ -n "$BLOCK_DEVICE" ] || BLOCK_DEVICE=$mount_device
    [ "$BLOCK_DEVICE" = "$mount_device" ] || return 3
    mounted=1
}

find_role_path() {
    [ -e "$ROLE_PATH" ] && return 0
    ROLE_PATH=$(find "$SYS_ROOT/devices" -path '*musb-hdrc.0.auto/mode' -print -quit 2>/dev/null || true)
    [ -n "$ROLE_PATH" ] && [ -e "$ROLE_PATH" ]
}

remove_gadget() {
    [ -d "$GADGET" ] || return 0
    if [ -e "$GADGET/UDC" ]; then
        printf '\n' > "$GADGET/UDC" 2>/dev/null || return 1
        # The legacy f_mtp function keeps the configfs directory busy until
        # the disconnect callback runs.  Give it a bounded handoff window so
        # a B-exit can be followed by another MTP session without rebooting.
        n=0
        while [ "$n" -lt 25 ]; do
            state=$(cat "$SYS_ROOT/class/udc/$UDC_NAME/state" 2>/dev/null || echo unknown)
            [ "$state" = 'not attached' ] || [ "$state" = 'disconnected' ] && break
            sleep 0.2
            n=$((n + 1))
        done
    fi
    bound=0
    find "$GADGET/configs" -type l -exec rm -f {} \; 2>/dev/null || true
    find "$GADGET/functions" -mindepth 1 -maxdepth 1 -type d -exec rmdir {} \; 2>/dev/null || true
    find "$GADGET/configs" -depth -type d -exec rmdir {} \; 2>/dev/null || true
    find "$GADGET/strings" -depth -type d -exec rmdir {} \; 2>/dev/null || true
    rmdir "$GADGET" 2>/dev/null || true
}

restore() {
    rc=$?
    trap - EXIT HUP INT TERM
    if [ -n "${mtp_pid:-}" ] && kill -0 "$mtp_pid" 2>/dev/null; then
        kill -TERM "$mtp_pid" 2>/dev/null || true
        wait "$mtp_pid" 2>/dev/null || true
    fi
    [ -n "${exit_watcher_pid:-}" ] && kill "$exit_watcher_pid" 2>/dev/null || true
    if [ "$bound" -eq 1 ]; then
        # A signal must never tear storage from a PC that may still be writing.
        state=$(cat "$SYS_ROOT/class/udc/$UDC_NAME/state" 2>/dev/null || echo unknown)
        if [ "$configured_once" -eq 1 ]; then
            # Never block the UI forever when a host driver aborts.  Windows
            # commonly signals the launcher while the legacy UDC still says
            # `configured`; cap the safety wait and force gadget teardown.
            detach_wait=0
            detach_timeout=${TF_USB_MTP_DETACH_TIMEOUT:-5}
            log "SIGNAL_DEFERRED state=$state timeout=${detach_timeout}s"
            while [ "$detach_wait" -lt "$detach_timeout" ]; do
                state=$(cat "$SYS_ROOT/class/udc/$UDC_NAME/state" 2>/dev/null || echo unknown)
                [ "$state" = 'not attached' ] && break
                sleep 1
                detach_wait=$((detach_wait + 1))
            done
            log "SIGNAL_CLEANUP state=$(cat "$SYS_ROOT/class/udc/$UDC_NAME/state" 2>/dev/null || echo unknown) elapsed=${detach_wait}s"
        fi
    fi
    remove_gadget || log "ERROR could not fully remove gadget"
    if [ "$role_changed" -eq 1 ] && [ -n "$original_role" ]; then
        printf '%s\n' "$original_role" > "$ROLE_PATH" 2>/dev/null || log "ERROR could not restore role=$original_role"
    fi
    if [ "$mounted" -eq 0 ] && [ -n "$mount_device" ]; then
        mkdir -p "$MOUNTPOINT" 2>/dev/null || true
        # Do not replay /proc/mounts' kernel/runtime-only flags (which some
        # BusyBox mount versions reject).  Let the device's normal mount
        # defaults apply; the filesystem and exact block device stay fixed.
        if mount -t "$mount_type" "$mount_device" "$MOUNTPOINT"; then
            mounted=1
            log "RESTORED mount=$mount_device on $MOUNTPOINT"
            if [ "$swap_was_active" -eq 1 ] && [ -f "$SWAPFILE" ]; then
                if swapon "$SWAPFILE" 2>>"$LOG"; then
                    log "RESTORED swap=$SWAPFILE"
                else
                    log "ERROR could not restore swap=$SWAPFILE"
                    rc=1
                fi
            fi
        else
            log "FATAL SD_REMOUNT_FAILED device=$mount_device mountpoint=$MOUNTPOINT"
            rc=1
        fi
    fi
    exit "$rc"
}

disable_sd_swap() {
    # The stock image enables cubegm/pagefile.sys during boot.  An active swap
    # file is an open kernel reference and makes an otherwise clean SD
    # unmount fail with EBUSY.  Remember and restore it after cable removal.
    if [ -f "$SWAPFILE" ]; then
        # Do not depend on a particular /proc/swaps formatting: vendor
        # BusyBox builds have emitted both absolute and escaped filenames.
        if grep -F "$SWAPFILE" "$PROC_SWAPS" >/dev/null 2>&1; then
            log "SWAPOFF $SWAPFILE"
            swapoff "$SWAPFILE" 2>>"$LOG" || fail "could not disable SD swap $SWAPFILE"
            swap_was_active=1
        else
            # A stale/nonstandard proc entry is still safer to probe directly;
            # inactive swapoff is harmless and its failure is ignored.
            swapoff "$SWAPFILE" 2>>"$LOG" || true
        fi
    fi
}

release_mount_users() {
    # A process cwd/root on the card keeps vfat busy.  Regular mapped
    # libraries do not, so only target the two VFS references that make
    # unmount impossible.  Never target this runtime (it is running from /tmp).
    for proc in /proc/[0-9]*; do
        pid=${proc##*/}
        [ "$pid" = "$$" ] && continue
        cwd=$(readlink "$proc/cwd" 2>/dev/null || true)
        root=$(readlink "$proc/root" 2>/dev/null || true)
        fd_ref=
        for fd in "$proc"/fd/*; do
            ref=$(readlink "$fd" 2>/dev/null || true)
            case "$ref" in "$MOUNTPOINT"|"$MOUNTPOINT"/*) fd_ref=$ref; break;; esac
        done
        case "$cwd:$root:$fd_ref" in
            "$MOUNTPOINT"*|*":$MOUNTPOINT"*|*":$MOUNTPOINT"*)
                cmd=$(tr '\0' ' ' < "$proc/cmdline" 2>/dev/null || true)
                log "MOUNT_USER pid=$pid cwd=$cwd root=$root fd=$fd_ref cmd=$cmd"
                kill "$pid" 2>/dev/null || true
                ;;
        esac
    done
    sleep 0.2
    for proc in /proc/[0-9]*; do
        pid=${proc##*/}
        [ "$pid" = "$$" ] && continue
        cwd=$(readlink "$proc/cwd" 2>/dev/null || true)
        root=$(readlink "$proc/root" 2>/dev/null || true)
        fd_ref=
        for fd in "$proc"/fd/*; do
            ref=$(readlink "$fd" 2>/dev/null || true)
            case "$ref" in "$MOUNTPOINT"|"$MOUNTPOINT"/*) fd_ref=$ref; break;; esac
        done
        case "$cwd:$root:$fd_ref" in
            "$MOUNTPOINT"*|*":$MOUNTPOINT"*|*":$MOUNTPOINT"*) kill -9 "$pid" 2>/dev/null || true ;;
        esac
    done
}

load_gadget_stack() {
    log "KERNEL uname=$(uname -a 2>/dev/null || true) role=$(cat "$ROLE_PATH" 2>/dev/null || echo unavailable)"
    if ! awk -v m="$CONFIG_ROOT" '$2 == m { found=1 } END { exit found ? 0 : 1 }' "$PROC_MOUNTS" 2>/dev/null; then
        mount -t configfs none "$CONFIG_ROOT" >>"$LOG" 2>&1 || true
    fi
    modprobe libcomposite >>"$LOG" 2>&1 || true
    modprobe usb_f_mass_storage >>"$LOG" 2>&1 || true
    if ! grep -q '^usb_f_mass_storage ' /proc/modules 2>/dev/null && [ -f "$MODULE_DIR/usb_f_mass_storage.ko" ]; then
        log "INSMOD $MODULE_DIR/usb_f_mass_storage.ko"
        insmod "$MODULE_DIR/usb_f_mass_storage.ko" >>"$LOG" 2>&1 || true
    fi
    log "MODULES $(grep -E '^(libcomposite|usb_f_mass_storage) ' /proc/modules 2>/dev/null | tr '\n' ';' || true)"
    dmesg 2>/dev/null | tail -n 40 >>"$LOG" || true
    [ -d "$CONFIG_ROOT/usb_gadget" ]
}

load_mtp_stack() {
    log "MTP module=$MTP_MODULE responder=$MTP_RESPONDER"
    modprobe usb_f_mtp >>"$LOG" 2>&1 || true
    if ! grep -q '^usb_f_mtp ' /proc/modules 2>/dev/null && [ -f "$MTP_MODULE" ]; then
        insmod "$MTP_MODULE" >>"$LOG" 2>&1 || true
    fi
    grep -q '^usb_f_mtp ' /proc/modules 2>/dev/null
}

set_mtp_peripheral_role() {
    if ! printf 'peripheral\n' > "$ROLE_PATH" 2>>"$LOG"; then
        printf 'b_peripheral\n' > "$ROLE_PATH" 2>>"$LOG" || return 1
    fi
    role_changed=1
    role_now=$(cat "$ROLE_PATH" 2>/dev/null || echo unavailable)
    log "MTP_ROLE peripheral now=$role_now"
}

set_safe_host_role() {
    # A stale f_mtp instance is not fully reset by unbinding its UDC on this
    # 4.4 MUSB driver.  Returning the controller to host mode drops the UDC
    # and gives the PC a genuine disconnect before the next peripheral bind.
    if ! printf 'host\n' > "$ROLE_PATH" 2>>"$LOG"; then
        printf 'b_idle\n' > "$ROLE_PATH" 2>>"$LOG" || return 1
    fi
    role_now=$(cat "$ROLE_PATH" 2>/dev/null || echo unavailable)
    log "MTP_ROLE host now=$role_now"
}

create_mtp_gadget() {
    mkdir -p "$GADGET" || return 1
    # Use a libmtp-known Android MTP VID/PID.  KDE's kmtpd rejects unknown
    # VID/PID devices even when mtp-probe identifies them correctly; the
    # protocol and product strings still identify this as TreeFrogUI.
    printf '0x18d1\n' > "$GADGET/idVendor"
    # 18D1:4E22 is a Windows-known Google MTP identity (Nexus 10).  Using
    # this PID lets the inbox WPD MTP association match even when the host
    # ignores the Microsoft compatible-ID descriptor on this legacy gadget.
    printf '0x4e22\n' > "$GADGET/idProduct"
    printf '0x0100\n' > "$GADGET/bcdDevice"
    printf '0x0200\n' > "$GADGET/bcdUSB"
    mkdir -p "$GADGET/strings/0x409" "$GADGET/configs/c.1/strings/0x409" || {
        log "MTP_SETUP_FAIL step=strings"; return 1;
    }
    printf 'TreeFrogUI-%s\n' "$(cat /etc/machine-id 2>/dev/null | cut -c1-16 || echo SF3000)" > "$GADGET/strings/0x409/serialnumber"
    printf 'TreeFrogUI\n' > "$GADGET/strings/0x409/manufacturer"
    printf 'TreeFrogUI MTP\n' > "$GADGET/strings/0x409/product"
    printf 'MTP file access\n' > "$GADGET/configs/c.1/strings/0x409/configuration"
    printf '120\n' > "$GADGET/configs/c.1/MaxPower"
    # The recovered vendor module registers the configfs function as mtp.
    # configfs objects can survive a host-aborted session on the vendor 4.4
    # kernel.  Reuse the function when it is already present; mkdir without
    # -p made the next connection fail even though the gadget was otherwise
    # perfectly usable.
    if [ ! -d "$GADGET/functions/mtp.usb0" ]; then
        mkdir "$GADGET/functions/mtp.usb0" 2>>"$LOG" || {
            log "MTP_SETUP_FAIL step=create_function"; return 2;
        }
    fi
    # Enable the module's Android-compatible Microsoft OS descriptor path.
    # The function module supplies the MTP compatible-ID data; configfs only
    # enables the OS string and associates it with this configuration.
    if [ -d "$GADGET/os_desc" ]; then
        # The recovered Android f_mtp module hard-codes vendor request 1 in
        # its MSFT100 string/control handler; configfs must advertise the
        # same value or Windows never receives the MTP compatible ID.
        printf '1\n' > "$GADGET/os_desc/b_vendor_code" 2>>"$LOG" || {
            log "MTP_SETUP_FAIL step=os_desc_vendor"; return 1;
        }
        printf 'MSFT100\n' > "$GADGET/os_desc/qw_sign" 2>>"$LOG" || {
            log "MTP_SETUP_FAIL step=os_desc_sign"; return 1;
        }
        # Windows' inbox MTP driver is selected from the extended compatible
        # ID.  The Android f_mtp module handles the vendor request, but does
        # not create the configfs interface entry itself on this 4.4 tree.
        # Advertise the standard MTP ID on the function (the symlink is
        # intentionally best-effort for kernels whose module owns this path).
        # Android's f_mtp exposes its own function-level os_desc group; the
        # compatible ID must be written there (a gadget-level directory is
        # ignored by the 4.4 configfs implementation).
        mkdir -p "$GADGET/functions/mtp.usb0/os_desc/interface.MTP" 2>>"$LOG" || {
            log "MTP_SETUP_FAIL step=os_desc_interface"; return 1;
        }
        printf 'MTP\n' > "$GADGET/functions/mtp.usb0/os_desc/interface.MTP/compatible_id" 2>>"$LOG" || {
            log "MTP_SETUP_FAIL step=compatible_id"; return 1;
        }
        # Associate the configuration before enabling OS descriptors.  The
        # composite core snapshots this link while handling the first 0xEE /
        # vendor request; enabling `use` first can make Windows receive an
        # empty compatible-ID descriptor on this legacy kernel.
        # configfs links cannot be atomically replaced while their function
        # is held by f_mtp.  Leave an already-correct link alone; `ln -sf`
        # follows it as a directory on BusyBox and fails the second session.
        if [ ! -L "$GADGET/os_desc/c.1" ]; then
            ln -s "$GADGET/configs/c.1" "$GADGET/os_desc/c.1" 2>>"$LOG" || {
                log "MTP_SETUP_FAIL step=os_desc_link"; return 1;
            }
        fi
        printf '1\n' > "$GADGET/os_desc/use" 2>>"$LOG" || {
            log "MTP_SETUP_FAIL step=os_desc_enable"; return 1;
        }
    fi
    if [ ! -L "$GADGET/configs/c.1/mtp.usb0" ]; then
        ln -s "$GADGET/functions/mtp.usb0" "$GADGET/configs/c.1/mtp.usb0" 2>>"$LOG" || {
            log "MTP_SETUP_FAIL step=config_link"; return 1;
        }
    fi
}

run_mtp_mode() {
    # MTP deliberately keeps /mnt/sdcard mounted; the responder accesses it
    # through normal filesystem operations instead of exporting its block
    # device. It must therefore run from the SD only after gadget setup.
    # Keep prior sessions: a hard lock/reboot can otherwise erase the only
    # evidence before the card is removed for inspection.
    printf '\n--- MTP session %s ---\n' "$(date 2>/dev/null || echo unknown)" >> "$LOG" 2>/dev/null || fail "cannot create log $LOG"
    trap restore_mtp EXIT HUP INT TERM
    [ "$(id -u)" = 0 ] || fail "must run as root"
    read_mount || fail "$MOUNTPOINT is not a simple mounted filesystem"
    find_role_path || fail "MUSB role control not found"
    load_gadget_stack || fail "configfs/libcomposite unavailable"
    load_mtp_stack || fail "MTP function module unavailable"
    original_role=$(cat "$ROLE_PATH" 2>/dev/null) || fail "cannot read USB role"
    # A previous session may have been detached by a host reset; legacy
    # configfs can finish unbinding asynchronously.  Clear that stale gadget
    # and wait briefly before creating the next one.
    if [ -d "$GADGET" ]; then
        log "MTP_STALE_GADGET cleanup"
        remove_gadget || true
        # Drop the entire peripheral controller state before reusing any
        # configfs object.  Without this, the host often keeps the previous
        # MTP instance cached even though the console reports "initialized".
        set_safe_host_role || log "ERROR could not switch MTP controller to host"
        sleep 1
        n=0
        # f_mtp's release callback on this 4.4 vendor kernel can take several
        # seconds after a Windows descriptor-request abort.  Give configfs
        # enough time to finish unbinding before declaring it wedged.
        while [ "$n" -lt 10 ] && [ -d "$GADGET" ]; do sleep 0.5; n=$((n+1)); done
        log "MTP_STALE_GADGET_WAIT elapsed=$((n / 2))s remaining=$( [ -d "$GADGET" ] && echo yes || echo no )"
        if [ -d "$GADGET" ]; then
            # f_mtp may keep configfs references busy after Windows aborts
            # descriptor negotiation.  The object is ours and can be safely
            # rebound once UDC is detached, so keep it and make setup
            # idempotent instead of wedging the UI or forcing a reboot.
            log "MTP_STALE_GADGET_REUSE path=$GADGET"
        fi
    fi
    set_mtp_peripheral_role || fail "cannot switch USB to peripheral role"
    n=0; while [ "$n" -lt 20 ] && [ ! -e "$SYS_ROOT/class/udc/$UDC_NAME" ]; do sleep 0.1; n=$((n+1)); done
    [ -e "$SYS_ROOT/class/udc/$UDC_NAME" ] || fail "UDC $UDC_NAME did not appear"
    create_mtp_gadget || fail "could not create MTP gadget"
    log "MTP_OS_DESC vendor=$(cat "$GADGET/os_desc/b_vendor_code" 2>/dev/null || echo missing) sign=$(cat "$GADGET/os_desc/qw_sign" 2>/dev/null || echo missing) use=$(cat "$GADGET/os_desc/use" 2>/dev/null || echo missing) compat=$(cat "$GADGET/functions/mtp.usb0/os_desc/interface.MTP/compatible_id" 2>/dev/null || echo missing)"
    printf '%s\n' "$UDC_NAME" > "$GADGET/UDC" || fail "could not bind MTP UDC"
    bound=1; mtp_mode=1
    [ -x "$MTP_RESPONDER" ] || fail "MTP responder missing: $MTP_RESPONDER"
    rm -f "$MTP_EXIT_FLAG"
    log "MTP_READY mount=$MOUNTPOINT responder=$MTP_RESPONDER"
    printf 'MTP USB ready. Eject/disconnect USB to exit.\n'
    # Keep the responder in the background so the launcher can surface the
    # actual UDC state.  Windows may take several seconds to bind WPD; showing
    # CONNECTED only after the gadget reports configured avoids a misleading
    # "ready" message while the cable is still negotiating.
    "$MTP_RESPONDER" "$MOUNTPOINT" >>"$LOG" 2>&1 &
    mtp_pid=$!
    if [ -x "$MTP_EXIT_WATCHER" ]; then
        "$MTP_EXIT_WATCHER" "$mtp_pid" >/dev/null 2>&1 &
        exit_watcher_pid=$!
        log "MTP_EXIT_WATCHER pid=$exit_watcher_pid"
    else
        log "MTP_EXIT_WATCHER unavailable path=$MTP_EXIT_WATCHER"
    fi
    connected_reported=0
    while kill -0 "$mtp_pid" 2>/dev/null; do
        udc_state=$(cat "$SYS_ROOT/class/udc/$UDC_NAME/state" 2>/dev/null || echo unknown)
        if [ "$udc_state" = configured ] && [ "$connected_reported" -eq 0 ]; then
            log "MTP_CONNECTED state=$udc_state"
            printf 'CONNECTED - TreeFrogUI MTP is mounted on the PC.\n'
            connected_reported=1
        fi
        sleep 1
    done
    wait "$mtp_pid"
    mtp_rc=$?
    [ -n "${exit_watcher_pid:-}" ] && kill "$exit_watcher_pid" 2>/dev/null || true
    log "MTP_EXIT rc=$mtp_rc"
    if [ -f "$MTP_EXIT_FLAG" ]; then
        rm -f "$MTP_EXIT_FLAG"
    elif [ "$mtp_rc" -ne 0 ]; then
        # A responder terminated by the host (usually SIGTERM=143 when Windows
        # abandons enumeration) is already a failed/disconnected session.
        # Do not wait on a stale UDC state in this case: cleanup must happen
        # immediately so the FrogUI event loop cannot appear frozen.
        log "MTP_ABORT cleanup_immediate rc=$mtp_rc"
    else
        # A Windows driver failure can leave the UDC in `configured` (or
        # `unknown`) forever even though the responder has exited.  Waiting
        # unboundedly here used to deadlock the UI and made the console appear
        # frozen.  Give a real host a short grace period, then let the EXIT
        # trap unbind the gadget and restore the normal USB role.
        detach_wait=0
        detach_timeout=${TF_USB_MTP_DETACH_TIMEOUT:-5}
        while :; do
            udc_state=$(cat "$SYS_ROOT/class/udc/$UDC_NAME/state" 2>/dev/null || echo unknown)
            [ "$udc_state" = 'not attached' ] && break
            [ "$detach_wait" -ge "$detach_timeout" ] && break
            log "MTP_WAIT_DISCONNECT state=$udc_state elapsed=${detach_wait}s"
            sleep 1
            detach_wait=$((detach_wait + 1))
        done
        udc_state=$(cat "$SYS_ROOT/class/udc/$UDC_NAME/state" 2>/dev/null || echo unknown)
        if [ "$udc_state" != 'not attached' ]; then
            log "MTP_FORCE_UNBIND state=$udc_state timeout=${detach_timeout}s"
        else
            log "MTP_DISCONNECTED elapsed=${detach_wait}s"
        fi
    fi
}

restore_mtp() {
    rc=$?; trap - EXIT HUP INT TERM
    remove_gadget || log "ERROR could not remove MTP gadget"
    # `(null)` is the vendor driver's reported boot value, not a writable
    # role.  Always return to a real host/idle state so a future MTP run has
    # a clean UDC and the PC observes a physical disconnect.
    [ "$role_changed" -eq 0 ] || set_safe_host_role || log "ERROR could not restore host role"
    exit "$rc"
}

create_gadget() {
    mkdir -p "$GADGET" || return 1
    printf '0x1209\n' > "$GADGET/idVendor"
    printf '0x3000\n' > "$GADGET/idProduct"
    printf '0x0100\n' > "$GADGET/bcdDevice"
    printf '0x0200\n' > "$GADGET/bcdUSB"
    mkdir -p "$GADGET/strings/0x409" "$GADGET/configs/c.1/strings/0x409" || return 1
    printf 'TreeFrogUI-%s\n' "$(cat /etc/machine-id 2>/dev/null | cut -c1-16 || echo SF3000)" > "$GADGET/strings/0x409/serialnumber"
    printf 'TreeFrogUI\n' > "$GADGET/strings/0x409/manufacturer"
    printf 'TreeFrogUI SD Card\n' > "$GADGET/strings/0x409/product"
    printf 'SD card storage\n' > "$GADGET/configs/c.1/strings/0x409/configuration"
    printf '120\n' > "$GADGET/configs/c.1/MaxPower"
    mkdir "$GADGET/functions/mass_storage.usb0" 2>/dev/null || return 2
    printf '1\n' > "$GADGET/functions/mass_storage.usb0/lun.0/removable"
    printf '0\n' > "$GADGET/functions/mass_storage.usb0/lun.0/cdrom"
    printf '0\n' > "$GADGET/functions/mass_storage.usb0/lun.0/ro"
    ln -s "$GADGET/functions/mass_storage.usb0" "$GADGET/configs/c.1/mass_storage.usb0" || return 1
}

preflight() {
    log "PREFLIGHT step=identity"
    [ "$(id -u)" = 0 ] || fail "must run as root"
    read_mount || fail "$MOUNTPOINT is not a simple mounted filesystem"
    log "PREFLIGHT mount_device=$mount_device mount_type=$mount_type"
    case "$BLOCK_DEVICE" in /dev/mmcblk*p[0-9]*) ;; *) fail "refusing unexpected backing device: $BLOCK_DEVICE";; esac
    [ -b "$BLOCK_DEVICE" ] || fail "backing device is not a block device: $BLOCK_DEVICE"
    log "PREFLIGHT step=role-path"
    find_role_path || fail "MUSB role control not found"
    log "PREFLIGHT role_path=$ROLE_PATH role=$(cat "$ROLE_PATH" 2>/dev/null || echo unavailable)"
    # This kernel registers the gadget UDC only after MUSB leaves its boot-time
    # host/b_idle state, so checking it before the role transition is invalid.
    log "PREFLIGHT step=gadget-conflict-check"
    for udc in "$CONFIG_ROOT"/usb_gadget/*/UDC; do
        [ -e "$udc" ] || continue
        [ -z "$(cat "$udc" 2>/dev/null)" ] || fail "another USB gadget is active: $udc"
    done
    load_gadget_stack || fail "configfs/libcomposite unavailable"
    log "PREFLIGHT step=module-check"
    grep -q '^usb_f_mass_storage ' /proc/modules 2>/dev/null ||
        fail "mass-storage function unavailable; install ABI-matched usb_f_mass_storage.ko"
    original_role=$(cat "$ROLE_PATH" 2>/dev/null) || fail "cannot read USB role"
    log "PREFLIGHT step=role-switch from=$original_role"
    if ! printf 'peripheral\n' > "$ROLE_PATH" 2>>"$LOG"; then
        log "ROLE_SWITCH peripheral_failed"
        if ! printf 'b_peripheral\n' > "$ROLE_PATH" 2>>"$LOG"; then
            fail "cannot switch USB to peripheral/b_peripheral role"
        fi
    fi
    log "PREFLIGHT role-after=$(cat "$ROLE_PATH" 2>/dev/null || echo unavailable)"
    role_changed=1
    n=0
    while [ "$n" -lt 20 ] && [ ! -e "$SYS_ROOT/class/udc/$UDC_NAME" ]; do
        sleep 0.1
        n=$((n + 1))
    done
    [ -e "$SYS_ROOT/class/udc/$UDC_NAME" ] || fail "UDC $UDC_NAME did not appear after peripheral switch"
    log "PREFLIGHT UDC_READY=$UDC_NAME"
}

run_mode() {
    # ash may lazily read its script.  Keep execution alive after the backing
    # SD filesystem is unmounted by re-executing a private RAM copy first.
    if [ "${TF_USB_RUNNING_COPY:-0}" != 1 ]; then
        runtime_script=/tmp/treefrog-usb-mode.$$.sh
        cp "$0" "$runtime_script" || fail "cannot copy runtime to RAM"
        chmod 700 "$runtime_script" || fail "cannot prepare RAM runtime"
        TF_USB_RUNNING_COPY=1 exec "$runtime_script" run
        fail "cannot execute RAM runtime"
    fi
    : > "$LOG" 2>/dev/null || fail "cannot create log $LOG"
    trap restore EXIT HUP INT TERM
    preflight
    # Preflight failures remain on the mounted SD. After it succeeds, continue
    # logging in RAM so no open/log writes can race the exported filesystem.
    cp "$LOG" "$RAM_LOG" 2>/dev/null || true
    LOG=$RAM_LOG
    # zhijack launches picoarch with stdout/stderr redirected to the SD
    # diagnostic log.  The exec'd runtime inherits those descriptors; close
    # them before unmount or the runtime itself keeps /mnt/sdcard busy.
    exec 1>/dev/null 2>/dev/null
    # BusyBox ash also keeps the original script FD open (often fd 10) when
    # a script re-execs a RAM copy. Close the inherited descriptor range; the
    # runtime only needs stdin/stdout/stderr, and stdout/stderr are now RAM.
    fd=3
    while [ "$fd" -le 64 ]; do
        eval "exec $fd>&- 2>/dev/null" || true
        fd=$((fd + 1))
    done
    # The launcher commonly inherits /mnt/sdcard as cwd; release that VFS
    # reference before attempting to unmount the filesystem.
    cd / || fail "cannot change working directory before SD unmount"
    disable_sd_swap
    release_mount_users
    sync
    unmount_ok=0
    unmount_try=0
    while [ "$unmount_try" -lt 10 ]; do
        if umount "$MOUNTPOINT" 2>>"$LOG"; then unmount_ok=1; break; fi
        sleep 1
        unmount_try=$((unmount_try + 1))
    done
    if [ "$unmount_ok" -eq 0 ]; then
        # Vendor BusyBox can retain a transient VFS reference even after all
        # users disappear.  -r first remounts read-only, then detaches; unlike
        # -f/-l it never exports a filesystem still writable by the console.
        log "UNMOUNT_RETRY readonly-remount"
        if umount -r "$MOUNTPOINT" 2>>"$LOG"; then unmount_ok=1; fi
    fi
    [ "$unmount_ok" -eq 1 ] || fail "could not unmount $MOUNTPOINT; close all SD users first"
    mounted=0
    # Verify the exact backing device is no longer mounted anywhere.
    awk -v d="$BLOCK_DEVICE" '$1 == d { found=1 } END { exit found ? 0 : 1 }' "$PROC_MOUNTS" &&
        fail "$BLOCK_DEVICE remains mounted"
    create_gadget || fail "could not create mass-storage gadget"
    printf '%s\n' "$BLOCK_DEVICE" > "$GADGET/functions/mass_storage.usb0/lun.0/file" || fail "could not attach SD block device"
    printf '%s\n' "$UDC_NAME" > "$GADGET/UDC" || fail "could not bind UDC"
    bound=1
    log "READY device=$BLOCK_DEVICE; unplug USB cable to exit safely"
    printf 'USB storage ready. Eject it on the PC, then unplug the cable.\n'

    # Do not interpret the initial not-attached state as a disconnect.
    detached_samples=0
    while :; do
        state=$(cat "$SYS_ROOT/class/udc/$UDC_NAME/state" 2>/dev/null || echo detached)
        [ "$state" = configured ] && configured_once=1
        if [ "$configured_once" -eq 1 ] && [ "$state" = 'not attached' ]; then
            detached_samples=$((detached_samples + 1))
            [ "$detached_samples" -ge 2 ] && break
        else
            detached_samples=0
        fi
        sleep 1
    done
    log "HOST_DISCONNECTED restoring local SD access"
}

status_mode() {
    state=$(cat "$SYS_ROOT/class/udc/$UDC_NAME/state" 2>/dev/null || echo unavailable)
    active=$(cat "$GADGET/UDC" 2>/dev/null || true)
    if [ -n "$active" ]; then printf 'active (%s, UDC %s)\n' "$state" "$active"; else printf 'inactive (%s)\n' "$state"; fi
}

case "${1:-run}" in
    run|start) run_mode ;;
    mtp) run_mtp_mode ;;
    status) status_mode ;;
    stop) fail "stop is intentionally disabled; eject on the PC and unplug the cable" ;;
    *) printf 'Usage: %s {run|start|mtp|status}\n' "$0" >&2; exit 2 ;;
esac
