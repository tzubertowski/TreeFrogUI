#!/bin/sh
# zhijack.sh for @DEV_LABEL@ — GENERATED from hijack/zhijack.tpl.sh by
# build_release.sh. Do not edit on the SD; edit the template and regenerate.
#
# Reached via stock boot: rkgame (verified, untouched) -> setting.xml autorun ->
# libemu_tfhijack.so forks this script (rkgame stays alive, keeping the
# cubevol gpio -> /tmp/joy_key input pipeline up). Everything device-specific
# is HARDCODED below — no runtime device detection. /tmp/tfdevice.env is still
# written because picoarch and the standalone frontends (pcsx4all, lgpt,
# pico286) read it.
mkdir /tmp/zhijack.lock 2>/dev/null || exit 0

# Diagnostics are OPT-IN so we don't chew the SD card in normal use: logging is
# ON only if the user pre-created /mnt/sdcard/log.txt. Otherwise LOG=/dev/null and
# every write below is a no-op (and picoarch's own dbg_log is gated the same way,
# on log.txt existing). To debug: drop an empty log.txt on the card and reboot.
if [ -f /mnt/sdcard/log.txt ]; then
    LOG=/mnt/sdcard/log.txt
    mv "$LOG" "$LOG.prev" 2>/dev/null
    : > "$LOG"
    echo "=== zhijack boot [@DEV_LABEL@] $(date '+%H:%M:%S' 2>/dev/null) ===" >> "$LOG"
    sync
else
    LOG=/dev/null
fi

# Freeze icube (the respawner), THEN kill rkgame. Devices that boot through
# icube (R36SX, SF3000, GB350) respawn any killed rkgame, and the fresh
# instance redraws the stock menu over our frames (flicker/ghosting); a merely
# frozen rkgame (SIGSTOP) glitched the display too. Frozen icube = no respawn;
# dead rkgame = nothing reacting to SELECT+START (its stock exit-game hotkey).
# On rkgame-direct devices (SF3500/HD/SF3100) there is no icube: STOP no-ops.
kill -STOP $(pidof icube) 2>/dev/null
killall rkgame 2>/dev/null
echo "icube frozen, rkgame killed" >> "$LOG"

cat > /tmp/tfdevice.env <<EOF
TF_DEVICE=@DEV@
TF_PANEL_W=@PW@
TF_PANEL_H=@PH@
TF_UI_SCALE=150
TF_ASPECT_NUM=@ASPN@
TF_ASPECT_DEN=@ASPD@
TF_ROTATE=@ROT@
TF_PRESENT=@PRESENT@
TF_DRIVER=/mnt/sdcard/cubegm/@DRIVER@
EOF
export TF_DEVICE=@DEV@ TF_PANEL_W=@PW@ TF_PANEL_H=@PH@ TF_UI_SCALE=150

# R36SX driver self-selection. Some kernels (v2.7-class, but firmware traits    #@R36@
# vary WITHIN 2.6/2.7, so no offline identification works) make the full v2.6   #@R36@
# driver SIGBUS in hcge_open. Measure instead of guessing: run the full driver; #@R36@
# if frogui dies with SIGBUS twice, switch permanently (marker file on SD) to   #@R36@
# driver_r36sx27.so, the variant with the crashing 2D engine stubbed out.       #@R36@
DRV_SAFE=/mnt/sdcard/cubegm/driver_r36sx27.so #@R36@
DRV_FLAG=/mnt/sdcard/cubegm/driver27.flag #@R36@
SIGBUS_N=0 #@R36@
if [ -f "$DRV_FLAG" ] && [ -f "$DRV_SAFE" ]; then #@R36@
    sed -i "s|^TF_DRIVER=.*|TF_DRIVER=$DRV_SAFE|" /tmp/tfdevice.env #@R36@
    echo "driver: SAFE variant (previous boots hit SIGBUS)" >> "$LOG" #@R36@
fi #@R36@

echo "processes at boot:" >> "$LOG"; ps >> "$LOG" 2>&1; [ "$LOG" = /dev/null ] || sync

export LD_LIBRARY_PATH=/mnt/sdcard/cubegm/lib:/mnt/sdcard/cubegm/usr/lib:$LD_LIBRARY_PATH

# CPU: force max-performance governor (helps every emulator).
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    [ -w "$g" ] && echo performance > "$g" 2>/dev/null
done
for c in /sys/devices/system/cpu/cpu*/cpufreq; do
    mx=$(cat "$c/cpuinfo_max_freq" 2>/dev/null)
    [ -n "$mx" ] && [ -w "$c/scaling_min_freq" ] && echo "$mx" > "$c/scaling_min_freq" 2>/dev/null
done

