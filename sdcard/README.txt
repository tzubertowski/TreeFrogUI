TreeFrogUI SD card layout
=========================

PREREQUISITES: Flash SF3000 stock firmware first (provides cubegm/usr/lib with
libSDL, audio driver, cubevol, etc.). Then rsync THIS folder on top.

  rsync -av sdcard/ /run/media/USER/SDCARD/

  sdcard/
  ├── cubegm/
  │   ├── icube          ← boot script (SF3000 OS calls this on startup)
  │   ├── picoarch       ← libretro frontend binary (custom build)
  │   ├── cores/         ← emulator cores (.so files, 57 total)
  │   │   └── frogui_libretro.so  ← the UI core
  │   └── lib/           ← runtime libs (libpng12, libstdc++, gba_bios.bin...)
  ├── frogui/
  │   ├── fonts/         ← GamePocket + Monogram TTF fonts
  │   └── settings.txt   ← theme/font preferences
  ├── picoarch.cfg       ← picoarch settings (scale_size=full etc.)
  ├── saves/             ← save files
  ├── states/            ← save states
  └── README.txt         ← this file

ROMs: place in /roms/<system>/ on SD root. Supported folder names:

  roms/nes/    NES         roms/gb/     Game Boy
  roms/snes/   SNES        roms/gbc/    GBC
  roms/gba/    GBA         roms/md/     Mega Drive
  roms/pce/    PC Engine   roms/sms/    Master System
  roms/gg/     Game Gear   roms/ngpc/   Neo Geo Pocket

Full mapping: frogui_libretro.c console_mappings[] and ext_mappings[]
Subfolders work too — core selected by file extension as fallback.

BIOS files (place in cubegm/lib/):
  gba_bios.bin   GBA (required for gpsp, already included)

Boot: SF3000 OS calls cubegm/icube on startup via icube_start.sh.
icube launches picoarch+frogui, then exec()s into game cores on selection.
