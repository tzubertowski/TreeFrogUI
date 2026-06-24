#!/bin/sh
# zhijack.sh — TreeFrogUI launcher for SF3500.
#
# Reached AFTER stock boot: bootloader -> kernel -> init -> rkgame (verified,
# untouched) -> autorun loads libemu_tfhijack.so -> retro_load_game() execl's
# this script, replacing the rkgame process. From here it is the same job
# icube does on R36SX/SF3000: detect device, set perf, run the picoarch frogui
# menu loop. We deliberately do NOT touch icube/rkgame so the SF3500 verifier
# stays happy.
LOG=/mnt/sdcard/log.txt
[ -f "$LOG" ] && mv "$LOG" "$LOG.prev"
> "$LOG"
echo "=== zhijack boot $(date '+%H:%M:%S' 2>/dev/null) ===" >> "$LOG"
sync   # flush to FAT now: proves zhijack ran even if a later step hangs

# rkgame ran us in-process (execl), so there is usually no rkgame left to kill;
# if the frontend forked a child for the core, the parent rkgame is killed here
# to free the display/input. Killing "rkgame" never matches our own sh process.
killall rkgame    2>/dev/null
killall hcprojector 2>/dev/null

export LD_LIBRARY_PATH=/mnt/sdcard/cubegm/lib:/mnt/sdcard/cubegm/usr/lib:$LD_LIBRARY_PATH

# Detect device + write /tmp/tfdevice.env (single source of truth: picoarch and
# the standalone frontends read it). On SF3500 this resolves to driver_sf3500.so.
[ -f /mnt/sdcard/cubegm/tf_detect.sh ] && sh /mnt/sdcard/cubegm/tf_detect.sh
[ -f /tmp/tfdevice.env ] && . /tmp/tfdevice.env && export TF_DEVICE TF_PANEL_W TF_PANEL_H TF_UI_SCALE
echo "detected: TF_DEVICE=$TF_DEVICE panel=${TF_PANEL_W}x${TF_PANEL_H} driver=$TF_DRIVER" >> "$LOG"
sync

# CPU: force max-performance governor (helps every emulator).
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    [ -w "$g" ] && echo performance > "$g" 2>/dev/null
done
for c in /sys/devices/system/cpu/cpu*/cpufreq; do
    mx=$(cat "$c/cpuinfo_max_freq" 2>/dev/null)
    [ -n "$mx" ] && [ -w "$c/scaling_min_freq" ] && echo "$mx" > "$c/scaling_min_freq" 2>/dev/null
done

# cubevol owns the power button + the /tmp/joy_key input shmem picoarch reads.
if ! pidof cubevol > /dev/null 2>&1; then
    echo "starting cubevol" >> "$LOG"
    [ -x /usr/bin/cubevol ] && /usr/bin/cubevol &
    sleep 0.3
fi

PICOARCH=/mnt/sdcard/cubegm/picoarch
PICOARCH_HI=/mnt/sdcard/cubegm/picoarch_hi
FROGUI_CORE=/mnt/sdcard/cubegm/cores/frogui_libretro.so
LAUNCH=/tmp/frogui_launch.txt

ITER=0
while true; do
    ITER=$((ITER+1))
    rm -f "$LAUNCH"
    killall rkgame 2>/dev/null
    echo "--- iter $ITER: frogui ---" >> "$LOG"
    "$PICOARCH" "$FROGUI_CORE" "$FROGUI_CORE" >> "$LOG" 2>&1
    echo "frogui exited rc=$?" >> "$LOG"

    if [ -f "$LAUNCH" ]; then
        CORE_PATH=$(sed -n '1p' "$LAUNCH")
        ROM_PATH=$(sed -n '2p' "$LAUNCH")
        rm -f "$LAUNCH"
        if [ -n "$CORE_PATH" ] && [ -n "$ROM_PATH" ]; then
            killall rkgame 2>/dev/null; sleep 0.3
            BIN="$PICOARCH"
            case "$CORE_PATH" in
                *gpsp*|*pcsx*|*ps1*) [ -f "$PICOARCH_HI" ] && BIN="$PICOARCH_HI" ;;
            esac
            echo "--- iter $ITER: game [$CORE_PATH] via $BIN ---" >> "$LOG"
            "$BIN" "$CORE_PATH" "$ROM_PATH" >> "$LOG" 2>&1
            echo "game exited rc=$?" >> "$LOG"
        fi
    fi
    sleep 0.2
done
