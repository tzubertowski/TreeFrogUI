Welcome to **TreeFrogUI** (v0.1.7) for the SF3000 and R36SX handheld consoles

> [!WARNING]
> This release supports the initial **SF3000** hardware iterations and the **R36SX** (firmware **v2.6** and **v2.7**). One build runs on both — the device is auto-detected at boot.

> [!IMPORTANT]
> This is an **early release** of the project and should be considered a beta/preview version. Since I was the only person testing it during development, it is highly likely that you will encounter bugs, quirks, or compatibility issues. 
> 
> Please help improve the project by leaving your feedback, bug reports, and suggestions here:
> 📋 **[Submit Anonymous Feedback (Google Forms)](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v0.1.7

- **No accidental sleep (R36SX).** Short power press no longer sleeps to a black screen. Long press still powers off.
- **PICO-8 way faster.** Rebuilt on the upstream emulator and optimised for this CPU. New **Audio off** and **Frame Skip** options. Many carts now run full speed. Folder renamed **`pico8`** (old `fake08` still works).
- **Arduboy now uses Ardens** (much faster core). The old `arduous` core is still there: put games in an `arduous` folder.
- **PS1 (PCSX4ALL).** L2/R2 buttons now work. New **Pixel Skip** + **Interlace** speed toggles in the menu (`SELECT + L`) for heavy games like Tekken 3. Real BIOS recommended (`scph1001.bin` in `cubegm/cores/.pcsx4all/`).
- **All cores faster.** Retuned for the device's 74Kc CPU (DSP2 + `-O3`). Default scaling is now **Aspect**.
- **Menu polish.** Smooth iPhone-style background fades (selection stays instant). New **Hide Empty Folders** setting. Right-stick drift no longer triggers phantom presses while navigating.
---

## High-Level Overview

TreeFrogUI is a heavily modified fork of FrogUI, ported to run within the `picoarch` environment on the MIPS-based SF3000 handheld. It provides a clean, minimalistic emulation frontend while supporting a massive range of retro gaming platforms.

### Key Features Included:

- **Minimalist & Fast Interface**: A distraction-free ROM browser with vertical system list navigation and intuitive controls.
- **57 Emulator Cores**: Upgraded from only 14 stock cores, adding compatibility for systems like **PICO-8** (via Fake08/Retro8 — supports both `.p8` and `.p8.png` carts), **Quake** (via Tyrquake), **Cave Story** (via NXEngine), **Doom** (via PrBoom), and classic computers like Commodore Amiga and Atari ST.
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
