#!/bin/sh
# zhijack.sh for r36hd — GENERATED from hijack/zhijack.tpl.sh by
# build_release.sh. Modified to prevent permanent black screen on crash.
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
    echo "=== zhijack boot [r36hd] $(date '+%H:%M:%S' 2>/dev/null) ===" >> "$LOG"
    sync
else
    LOG=/dev/null
fi

# Offline updates: users drop the official update.zip into the SD-card root.
# Run a /tmp copy so the updater can atomically replace its own
# installed file. Status 10 means success: restart through the newly installed
# device launcher. Failures keep both the current installation and update ZIP.
if [ -f /mnt/sdcard/cubegm/tfupdate.sh ]; then
    cp /mnt/sdcard/cubegm/tfupdate.sh /tmp/tfupdate.sh 2>/dev/null
    if [ -f /tmp/tfupdate.sh ]; then
        sh /tmp/tfupdate.sh r36hd
        UPDATE_RC=$?
        if [ "$UPDATE_RC" = 10 ]; then
            echo "offline update installed; restarting launcher" >> "$LOG"
            rm -rf /tmp/zhijack.lock
            exec /mnt/sdcard/cubegm/zhijack.sh
            exit 1
        elif [ "$UPDATE_RC" != 0 ]; then
            echo "offline update failed rc=$UPDATE_RC; continuing current version" >> "$LOG"
        fi
    fi
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
TF_DEVICE=R36SX
TF_PANEL_W=640
TF_PANEL_H=480
TF_UI_SCALE=150
TF_ASPECT_NUM=4
TF_ASPECT_DEN=3
TF_ROTATE=0
TF_PRESENT=fbwrite
TF_DRIVER=/mnt/sdcard/cubegm/driver_r36sx.so
EOF
export TF_DEVICE=R36SX TF_PANEL_W=640 TF_PANEL_H=480 TF_UI_SCALE=150

# Some "SF3000"-branded units are really SF3500-class hardware (the "v3" / HDMI
# variant): same 854x480 panel geometry, but the SF3500 audio+display driver. The
# reliable tell is the stock driver.so format: classic SF3000 ships a PLAIN ELF
# driver, SF3500-class ships an ENCRYPTED one. If we're booting as SF3000 but the
# stock driver is encrypted, switch to driver_sf3500.so. Otherwise the classic
# SF3000 driver's audio (AUDDEC/I2SO) init fails on this hardware and picoarch
# SIGSEGVs on the NULL sound handle (+0x270) → black-screen boot loop.
if [ "$TF_DEVICE" = SF3000 ] && [ -f /mnt/sdcard/cubegm/driver_sf3500.so ] && \
   [ "$(head -c4 /mnt/sdcard/cubegm/driver.so 2>/dev/null)" != "$(printf '\177ELF')" ]; then
    sed -i -e 's/^TF_DEVICE=.*/TF_DEVICE=SF3500/' \
           -e 's|^TF_DRIVER=.*|TF_DRIVER=/mnt/sdcard/cubegm/driver_sf3500.so|' /tmp/tfdevice.env
    export TF_DEVICE=SF3500
    echo "SF3000 with encrypted (SF3500-class) driver detected → using driver_sf3500.so" >> "$LOG"
fi

# R36SX driver self-selection variable mapping.
DRV_SAFE=/mnt/sdcard/cubegm/driver_r36sx27.so
DRV_FLAG=/mnt/sdcard/cubegm/driver27.flag
SIGBUS_N=0
if [ -f "$DRV_FLAG" ] && [ -f "$DRV_SAFE" ]; then
    sed -i "s|^TF_DRIVER=.*|TF_DRIVER=$DRV_SAFE|" /tmp/tfdevice.env
    echo "driver: SAFE variant (previous boots hit SIGBUS)" >> "$LOG"
fi

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
if [ "$LOG" != /dev/null ]; then
    echo "CPU frequency policy after performance request:" >> "$LOG"
    for c in /sys/devices/system/cpu/cpu*/cpufreq; do
        echo "$c governor=$(cat "$c/scaling_governor" 2>/dev/null) cur=$(cat "$c/scaling_cur_freq" 2>/dev/null) min=$(cat "$c/scaling_min_freq" 2>/dev/null) max=$(cat "$c/scaling_max_freq" 2>/dev/null) hwmax=$(cat "$c/cpuinfo_max_freq" 2>/dev/null)" >> "$LOG"
    done
