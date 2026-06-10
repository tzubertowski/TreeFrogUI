> [!CAUTION]
> **R36SX v2.7 owners — read this first.** There are **many different v2.7 hardware revisions**, and I do not have access to all of them. Some run TreeFrogUI perfectly (like mine); others get stuck on a **"damaged SD card"** screen. **Your particular v2.7 may or may not work — I cannot guarantee it.** I currently don't own one of the newer v2.7 units to test against; if I manage to find one discounted, I'll get it and try to add support.

Welcome to **TreeFrogUI** (v0.1.6) for the SF3000 and R36SX handheld consoles

> [!WARNING]
> This release supports the initial **SF3000** hardware iterations and the **R36SX** (firmware **v2.6** and **v2.7**). One build runs on both — the device is auto-detected at boot.

> [!IMPORTANT]
> This is an **early release** of the project and should be considered a beta/preview version. Since I was the only person testing it during development, it is highly likely that you will encounter bugs, quirks, or compatibility issues. 
> 
> Please help improve the project by leaving your feedback, bug reports, and suggestions here:
> 📋 **[Submit Anonymous Feedback (Google Forms)](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v0.1.6

- **Redesigned in-game pause menu (MinUI-style)**: the `SELECT + START` menu now uses the same TTF font as FrogUI, rounded-pill selection, and the game title + a live screenshot thumbnail. Options pages share the same look.
- **Per-savestate screenshots**: each save slot stores and shows a thumbnail of the exact moment it was saved. Save/Load now lists **8 slots**; the 10th slot is reserved for auto-resume.
- **Per-game / per-folder core override**: press **`SELECT`** on a game or system folder in FrogUI to pick which emulator core runs it (default = the folder's core). Choices persist.
- **Game search**: press **`X`** in FrogUI to search by name with an on-screen keyboard — scoped to the current folder or across your whole library.
- **Animated backgrounds**: the system/folder banner now crossfades when you move between systems. Toggle all UI animations in **Settings → Animations**.
- **Two GBA cores**: the `gba` folder runs upstream **gpSP**; put games in a `gbac` folder to use the multi-core gpSP build instead. FrogUI tells the folders apart automatically.
- **Commodore 64 (Frodo)**: the `frodo` core now builds and runs — put disks in a `c64f` (or `c64fc`) folder. The inserted disk auto-loads on boot (`LOAD"*",8,1:RUN`).
- **PlayStation 1 memory cards fixed**: PCSX4ALL now creates/loads memory cards correctly and saves persist. For best results (graphics, performance, and reliable card saves) drop a real BIOS at `cubegm/cores/.pcsx4all/scph1001.bin` — see the install guide.
- **Stability & polish**: fixed Sega/Genesis black-screen crash, oversized in-game FPS overlay, random "back" presses and disappearing menu glyphs while scrolling, and inconsistent fast-forward. Faster Arduboy emulation. Menus now filter accidental right-stick drift.
---

> [!NOTE]
> **The right analog stick cannot work as a true analog stick on the R36SX — this is a hardware limitation, not a missing feature.** On this device the right stick is wired straight onto the **same digital lines as the X/A/B/Y face buttons**: pushing the stick is electrically identical to pressing those buttons. The OS exposes **no separate analog signal** for it anywhere — there is no joystick/event device, the input daemon reports only on/off button bits, and the analog-to-digital block the stock firmware uses is left unpowered by the kernel and locks up the device if touched from software. I reverse-engineered every available path to confirm this. As a result, in TreeFrogUI the right stick simply **mirrors the face buttons** and **cannot be remapped to analog axes**. (The menus do filter out accidental stick *drift* so it won't fire buttons on its own.)
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
