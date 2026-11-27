# PC Engine / TurboGrafx-16

← [back to README](../../README.md)

`pce` uses the **Beetle PCE Fast** (`mednafen_pce_fast_libretro.so`) libretro core.

## TurboGrafx-CD / PC Engine CD

1. Copy your Super CD-ROM² System Card v3 BIOS to **`cubegm/bios/syscard3.pce`** on the SD card.
2. Put each game's `.cue` and all the disc tracks it references in the same folder under **`roms/pce/`**, for example `roms/pce/Lords of Thunder/`. Match the filenames and capitalization in the cue sheet.
3. On the handheld, open **Games → Explore Content → PC Engine** and launch the **`.cue`** file.

BIN/CUE playback was reported working on R36SX v3.0 with *Lords of Thunder*, *Dungeon Explorer II*, and *Ys Book I & II*. [Device report #105](https://github.com/tzubertowski/TreeFrogUI/issues/105) · [Beetle PCE Fast documentation](https://docs.libretro.com/library/beetle_pce_fast/#bios)

## Troubleshooting

**Crash or reset when returning from the in-game menu, on some devices (seen on
SF3000 HD)?** Turn on **Disable Soft Reset** in the core's options
(`SELECT + START` → Core Options → `pce_fast_disable_softreset`). The stock PC
Engine soft-reset combo (RUN+SELECT) can fire spuriously when control returns
to the core after the menu closes, resetting or crashing it. Disabling soft
reset removes that combo entirely and fixes it. Not all devices are affected;
if you don't see this, no action needed.