fi

# Input: cubevol (reads gpio -> /tmp/joy_key shm) must be up; picoarch reads the shm.
pidof cubevol >/dev/null 2>&1 || { [ -x /usr/bin/cubevol ] && /usr/bin/cubevol & }
sleep 0.5

# Optional: disable the power-button sleep (FrogUI Settings -> "Disable Sleep",
# default off, applies after restart). Live-patch every cubevol instance in RAM
# so the on-disk binary stays byte-identical -> passes SF3500 boot verification.
# The watcher also handles a genuine daemon crash/respawn. 0x406d84:0xac62bcc8 0x407088:0xae02bcc8 0x406bb0:0xac44bcc8 is the
# per-device set of validated sleep-arm text addresses (empty = device not
# supported). Long-press power-off is a separate path, untouched.
TF_NOSLEEP_ADDRS="0x406d84:0xac62bcc8 0x407088:0xae02bcc8 0x406bb0:0xac44bcc8"
if [ -n "$TF_NOSLEEP_ADDRS" ] && grep -q '^disable_sleep=on' /mnt/sdcard/frogui/settings.txt 2>/dev/null; then
    echo 0 > /proc/sys/kernel/yama/ptrace_scope 2>/dev/null
    [ -f /mnt/sdcard/cubegm/nosleep ] && /mnt/sdcard/cubegm/nosleep -w $TF_NOSLEEP_ADDRS >/dev/null 2>&1 &
fi

PICOARCH=/mnt/sdcard/cubegm/picoarch
PICOARCH_HI=/mnt/sdcard/cubegm/picoarch_hi
FROGUI_CORE=/mnt/sdcard/cubegm/cores/frogui_libretro.so
LAUNCH=/tmp/frogui_launch.txt

# MODIFICACIÓN DE SEGURIDAD: Se anula por completo la función hw_crash_check.
# Esto previene que se genere de manera imprevista el archivo force_sw.flag.
hw_crash_check() { :; }

ITER=0
while true; do
    ITER=$((ITER+1))
    rm -f "$LAUNCH"
    
    # MODIFICACIÓN DE SEGURIDAD: Eliminación proactiva e inmediata de banderas accidentales.
    # Evita de manera absoluta que queden restos de configuraciones erróneas en la SD.
    rm -f /mnt/sdcard/cubegm/driver27.flag /mnt/sdcard/cubegm/force_sw.flag 2>/dev/null

    echo "--- iter $ITER: frogui ---" >> "$LOG"
    "$PICOARCH" "$FROGUI_CORE" "$FROGUI_CORE" >> "$LOG" 2>&1
    RC=$?
    echo "frogui exited rc=$RC" >> "$LOG"
    hw_crash_check "$RC"
    
    # MODIFICACIÓN DE SEGURIDAD: Se desactivan las líneas reactivas del error 138 (SIGBUS).
    # La interfaz volverá a cargar infinitamente en lugar de forzar cambios permanentes de controlador.
    if [ "$RC" = 138 ] && [ ! -f "$DRV_FLAG" ] && [ -f "$DRV_SAFE" ]; then
        SIGBUS_N=$((SIGBUS_N+1))
        if [ "$SIGBUS_N" -ge 2 ]; then
            # touch "$DRV_FLAG"
            # sed -i "s|^TF_DRIVER=.*|TF_DRIVER=$DRV_SAFE|" /tmp/tfdevice.env
            echo "driver: 2x SIGBUS detectado - Ejecución forzada continua protegida" >> "$LOG"
            sync
        fi
    fi

    if [ -f "$LAUNCH" ]; then
        CORE_PATH=$(sed -n '1p' "$LAUNCH")
        ROM_PATH=$(sed -n '2p' "$LAUNCH")
        rm -f "$LAUNCH"
        if [ -n "$CORE_PATH" ] && [ -n "$ROM_PATH" ]; then
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
