# PlayStation 1

← [back to README](../../README.md)

PS1 has **two cores**. `PS`/`ps1`/`psx` folders prefer the standalone **PCSX4ALL** if its binary is present, falling back to the libretro **pcsx_rearmed** core otherwise; the `ps1r` folder always uses pcsx_rearmed directly (lightrec JIT).

**Use a real BIOS.** Without one, both cores fall back to HLE, which causes **graphical glitches, worse performance, and broken/hanging memory-card saves** (e.g. Harvest Moon). Each core has its own BIOS location - without a real BIOS things degrade, they don't refuse to run, so it's easy to miss. Drop a real `scph1001.bin` in **both** locations so either core works (filenames are case-insensitive):

| Core | ROM folder | BIOS path |
|------|-----------|-----------|
| **PCSX4ALL** | `PS` | `/mnt/sdcard/cubegm/cores/.pcsx4all/scph1001.bin` |
| **pcsx_rearmed** (lightrec) | `ps1r` | `/mnt/sdcard/cubegm/bios/scph1001.bin` |

(pcsx_rearmed also accepts `scph5501.bin` / `scph7001.bin` in `cubegm/bios/`.)

**Speed toggles:** for heavy 3D games (e.g. Tekken 3) that don't run full speed, open the PCSX4ALL menu with **`SELECT + L`** and turn on **Pixel Skip** and/or **Interlace** - they trade a little image quality for a real speed boost.

PCSX4ALL is a standalone emulator with its own menu and hotkeys, separate from the shared in-game shortcuts.
