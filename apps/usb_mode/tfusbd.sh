#!/bin/sh
# tfusbd - background USB manager for TreeFrogUI (HiChip HC16xx, GB350).
#
# Keeps the OTG port (musb0) useful for both directions without user action:
#   IDLE : alternate HOST (OTG devices: mouse, flash drive, pad) and
#          PERIPHERAL (MTP gadget bound, waiting for a PC)
#   PC   : a PC is talking to us (USB frame counter is running) -> stay MTP
#   DEV  : a USB device is attached in host role -> stay host
# PC presence is detected from the MUSB FRAME register (SOF counter): on this
# board VBUS is always on and the UDC state never leaves "configured" after
# an unplug, so neither can be used.
#
# tfmtp (MTP responder) runs the whole time at low priority; the SD card stays
# mounted and games/menus keep running.
#
#   tfusbd.sh start | stop | status
set -u
ROOT=/mnt/sdcard
CG=$ROOT/cubegm
G=/sys/kernel/config/usb_gadget/treefrog_storage
M0=/sys/devices/platform/soc/18844000.usb/musb-hdrc.0.auto
UDC=musb-hdrc.0.auto
FRAME=0x1884400C
LOG=/tmp/tfusbd.log
PIDF=/tmp/tfusbd.pid
HOST_SLICE=${TFUSBD_HOST_SLICE:-2}      # seconds in host role per idle cycle
PERI_SLICE=${TFUSBD_PERI_SLICE:-2}      # seconds in peripheral role per idle cycle
NICE=${TFUSBD_NICE:-10}

log() {
    [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 262144 ] && mv "$LOG" "$LOG.1"
    printf '%s %s\n' "$(cut -d' ' -f1 /proc/uptime)" "$*" >> "$LOG"
}

frame_running() {   # true if the host is sending SOFs
    a=$(devmem $FRAME 16); usleep 3000; b=$(devmem $FRAME 16)
    [ "$a" != "$b" ]
}
host_devices() { ls /sys/bus/usb/devices 2>/dev/null | grep -c '^1-'; }
udc_state() { cat /sys/class/udc/$UDC/state 2>/dev/null || echo none; }

ensure_gadget() {
    grep -q ' /sys/kernel/config ' /proc/mounts || mount -t configfs none /sys/kernel/config 2>/dev/null
    if ! grep -q '^usb_f_mtp ' /proc/modules; then
        # same order as usb_mode.sh on a cold boot
        modprobe libcomposite 2>/dev/null
        grep -q '^usb_f_mass_storage ' /proc/modules || insmod "$CG/modules/$(uname -r)/usb_f_mass_storage.ko" 2>>"$LOG"
        insmod "$CG/modules/$(uname -r)/usb_f_mtp.ko" 2>>"$LOG"
        log "modules: $(grep -E '^(usb_f_mtp|usb_f_mass_storage|libcomposite) ' /proc/modules | cut -d' ' -f1 | tr '\n' ' ')"
    fi
    [ -d "$G/functions/mtp.usb0" ] && [ -L "$G/configs/c.1/mtp.usb0" ] && return 0
    mkdir -p "$G/strings/0x409" "$G/configs/c.1/strings/0x409" || return 1
    echo 0x18d1 > "$G/idVendor"; echo 0x4e22 > "$G/idProduct"
    echo 0x0100 > "$G/bcdDevice"; echo 0x0200 > "$G/bcdUSB"
    printf 'TreeFrogUI-%s\n' "$(cut -c1-16 /etc/machine-id 2>/dev/null || echo SF3000)" > "$G/strings/0x409/serialnumber"
    echo TreeFrogUI > "$G/strings/0x409/manufacturer"
    echo 'TreeFrogUI MTP' > "$G/strings/0x409/product"
    echo 'MTP file access' > "$G/configs/c.1/strings/0x409/configuration"
    echo 120 > "$G/configs/c.1/MaxPower"
    [ -d "$G/functions/mtp.usb0" ] || mkdir "$G/functions/mtp.usb0" || return 1
    if [ -d "$G/os_desc" ]; then
        echo 1 > "$G/os_desc/b_vendor_code"; echo MSFT100 > "$G/os_desc/qw_sign"
        mkdir -p "$G/functions/mtp.usb0/os_desc/interface.MTP"
        echo MTP > "$G/functions/mtp.usb0/os_desc/interface.MTP/compatible_id"
        [ -L "$G/os_desc/c.1" ] || ln -s "$G/configs/c.1" "$G/os_desc/c.1"
        echo 1 > "$G/os_desc/use"
    fi
    [ -L "$G/configs/c.1/mtp.usb0" ] || ln -s "$G/functions/mtp.usb0" "$G/configs/c.1/mtp.usb0"
}

responder_pid=
ensure_responder() {
    [ -n "$responder_pid" ] && kill -0 "$responder_pid" 2>/dev/null && return 0
    if [ -f "$ROOT/log.txt" ]; then mlog="$ROOT/log.txt"; else mlog=/dev/null; fi   # /tmp is RAM
    nice -n "$NICE" "$CG/tfmtp" "$ROOT" >> "$mlog" 2>&1 &
    responder_pid=$!
    log "responder started pid=$responder_pid"
}

role_host() {
    [ -n "$(cat $G/UDC 2>/dev/null)" ] && echo "" > "$G/UDC" 2>/dev/null
    echo host > "$M0/mode" 2>/dev/null
}
role_peripheral() {
    echo peripheral > "$M0/mode" 2>/dev/null
    [ -z "$(cat $G/UDC 2>/dev/null)" ] && echo "$UDC" > "$G/UDC" 2>/dev/null
}

