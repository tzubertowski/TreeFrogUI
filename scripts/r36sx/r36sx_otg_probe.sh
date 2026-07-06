#!/bin/sh
# R36SX OTG read-only probe. Ejecutar en la consola, preferiblemente desde /mnt/sdcard.
set -u
TS="$(date +%Y%m%d_%H%M%S 2>/dev/null || echo now)"
OUT="/mnt/sdcard/r36sx_otg_probe_$TS"
mkdir -p "$OUT"
LOG="$OUT/summary.txt"

run() {
  echo "\n### $*" >> "$LOG"
  sh -c "$*" >> "$LOG" 2>&1
}

{
  echo "R36SX OTG probe $TS"
  echo "PWD=$(pwd)"
  echo "PATH=$PATH"
} > "$LOG"

run 'uname -a'
run 'cat /proc/cmdline'
run 'mount'
run 'cat /proc/modules 2>/dev/null || true'
run 'lsmod 2>/dev/null || true'
run 'ls -la /sys/class/udc 2>/dev/null || true'
run 'for f in /sys/class/udc/*/state /sys/class/udc/*/current_speed /sys/class/udc/*/soft_connect; do [ -e "$f" ] && echo "$f=$(cat "$f" 2>/dev/null)"; done'
run 'ls -la /sys/kernel/config 2>/dev/null || true'
run 'ls -la /sys/kernel/config/usb_gadget 2>/dev/null || true'
run 'for f in /sys/devices/platform/*musb*/mode /sys/devices/platform/*usb*/mode; do [ -e "$f" ] && echo "$f=$(cat "$f" 2>/dev/null)"; done'
run 'ls -la /dev/snd 2>/dev/null || true'
run 'cat /proc/asound/cards 2>/dev/null || true'
run 'cat /proc/asound/devices 2>/dev/null || true'
run 'find /lib/modules /mnt/sdcard -name "g_audio*.ko" -o -name "u_audio*.ko" -o -name "usb_f_uac*.ko" -o -name "g_mass_storage*.ko" -o -name "usb_f_mass_storage*.ko" -o -name "usb_f_mtp*.ko" -o -name "libcomposite*.ko" 2>/dev/null | sort'
run 'dmesg | tail -200 2>/dev/null || true'

# compact machine-readable flags
FLAGS="$OUT/flags.txt"
{
  [ -d /sys/class/udc ] && echo "UDC_DIR=YES" || echo "UDC_DIR=NO"
  UDC_COUNT=$(ls /sys/class/udc 2>/dev/null | wc -l | tr -d " ")
  echo "UDC_COUNT=$UDC_COUNT"
  [ -d /sys/kernel/config/usb_gadget ] && echo "USB_GADGET_CONFIGFS=YES" || echo "USB_GADGET_CONFIGFS=NO"
  [ -d /dev/snd ] && echo "DEV_SND=YES" || echo "DEV_SND=NO"
  [ -d /proc/asound ] && echo "PROC_ASOUND=YES" || echo "PROC_ASOUND=NO"
  find /lib/modules /mnt/sdcard -name "u_audio*.ko" -o -name "usb_f_uac*.ko" 2>/dev/null | grep -q . && echo "UAC_MODULES_FOUND=YES" || echo "UAC_MODULES_FOUND=NO"
} > "$FLAGS"

echo "OTG probe complete: $OUT"
echo "Sube la carpeta completa o al menos summary.txt y flags.txt"