# Input: cubevol (reads gpio -> /tmp/joy_key shm) must be up; picoarch reads the shm.
pidof cubevol >/dev/null 2>&1 || { [ -x /usr/bin/cubevol ] && /usr/bin/cubevol & }
sleep 0.5

PICOARCH=/mnt/sdcard/cubegm/picoarch
PICOARCH_HI=/mnt/sdcard/cubegm/picoarch_hi
FROGUI_CORE=/mnt/sdcard/cubegm/cores/frogui_libretro.so
LAUNCH=/tmp/frogui_launch.txt

# Self-healing HW-render fallback (disp_frame devices, non-R36SX). A few units  #@HW@
# can't drive the HW path and picoarch ABORTS on it (SIGABRT/SIGBUS) before it  #@HW@
# ever renders a frame. Crash-only: count such crashes, and after 2 strikes in  #@HW@
# one boot switch permanently to software (marker on SD). Crash-only cannot     #@HW@
# false-trigger on a healthy unit (which never crashes). Once HW has proven     #@HW@
# itself (/tmp/hw_rendered), later crashes are game bugs, not HW, so ignored.    #@HW@
FORCE_SW_FLAG=/mnt/sdcard/cubegm/force_sw.flag #@HW@
HW_CRASH_N=0 #@HW@
if [ -f "$FORCE_SW_FLAG" ]; then export TF_FORCE_SW=1; echo "display: SW forced (marker present)" >> "$LOG"; fi #@HW@
hw_crash_check() { #@HW@
    [ -n "$FORCE_SW_FLAG" ] || return 0 #@HW@
    [ -f "$FORCE_SW_FLAG" ] && return 0 #@HW@
    [ -f /tmp/hw_rendered ] && return 0 #@HW@
    [ "$1" -ge 129 ] 2>/dev/null || return 0 #@HW@
    HW_CRASH_N=$((HW_CRASH_N+1)) #@HW@
    echo "HW crash rc=$1 (strike $HW_CRASH_N, before any HW frame)" >> "$LOG" #@HW@
    if [ "$HW_CRASH_N" -ge 2 ]; then #@HW@
        touch "$FORCE_SW_FLAG"; export TF_FORCE_SW=1; sync #@HW@
        echo "2x HW crash → forcing software rendering permanently" >> "$LOG" #@HW@
    fi #@HW@
} #@HW@
# R36SX (no FORCE_SW_FLAG): make hw_crash_check a harmless no-op.
[ -n "$FORCE_SW_FLAG" ] || hw_crash_check() { :; }

ITER=0
while true; do
    ITER=$((ITER+1))
    rm -f "$LAUNCH"
    killall rkgame 2>/dev/null #@KILL@
    echo "--- iter $ITER: frogui ---" >> "$LOG"
    "$PICOARCH" "$FROGUI_CORE" "$FROGUI_CORE" >> "$LOG" 2>&1
    RC=$?
    echo "frogui exited rc=$RC" >> "$LOG"
    hw_crash_check "$RC"
    # SIGBUS in the menu with the full driver → count, and after 2 strikes    #@R36@
    # flip to the safe driver for this and every future boot.                 #@R36@
    if [ "$RC" = 138 ] && [ ! -f "$DRV_FLAG" ] && [ -f "$DRV_SAFE" ]; then #@R36@
        SIGBUS_N=$((SIGBUS_N+1)) #@R36@
        if [ "$SIGBUS_N" -ge 2 ]; then #@R36@
            touch "$DRV_FLAG" #@R36@
            sed -i "s|^TF_DRIVER=.*|TF_DRIVER=$DRV_SAFE|" /tmp/tfdevice.env #@R36@
            echo "driver: 2x SIGBUS with full driver → switching to SAFE variant permanently" >> "$LOG" #@R36@
            sync #@R36@
        fi #@R36@
    fi #@R36@

    if [ -f "$LAUNCH" ]; then
        CORE_PATH=$(sed -n '1p' "$LAUNCH")
        ROM_PATH=$(sed -n '2p' "$LAUNCH")
        rm -f "$LAUNCH"
        if [ -n "$CORE_PATH" ] && [ -n "$ROM_PATH" ]; then
            killall rkgame 2>/dev/null #@KILL@
            sleep 0.3
            BIN="$PICOARCH"
            case "$CORE_PATH" in
                *gpsp*|*pcsx*|*ps1*) [ -f "$PICOARCH_HI" ] && BIN="$PICOARCH_HI" ;;
            esac
            echo "--- iter $ITER: game [$CORE_PATH] via $BIN ---" >> "$LOG"
            "$BIN" "$CORE_PATH" "$ROM_PATH" >> "$LOG" 2>&1
            GRC=$?
            echo "game exited rc=$GRC" >> "$LOG"
            hw_crash_check "$GRC"
        fi
    fi
    sleep 0.2
done
