TreeFrogUI SD card layout
=========================

Copy the contents of this folder to the ROOT of your SD card.

  sdcard/
  ├── cubegm/
  │   ├── icube          ← boot script (SF3000 OS calls this on startup)
  │   ├── picoarch       ← libretro frontend binary
  │   ├── cores/         ← emulator cores (.so files)
  │   │   ├── frogui_libretro.so
  │   │   └── ... (57 cores)
  │   └── lib/           ← shared libraries required by picoarch
  ├── frogui/
  │   └── settings.txt   ← theme/font settings (edit to change appearance)
  ├── saves/             ← save files go here
  ├── states/            ← save states go here
  └── README.txt         ← this file

After copying, add your ROMs in folders matching the system names:
  FC/    NES roms
  SFC/   SNES roms
  GBA/   GBA roms (needs gba_bios.bin in cubegm/lib/)
  MD/    Mega Drive/Genesis roms
  etc.

Full folder→system mapping: https://github.com/tzubertowski/treefrog-ui/blob/master/cores.md

BIOS files (place in cubegm/lib/):
  gba_bios.bin   GBA (required for gpsp)
  kick.rom       Amiga (required for UAE)

Boot: the SF3000 OS must call icube on startup.
Check your device's /etc/init.d/ or equivalent boot config.