usb_mode_running() { ps | grep -v grep | grep -q 'usb_mode.sh'; }

takeover() {
    # A session started from the TreeFrog menu is ended exactly like the B
    # button does it (exit flag + SIGTERM to the responder), so usb_mode.sh
    # runs its own teardown and FrogUI comes back normally.
    if usb_mode_running; then
        : > /tmp/treefrog_mtp_exit
        old=$(pidof tfmtp mtp-server)
        [ -n "$old" ] && kill -TERM $old 2>/dev/null
        log "takeover: asked usb_mode.sh to exit (responder $old)"
        n=0; while usb_mode_running && [ $n -lt 60 ]; do sleep 0.5; n=$((n + 1)); done
        log "takeover: usb_mode.sh $(usb_mode_running && echo 'STILL RUNNING' || echo exited) after $((n / 2))s"
        sleep 2
    fi
    old=$(pidof tfmtp)
    [ -n "$old" ] && { kill $old 2>/dev/null; log "takeover: stopped stray tfmtp $old"; sleep 0.5; }
}

run() {
    echo $$ > "$PIDF"
    log "=== tfusbd start pid=$$ host=${HOST_SLICE}s peri=${PERI_SLICE}s nice=$NICE ==="
    renice -n "$NICE" $$ >/dev/null 2>&1
    sleep 3   # let the command that started us finish its MTP reply
    takeover
    ensure_gadget || { log "FATAL gadget setup failed"; exit 1; }
    ensure_responder
    state=
    role_host; sleep 0.3
    while :; do
        ensure_responder
        if usb_mode_running; then sleep 2; continue; fi
        case "$state" in
        PC)
            miss=0
            while [ $miss -lt 3 ]; do
                if frame_running; then miss=0; else miss=$((miss + 1)); fi
                sleep 1
                ensure_responder
            done
            log "PC gone (udc=$(udc_state))"
            role_host; state=; sleep 0.3
            ;;
        DEV)
            while [ "$(host_devices)" -gt 1 ]; do sleep 1; done
            log "USB device removed"
            state=
            ;;
        *)
            # host slice: does anything enumerate?
            [ "$(cat $M0/mode)" = b_peripheral ] && role_host
            t=0
            while [ $t -lt $((HOST_SLICE * 4)) ]; do
                if [ "$(host_devices)" -gt 1 ]; then
                    sleep 1
                    log "USB device attached: $(cat /sys/bus/usb/devices/1-1/manufacturer /sys/bus/usb/devices/1-1/product 2>/dev/null | tr '\n' ' ')(idVendor=$(cat /sys/bus/usb/devices/1-1/idVendor 2>/dev/null) class=$(cat /sys/bus/usb/devices/1-1:1.0/bInterfaceClass 2>/dev/null))"
                    state=DEV; break
                fi
                usleep 250000; t=$((t + 1))
            done
            [ "$state" = DEV ] && continue
            # peripheral slice: does a PC start talking?
            role_peripheral
            t=0
            while [ $t -lt $((PERI_SLICE * 4)) ]; do
                # fresh bind starts at "not attached"; any other state means a
                # host reset us, and SOFs follow as soon as it enumerates
                if frame_running || [ "$(udc_state)" != 'not attached' ]; then
                    log "PC detected (udc=$(udc_state))"
                    state=PC; break
                fi
                usleep 250000; t=$((t + 1))
            done
            [ "$state" = PC ] && continue
            role_host
            ;;
        esac
    done
}

case "${1:-}" in
start)
    if [ -f "$PIDF" ] && kill -0 "$(cat $PIDF)" 2>/dev/null; then echo "already running"; exit 0; fi
    # Prefer the C daemon (no polling forks); this script is the fallback.
    # Both run from RAM so the SD card is never kept busy.
    if [ -x "$CG/tfusbd" ] && [ "${TFUSBD_SHELL:-0}" != 1 ] && cp "$CG/tfusbd" /tmp/tfusbd.bin 2>/dev/null && chmod +x /tmp/tfusbd.bin; then
        /tmp/tfusbd.bin -d
        echo "started (C daemon)"
    else
        cp "$0" /tmp/tfusbd.run.sh 2>/dev/null && chmod +x /tmp/tfusbd.run.sh
        setsid /bin/sh /tmp/tfusbd.run.sh run </dev/null >/dev/null 2>&1 &
        echo "started (shell daemon)"
    fi
    ;;
run) run ;;
stop)
    p=$(cat "$PIDF" 2>/dev/null); [ -n "$p" ] && kill "$p" 2>/dev/null
    n=0; while [ -n "$p" ] && kill -0 "$p" 2>/dev/null && [ $n -lt 20 ]; do usleep 250000; n=$((n + 1)); done
    t=$(pidof tfmtp); [ -n "$t" ] && kill $t
    echo "" > "$G/UDC" 2>/dev/null; echo host > "$M0/mode" 2>/dev/null
    rm -f "$PIDF"; log "stopped"; echo stopped
    ;;
status)
    echo "daemon: $(cat $PIDF 2>/dev/null) [$(cat /tmp/tfusbd.state 2>/dev/null)] tfmtp: $(pidof tfmtp) mode: $(cat $M0/mode) udc: $(cat $G/UDC 2>/dev/null) state: $(udc_state) devices: $(host_devices)"
    tail -n 15 "$LOG" 2>/dev/null
    ;;
*) echo "usage: $0 start|stop|status"; exit 2 ;;
esac
