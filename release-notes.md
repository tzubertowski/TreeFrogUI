# TreeFrogUI v0.1.1 - Release Notes

Welcome to **TreeFrogUI** (v0.1.1) for the SF3000 handheld console!

![UI Preview on SF3000 Console](console.jpg)

> [!IMPORTANT]
> This is an **early release** of the project and should be considered a beta/preview version. Since I was the only person testing it during development, it is highly likely that you will encounter bugs, quirks, or compatibility issues. 
> 
> Please help improve the project by leaving your feedback, bug reports, and suggestions here:
> 📋 **[Submit Anonymous Feedback (Google Forms)](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v0.1.1

- **PICO-8 (fake08) working**: fake08 core now builds and runs; launches both `.p8` (text source) and `.p8.png` (cart image) files from `roms/fake08/`.
- **Smoother menu fonts**: glyph rendering now alpha-blends edges instead of hard 1-bit thresholding, removing the jagged menu text.
- **PCSX4ALL BIOS path documented**: place `scph1001.bin` in `/mnt/sdcard/cubegm/cores/.pcsx4all/` (missing BIOS falls back to HLE, lower compatibility).

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
- **Useful In-Game Shortcuts**: Use **`SELECT + START`** to open the in-game picoarch menu (all cores except PCSX4ALL), **`SELECT + L`** to open the emulator menu (PCSX4ALL only) or load a state (slot 0, default), and **`SELECT + R`** to save a state (slot 0, default).
- **Custom Boot Logo**: Includes a custom-fit, top-down `xgame-logo.bmp` splash screen to replace the stock boot logo on your device.

---

## Installation Summary

For step-by-step setup instructions, please refer to the [Installation Guide](install.md).

*Note: You must have the original **stock OS** installed on your SD card as a prerequisite (clean backup available [here](https://github.com/Q-ta-s/q-ta-s.github.io/releases/download/sf3000/SF3000_sdcard.7z)).*

1. Back up your current SD card (especially before installing TreeFrogUI or restoring any backups, save a copy of at least `cubegm/icube` and `cubegm/icube_start.sh`).
2. Download the release archive.
3. Copy over the extracted `sdcard/` contents directly to the **ROOT** of your SD card (replacing files when prompted).
4. Insert the card into your SF3000 and boot up!
5. Put game ROMs in the corresponding subfolders inside the `roms/` directory on the root of your SD card (e.g., `roms/GBA/`, `roms/FC/`).

---

## Troubleshooting & Feedback

- **Black Screen / Only Battery Icon Visible:** If nothing loads or only the battery icon is visible after the boot logo, set up your SD card with the clean **[Stock OS Backup](https://github.com/Q-ta-s/q-ta-s.github.io/releases/download/sf3000/SF3000_sdcard.7z)** first, then copy the TreeFrogUI files over.
- **Submit Feedback Anonymously**: Help improve the project by submitting bugs, performance issues, or compatibility reports on the [Feedback Form](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header).
- **GitHub Issues**: You can also open an issue on the [GitHub repository](https://github.com/tzubertowski/treefrog-ui/issues).
