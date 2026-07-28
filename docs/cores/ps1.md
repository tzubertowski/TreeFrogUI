# PlayStation 1

← [back to README](../../README.md)

PS1 has **two cores**. `PS`/`ps1`/`psx` folders prefer the standalone **PCSX4ALL** if its binary is present, falling back to the libretro **pcsx_rearmed** core otherwise; the `ps1r` folder always uses pcsx_rearmed directly (lightrec JIT).

**Use a real BIOS.** Without one, both cores fall back to HLE, which causes **graphical glitches, worse performance, and broken/hanging memory-card saves** (e.g. Harvest Moon). Drop **any** PS1 BIOS in **`cubegm/bios/`** and both cores find it:

| Core | ROM folder | BIOS |
|------|-----------|------|
| **PCSX4ALL** | `PS` | auto-detects any `scph*.bin` in `cubegm/bios/` (legacy `cubegm/cores/.pcsx4all/` still works) |
| **pcsx_rearmed** (lightrec) | `ps1r` | any `scph*.bin` in `cubegm/bios/` |

Filenames are case-insensitive; `scph1001.bin`, `scph5501.bin`, `scph7001.bin`, etc. all work. One file in `cubegm/bios/` covers both cores.

> [!NOTE]
> **PCSX4ALL now uses the BIOS automatically.** If a valid BIOS is present it
> switches HLE off on its own at launch - no menu steps. The old "turn HLE off
> in Core Settings" dance is gone; it was only needed because the file wasn't
> being found. If you ever want to force HLE, delete the BIOS from `cubegm/bios/`.

**Speed toggles:** for heavy 3D games (e.g. Tekken 3) that don't run full speed, open the PCSX4ALL menu with **`SELECT + L`** and turn on **Pixel Skip** and/or **Interlace** - they trade a little image quality for a real speed boost.

### Hi-Res Fix (for games that freeze or go black)

A few games switch into a **hi-resolution video mode** (480 lines) that the
display driver can't present directly - the screen freezes or goes black while
the game keeps running underneath. Known cases: **Colin McRae Rally 2.0**,
**Worms Armageddon**.

If a game does that, open the PCSX4ALL menu (**`SELECT + L`**) and turn **Hi-Res
Fix** to **On**. It scales those hi-res frames down to something the driver can
show, at a small per-frame CPU cost.

It's **Off by default** because most games never use hi-res mode and the fix
isn't free - leaving it off keeps every normal game running at full speed. Only
flip it on for the specific games that need it (the setting is saved per the
PCSX4ALL config, so it persists once set).

PCSX4ALL is a standalone emulator with its own menu and hotkeys, separate from the shared in-game shortcuts.
