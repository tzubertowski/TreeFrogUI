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

LOG=/mnt/sdcard/log.txt
[ -f "$LOG" ] && mv "$LOG" "$LOG.prev"
> "$LOG"
echo "=== zhijack boot [@DEV_LABEL@] $(date '+%H:%M:%S' 2>/dev/null) ===" >> "$LOG"
sync   # flush to FAT now: proves zhijack ran even if a later step hangs

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

# R36SX v2.7 detection: its stock cubegm/driver.so is ENCRYPTED (no ELF magic;   #@R36@
# v2.6's is a plain ELF). On the v2.7 kernel our bundled v2.6 driver SIGBUSes in  #@R36@
# hcge_open (driver pool hands back a kseg pointer), so v2.7 gets a variant with  #@R36@
# hcge_open stubbed to NULL: the driver treats the 2D engine as unavailable.      #@R36@
if [ "$(head -c4 /mnt/sdcard/cubegm/driver.so 2>/dev/null)" != "$(printf '\177ELF')" ] && [ -f /mnt/sdcard/cubegm/driver_r36sx27.so ]; then #@R36@
    sed -i 's|^TF_DRIVER=.*|TF_DRIVER=/mnt/sdcard/cubegm/driver_r36sx27.so|' /tmp/tfdevice.env #@R36@
    echo "v2.7 detected (encrypted stock driver): using driver_r36sx27.so" >> "$LOG"; sync #@R36@
fi #@R36@

echo "processes at boot:" >> "$LOG"; ps >> "$LOG" 2>&1; sync

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

ITER=0
while true; do
    ITER=$((ITER+1))
    rm -f "$LAUNCH"
    killall rkgame 2>/dev/null #@KILL@
    echo "--- iter $ITER: frogui ---" >> "$LOG"
    "$PICOARCH" "$FROGUI_CORE" "$FROGUI_CORE" >> "$LOG" 2>&1
    echo "frogui exited rc=$?" >> "$LOG"

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
            echo "game exited rc=$?" >> "$LOG"
        fi
    fi
    sleep 0.2
done
