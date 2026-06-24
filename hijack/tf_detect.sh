#!/bin/sh
# TreeFrogUI device detector — one SD image, N devices.
#
# Identifies the handheld from its live device-tree (/proc/device-tree) and
# writes /tmp/tfdevice.env, the single source of truth every frontend reads
# (picoarch parses it directly; falls back to its own DT scan if absent).
#
# Detection (matches sf3000_detect_device() in picoarch/plat_sdl.c):
#   r63311 panel node present      -> R36SX  (640x480 landscape, fb-write)
#   else /panel node present       -> SF3500 (480x854 portrait -> 854x480)
#   else (/hcrtos/lcd, no /panel)  -> SF3000 (480x854 portrait -> 854x480)
#
# All geometry below comes from the stock dtbs (de-engine timing-para / fb1).

DT=/proc/device-tree

if [ -d "$DT/hcrtos/lcd-dsi0-r63311" ]; then
    DEV=R36SX; PW=640; PH=480; ASPN=4;  ASPD=3; ROT=0;  PRESENT=fbwrite
    DRIVER=/mnt/sdcard/cubegm/driver_r36sx.so
elif [ -d "$DT/panel" ]; then
    DEV=SF3500; PW=854; PH=480; ASPN=16; ASPD=9; ROT=90; PRESENT=dispframe
    DRIVER=/mnt/sdcard/cubegm/driver_sf3500.so
else
    DEV=SF3000; PW=854; PH=480; ASPN=16; ASPD=9; ROT=90; PRESENT=dispframe
    DRIVER=/mnt/sdcard/cubegm/driver_sf3000.so
fi

cat > /tmp/tfdevice.env <<EOF
TF_DEVICE=$DEV
TF_PANEL_W=$PW
TF_PANEL_H=$PH
TF_UI_SCALE=150
TF_ASPECT_NUM=$ASPN
TF_ASPECT_DEN=$ASPD
TF_ROTATE=$ROT
TF_PRESENT=$PRESENT
TF_DRIVER=$DRIVER
EOF

# Also log to the standard diagnostics file when present.
[ -f /mnt/sdcard/log.txt ] && echo "tf_detect: $DEV ${PW}x${PH} present=$PRESENT" >> /mnt/sdcard/log.txt
