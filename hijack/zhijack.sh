#!/bin/sh
# zhijack.sh — TreeFrogUI launcher for SF3500.
#
# Reached AFTER stock boot: bootloader -> kernel -> init -> rkgame (verified,
# untouched) -> autorun loads libemu_tfhijack.so -> retro_load_game() execl's
# this script, replacing the rkgame process. From here it is the same job
# icube does on R36SX/SF3000: detect device, set perf, run the picoarch frogui
# menu loop. We deliberately do NOT touch icube/rkgame so the SF3500 verifier
# stays happy.
# FORK approach: the hijack core forks us (does NOT execl), so rkgame stays ALIVE
# running our "game" — keeping the input pipeline up (cubevol reads gpio → joy_key
# shm, which picoarch reads). We must NOT kill rkgame here (that kills input) and
# the core forks only once, so no stacking. Single-instance guard just in case.
mkdir /tmp/zhijack.lock 2>/dev/null || exit 0

LOG=/mnt/sdcard/log.txt
[ -f "$LOG" ] && mv "$LOG" "$LOG.prev"
> "$LOG"
echo "=== zhijack boot $(date '+%H:%M:%S' 2>/dev/null) ===" >> "$LOG"
sync   # flush to FAT now: proves zhijack ran even if a later step hangs

# GRAB the firmware-decrypted plaintext driver/rkgame (the SF3500 stock driver.so
# on the SD is encrypted; the boot decrypts it to /tmp/cubegm/). One-shot dump.
[ -f /tmp/cubegm/driver.so ] && [ ! -f /mnt/sdcard/driver_sf3500_dec.so ] && \
    cp /tmp/cubegm/driver.so /mnt/sdcard/driver_sf3500_dec.so && sync
[ -f /tmp/cubegm/rkgame ] && [ ! -f /mnt/sdcard/rkgame_dec ] && \
    cp /tmp/cubegm/rkgame /mnt/sdcard/rkgame_dec && sync

# rkgame is left ALIVE (running our hijack core, idle, not drawing). Killing it
# makes icube respawn a fresh rkgame that redraws its menu over our framebuffer —
# on the R36SX fb-write path that corrupts/flickers the screen after a few seconds.
echo "processes at boot:" >> "$LOG"; ps >> "$LOG" 2>&1; sync

export LD_LIBRARY_PATH=/mnt/sdcard/cubegm/lib:/mnt/sdcard/cubegm/usr/lib:$LD_LIBRARY_PATH

# Detect device + write /tmp/tfdevice.env (single source of truth: picoarch and
# the standalone frontends read it). On SF3500 this resolves to driver_sf3500.so.
[ -f /mnt/sdcard/cubegm/tf_detect.sh ] && sh /mnt/sdcard/cubegm/tf_detect.sh
[ -f /tmp/tfdevice.env ] && . /tmp/tfdevice.env && export TF_DEVICE TF_PANEL_W TF_PANEL_H TF_UI_SCALE
echo "detected: TF_DEVICE=$TF_DEVICE panel=${TF_PANEL_W}x${TF_PANEL_H} driver=$TF_DRIVER" >> "$LOG"
sync

# rkgame handling is PER-DEVICE:
#   R36SX (fb-write path): keep rkgame ALIVE. Killing it makes icube respawn a
#     fresh rkgame that redraws its menu over our framebuffer → flicker/corruption
#     after a few seconds. It stays idle (running our hijack core), so no conflict.
#   Everyone else (SF3500/SF3000/HD/SF3100/GB350, disp_frame): kill it as before
#     (proven; cubevol keeps the input pipeline alive independently).
maybe_kill_rkgame() { [ "$TF_DEVICE" = "R36SX" ] || killall rkgame 2>/dev/null; }

# CPU: force max-performance governor (helps every emulator).
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    [ -w "$g" ] && echo performance > "$g" 2>/dev/null
done
for c in /sys/devices/system/cpu/cpu*/cpufreq; do
    mx=$(cat "$c/cpuinfo_max_freq" 2>/dev/null)
    [ -n "$mx" ] && [ -w "$c/scaling_min_freq" ] && echo "$mx" > "$c/scaling_min_freq" 2>/dev/null
done

# Input: cubevol (already running, reads gpio → /tmp/joy_key shm) provides input.
# rkgame is alive (we forked), so the pipeline is intact. Don't restart cubevol —
# just ensure it's up.
pidof cubevol >/dev/null 2>&1 || { [ -x /usr/bin/cubevol ] && /usr/bin/cubevol & }
sleep 0.5

PICOARCH=/mnt/sdcard/cubegm/picoarch
PICOARCH_HI=/mnt/sdcard/cubegm/picoarch_hi
FROGUI_CORE=/mnt/sdcard/cubegm/cores/frogui_libretro.so
LAUNCH=/tmp/frogui_launch.txt

ITER=0
while true; do
    ITER=$((ITER+1))
    rm -f "$LAUNCH"
    maybe_kill_rkgame
    echo "--- iter $ITER: frogui ---" >> "$LOG"
    "$PICOARCH" "$FROGUI_CORE" "$FROGUI_CORE" >> "$LOG" 2>&1
    echo "frogui exited rc=$?" >> "$LOG"

    if [ -f "$LAUNCH" ]; then
        CORE_PATH=$(sed -n '1p' "$LAUNCH")
        ROM_PATH=$(sed -n '2p' "$LAUNCH")
        rm -f "$LAUNCH"
        if [ -n "$CORE_PATH" ] && [ -n "$ROM_PATH" ]; then
            maybe_kill_rkgame; sleep 0.3
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
