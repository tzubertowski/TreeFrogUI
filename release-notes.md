Welcome to **TreeFrogUI** (v0.1.8) for the SF3000 and R36SX handheld consoles

> [!IMPORTANT]
> This is an **early release** of the project and should be considered a beta/preview version. Since I was the only person testing it during development, it is highly likely that you will encounter bugs, quirks, or compatibility issues. 
> 
> Please help improve the project by leaving your feedback, bug reports, and suggestions here:
> 📋 **[Submit Anonymous Feedback (Google Forms)](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v0.1.8

### 🕹️ The big ones: MS-DOS and Neo Geo

Your handheld now runs **MS-DOS PC games** and **Neo Geo arcade** games.

- **MS-DOS PC (pico286).** Play classics like Prince of Persia, Oregon Trail, Doom-era DOS games, and more. Boots FreeDOS automatically, so most games just run. Built-in **on-screen keyboard**, **disk swap**, **mouse mode**, and **joystick** support. Drop games in a `pico286` folder.
- **Neo Geo arcade.** Metal Slug, KOF, and the rest, via FB Alpha 2012. Put games in a `neogeo` folder and the **`neogeo.zip` BIOS in `roms/neogeo/`** too (a copy in `cubegm/bios/` does no harm). Romsets must match FB Alpha 2012 (0.2.97.30). Heavy games like Metal Slug may need **Frameskip 1** for full speed.

---

**More new systems**

- **Capcom arcade (CPS-1, CPS-2).** Street Fighter II, Marvel vs Capcom, and more. Use `cps1` / `cps2` folders. Romsets must match FB Alpha 2012 (0.2.97.30).
- **TIC-80 fantasy console.** Run `.tic` carts from a `tic80` folder.
- **Sega CD, Sega 32X, Famicom Disk System.** New `segacd`, `32x`, `fds` folders. Sega CD needs its BIOS (`bios_CD_U/E/J.bin` in `cubegm/bios`), FDS needs `disksys.rom`.

**Game library**

- **Game Switcher.** New recent-games view: full-screen box art (or the game's last screenshot) plus how long you have played it. **On by default.** **Left/Right** flips games, **A** jumps back in. Toggle in Settings.
- **Per-game screenshots.** Open the in-game menu once (`SELECT + START`) and TreeFrogUI snaps the current frame as that game's art. No box art needed.
- **Play-time tracking.** Records time played per game, shown in the Game Switcher.
- **Start in Recents.** Optional: boot straight into your recent games. Turn on in Settings.

**Emulation quality of life**

- **OnionOS-style hotkeys.** `SELECT + L2` load state, `SELECT + R2` save state, `SELECT + R1` fast-forward, `SELECT + START` menu.
- **Per-core Fast Forward and Rewind.** Enable either one per system in the in-game menu; settings stick per core.
- **Save states no longer freeze.** Fixed a hang when saving on some cores.
- **No more random inputs.** Right analog-stick drift no longer fires phantom button presses while you navigate or play.
- **PS1 buttons fixed.** Face buttons now map correctly (Cross/Circle/Square/Triangle).
---

## High-Level Overview

TreeFrogUI is a heavily modified fork of FrogUI, ported to run within the `picoarch` environment on the MIPS-based SF3000 handheld. It provides a clean, minimalistic emulation frontend while supporting a massive range of retro gaming platforms.

### Key Features Included:

- **Minimalist & Fast Interface**: A distraction-free ROM browser with vertical system list navigation and intuitive controls.
- **57 Emulator Cores**: Upgraded from only 14 stock cores, adding compatibility for systems like **PICO-8** (via Fake08/Retro8, supports both `.p8` and `.p8.png` carts), **Quake** (via Tyrquake), **Cave Story** (via NXEngine), **Doom** (via PrBoom), and classic computers like Commodore Amiga and Atari ST.
- **Highly Configurable Cores**: Full support for tweaking libretro core options directly, enabling retro features like system color palette swaps, LCD ghosting emulation, and key mappings.
- **Proper PCSX4ALL Integration**: A configurable PlayStation 1 emulator core supporting `.iso`, `.bin`/`.cue`, `.pbp`, and other standard disc formats.
- **In-Game Save Support**: Battery saves and in-game saves are fully supported across all compatible cores.
- **Auto-Resume on Boot**: Automatically launches you back into your last-played game or the system frontend menu when you boot up your device.
- **Rich Theming Options**: Includes 30 built-in color themes (selectable in-app) and support for custom fonts and per-system/per-folder background images (`PNG`, `JPG`, `BMP`).
- **Flexible Aspect Ratio Scaling**: Switch between Zoom, Aspect Ratio, and Integer Scaling display modes on the fly.
- **Useful In-Game Shortcuts**: Use **`SELECT + START`** to open the in-game picoarch menu (all cores except PCSX4ALL), **`SELECT + L`** to open the emulator menu (PCSX4ALL only) or load a state (slot 0, default), **`SELECT + R`** to save a state (slot 0, default), **`SELECT + Y`** to cycle fast-forward (off → 2× → 3× → off, audio mutes), and hold **`SELECT + B`** to rewind.
- **Custom Boot Logo**: Includes a custom-fit, top-down `xgame-logo.bmp` splash screen to replace the stock boot logo on your device.

---

## Installation Summary

For step-by-step setup instructions, please refer to the [Installation Guide](install.md).

*Note: You must have the original **stock OS** installed on your SD card as a prerequisite. Clean backups: [SF3000](https://github.com/Q-ta-s/q-ta-s.github.io/releases/download/sf3000/SF3000_sdcard.7z) · [R36SX v2.6](https://drive.google.com/file/d/1xTCNNRKfQmFJr2Zkd1oCBRChuWiidIBD) · [R36SX v2.7](https://drive.google.com/file/d/12G3CQAWkaRMWbrY_YmGH8nstGbs1hB-O).*

---

## Troubleshooting & Feedback

- **Black Screen / Only Battery Icon Visible:** If nothing loads or only the battery icon is visible after the boot logo, set up your SD card with the clean **[Stock OS Backup](https://github.com/Q-ta-s/q-ta-s.github.io/releases/download/sf3000/SF3000_sdcard.7z)** first, then copy the TreeFrogUI files over.
- **Submit Feedback Anonymously**: Help improve the project by submitting bugs, performance issues, or compatibility reports on the [Feedback Form](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header).
- **GitHub Issues**: You can also open an issue on the [GitHub repository](https://github.com/tzubertowski/treefrog-ui/issues).

---

## Want TreeFrogUI on another device?

R36SX v2.7 (bootloader protection), SF3000 V3 (bootloader protection), SF3500,
SF3100, GB350, HDMI-out clones, and more are all on the wishlist.

The catch: porting needs the actual hardware in hand. Bootloaders differ, input
and display wiring differ, the protected variants need live debugging. No way to
do it blind.

Every device supported so far was bought out of my own pocket, and there are far
more clones than I can keep buying.

If you want to see a port happen, chip in: ☕ **[ko-fi.com/proszty](https://ko-fi.com/proszty)**. Donations go straight toward the next device to port to.
