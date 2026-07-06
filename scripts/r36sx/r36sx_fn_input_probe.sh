#!/bin/sh
# Probe no destructivo para descubrir cómo aparece FN en R36SX.
set -u
TS="$(date +%Y%m%d_%H%M%S 2>/dev/null || echo now)"
OUT="/mnt/sdcard/r36sx_fn_probe_$TS"
mkdir -p "$OUT"
LOG="$OUT/summary.txt"

echo "R36SX FN input probe $TS" > "$LOG"
echo "Durante la captura, presiona FN, FN+A, FN+B, FN+START y suelta todos." >> "$LOG"

capture_cmd() {
  name="$1"; shift
  echo "\n### $*" >> "$LOG"
  sh -c "$*" >> "$OUT/$name" 2>&1 || true
  cat "$OUT/$name" >> "$LOG" 2>/dev/null || true
}

capture_cmd proc_bus_input_devices 'cat /proc/bus/input/devices 2>/dev/null'
capture_cmd sys_class_input 'find /sys/class/input -maxdepth 3 -type f 2>/dev/null | while read f; do echo "--- $f"; cat "$f" 2>/dev/null; done'
capture_cmd dev_input_listing 'ls -la /dev/input 2>/dev/null; ls -la /dev 2>/dev/null | grep -Ei "event|js|joy|key|gpio|input"'
capture_cmd ipcs_m 'ipcs -m 2>/dev/null || true'
capture_cmd proc_modules 'cat /proc/modules 2>/dev/null || true'
capture_cmd processes 'ps 2>/dev/null || true'

# Captura breve de eventos si existen. Puede no haber /dev/input en esta plataforma.
if [ -d /dev/input ]; then
  for dev in /dev/input/event*; do
    [ -e "$dev" ] || continue
    base="$(basename "$dev")"
    echo "Capturando $dev durante 10 segundos..." | tee -a "$LOG"
    (
      if command -v hexdump >/dev/null 2>&1; then
        hexdump -Cv "$dev" > "$OUT/${base}_capture.hex" 2>/dev/null
      else
        od -An -tx1 "$dev" > "$OUT/${base}_capture.hex" 2>/dev/null
      fi
    ) &
    PID=$!
    sleep 10
    kill "$PID" 2>/dev/null || true
  done
fi

echo "FN probe complete: $OUT" | tee -a "$LOG"
echo "Sube summary.txt y cualquier *_capture.hex que se haya generado." | tee -a "$LOG"
