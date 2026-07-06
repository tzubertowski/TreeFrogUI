#!/bin/sh
# Captura estado de la instalación estable TreeFrogUI en SD.
set -u
TS="$(date +%Y%m%d_%H%M%S 2>/dev/null || echo now)"
OUT="/mnt/sdcard/r36sx_stable_state_$TS"
mkdir -p "$OUT"
LOG="$OUT/summary.txt"
{
  echo "R36SX stable state $TS"
  echo "## cubegm files"
  ls -la /mnt/sdcard/cubegm 2>/dev/null | sed -n '1,120p'
  echo "\n## driver files"
  ls -la /mnt/sdcard/cubegm/driver* 2>/dev/null || true
  echo "\n## settings"
  cat /mnt/sdcard/frogui/settings.txt 2>/dev/null || true
  echo "\n## logs"
  ls -la /mnt/sdcard/log* 2>/dev/null || true
} > "$LOG" 2>&1

echo "Stable state captured: $OUT"
