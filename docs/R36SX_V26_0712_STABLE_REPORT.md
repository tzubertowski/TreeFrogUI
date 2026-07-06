# R36SX V2.6 (0712) stable test report

## Device / firmware

- Device: R36SX
- Firmware / stock OS: R36SX V2.6 (0712) Minimal Backup
- TreeFrogUI baseline: v1.0.2 / main test package

## Summary

On R36SX V2.6 (0712), the stock `driver_r36sx.so` hardware display path can enter a black-screen flashing loop during TreeFrogUI startup. The frontend itself initializes successfully; the failure happens when `picoarch` enters the hardware display path and calls the proprietary display frame path.

A software-framebuffer fallback avoids the black-screen loop and allows TreeFrogUI to display. This confirms that the R36SX v2.6 issue is in the hardware display path, not in `frogui_libretro.so` initialization or the SD card layout.

## Observed failure pattern

Typical failing sequence from logs:

```text
DBG hwdisp: loaded /mnt/sdcard/cubegm/driver_r36sx.so
hwdisp: HW path active
DBG present_direct#1: pre disp_frame 640x480 scale=1
picoarch: pthread_mutex_lock.c:81: __pthread_mutex_lock: Assertion `mutex->__data.__owner == 0' failed.
Aborted
frogui exited rc=134
```

## Verified workaround

Disabling `cubegm/driver_r36sx.so` prevents the faulty hardware display path from loading. TreeFrogUI then falls back to framebuffer rendering and avoids the black-screen loop.

This is a workaround, not the ideal final fix. The proper source-level fix should be in `picoarch`: R36SX v2.6 should have a guarded software-framebuffer path that skips `hwdisp/disp_frame` and handles the required orientation/scaling explicitly.

## Expected source-level fix

Recommended implementation direction:

1. Detect R36SX v2.6 / affected framebuffer configuration.
2. If the affected path is detected, skip `hwdisp_init()` / `disp_frame()` for frontend rendering.
3. Render via framebuffer software path.
4. Apply the correct rotation and scaling for the physical panel.
5. Keep the existing hardware path available for unaffected R36SX revisions.

## Test notes

- `frogui_libretro.so` initialization completed successfully before the display crash.
- The crash repeats on each `zhijack.sh` relaunch, causing black flashing.
- GB350-style hardware-driver substitution was not a reliable fix; it can re-enter the same hardware-display crash path.
- Software framebuffer is the stable baseline for affected R36SX V2.6 (0712) units.

## Caution

Do not ship this workaround as a silent driver deletion unless clearly documented. Users need a reversible fix and a path back to the original driver if future `picoarch` builds handle R36SX hardware display correctly.
