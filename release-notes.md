Welcome to **TreeFrogUI** (v1.0.0) — one build for **six** handhelds: R36SX (v2.6 & v2.7), SF3000, SF3000 HD, SF3100, SF3500, and GB350

> [!TIP]
> **Consider donating to extend support for these devices:** ☕ **[ko-fi.com/proszty](https://ko-fi.com/proszty)**
> Every supported device was bought out of pocket. Donations go straight toward the next device to port to, and toward keeping these ones updated.

> [!IMPORTANT]
> This is the **1.0 milestone** — the first build to support all six devices from one package. It's been tested mostly by one person, so depending on your exact hardware revision you may still hit bugs, quirks, or compatibility issues.
> 
> Please help improve the project by leaving your feedback, bug reports, and suggestions here:
> 📋 **[Submit Anonymous Feedback (Google Forms)](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v1.0.0

### 🎉 One build, six handhelds

TreeFrogUI is now a **single package that auto-detects your device at boot** and
runs on **R36SX** (v2.6 & v2.7), **SF3000**, **SF3000 HD**, **SF3100**, **SF3500**,
and **GB350**. No more per-device builds — flash the same files everywhere, then
drop in your device's small `install_first/` folder.

- **Unified, safe boot.** Instead of replacing the stock menu, TreeFrogUI now hooks
  the stock launcher's **own autorun**. The protected boot files (`icube`, `rkgame`)
  are **never touched** — which fixes the dreaded "**sdcard is damaged**" error on
  bootloader-protected devices (SF3500-class and R36SX v2.7).
- **Four new devices.** **SF3000 HD** (HDMI-out variant), **SF3100**, and **SF3500**
  all share the same 854×480 panel and driver; **GB350** is a 640×480 4:3 device.
  Plus **R36SX v2.7** support.
- **Per-device install guide.** Pick your device, grab its matching stock backup,
  copy `cubegm/`+`frogui/`+`MAME/`, then your `install_first/<device>/` folder. The
  [install guide](install.md) has a tab per device with the backup links.

### 🕹️ New this release

- **Screenshot hotkey.** **`SELECT + L1`** grabs whatever's on screen — game, menu,
  pause screen — to a `.bmp` in the `screenshots/` folder on your card.
- **Display fixes (854×480 devices).** Correct full-screen geometry, and the
  in-game pause menu no longer duplicates/tiles across the screen.
- **Cleaner input.** Phantom/missed presses from the two-writer input race are
  filtered out, on top of the existing right-stick drift filtering.

---

## High-Level Overview

TreeFrogUI is a heavily modified fork of FrogUI, ported to run within the `picoarch` environment on the MIPS-based Hichip handhelds (R36SX, SF3000, SF3000 HD, SF3100, SF3500, GB350). It provides a clean, minimalistic emulation frontend while supporting a massive range of retro gaming platforms.

### Key Features Included:

- **Minimalist & Fast Interface**: A distraction-free ROM browser with vertical system list navigation and intuitive controls.
- **57 Emulator Cores**: Upgraded from only 14 stock cores, adding compatibility for systems like **PICO-8** (via Fake08/Retro8, supports both `.p8` and `.p8.png` carts), **Quake** (via Tyrquake), **Cave Story** (via NXEngine), **Doom** (via PrBoom), and classic computers like Commodore Amiga and Atari ST.
- **Highly Configurable Cores**: Full support for tweaking libretro core options directly, enabling retro features like system color palette swaps, LCD ghosting emulation, and key mappings.
- **Proper PCSX4ALL Integration**: A configurable PlayStation 1 emulator core supporting `.iso`, `.bin`/`.cue`, `.pbp`, and other standard disc formats. **PS1 needs a real BIOS to save** — drop `scph1001.bin` in `cubegm/cores/.pcsx4all/` (PS1 folder). Without it the emulator runs on HLE, where memory-card saves are broken. See the [install guide](install.md#playstation-1-bios-strongly-recommended).
- **In-Game Save Support**: Battery saves and in-game saves are fully supported across all compatible cores.
- **Auto-Resume on Boot**: Automatically launches you back into your last-played game or the system frontend menu when you boot up your device.
- **Rich Theming Options**: Includes 30 built-in color themes (selectable in-app) and support for custom fonts and per-system/per-folder background images (`PNG`, `JPG`, `BMP`).
- **Flexible Aspect Ratio Scaling**: Switch between Zoom, Aspect Ratio, and Integer Scaling display modes on the fly.
- **Useful In-Game Shortcuts**: Use **`SELECT + START`** to open the in-game picoarch menu (all cores except PCSX4ALL), **`SELECT + L`** to open the emulator menu (PCSX4ALL only) or load a state (slot 0, default), **`SELECT + R`** to save a state (slot 0, default), **`SELECT + Y`** to cycle fast-forward (off → 2× → 3× → off, audio mutes), hold **`SELECT + B`** to rewind, and **`SELECT + L1`** to grab a screenshot (BMP saved to the `screenshots/` folder on your card).
- **Custom Boot Logo**: Includes a custom-fit, top-down `xgame-logo.bmp` splash screen to replace the stock boot logo on your device.

---

## Installation Summary

For step-by-step setup instructions, please refer to the [Installation Guide](install.md).

*Note: You must have the original **stock OS** for your device installed on your SD card as a prerequisite. Clean backups: [SF3000](https://github.com/Q-ta-s/q-ta-s.github.io/releases/download/sf3000/SF3000_sdcard.7z) · [R36SX v2.6](https://drive.google.com/file/d/1xTCNNRKfQmFJr2Zkd1oCBRChuWiidIBD) · [R36SX v2.7](https://drive.google.com/file/d/12G3CQAWkaRMWbrY_YmGH8nstGbs1hB-O) · [SF3000 HD / SF3100 / SF3500 / GB350](https://github.com/Q-ta-s/q-ta-s.github.io/releases). The [install guide](install.md) maps each device to its backup + `install_first/` folder.*

---

## Troubleshooting & Feedback

- **Black Screen / Only Battery Icon Visible:** If nothing loads or only the battery icon is visible after the boot logo, set up your SD card with the clean **[Stock OS Backup](https://github.com/Q-ta-s/q-ta-s.github.io/releases/download/sf3000/SF3000_sdcard.7z)** first, then copy the TreeFrogUI files over.
- **Submit Feedback Anonymously**: Help improve the project by submitting bugs, performance issues, or compatibility reports on the [Feedback Form](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header).
- **GitHub Issues**: You can also open an issue on the [GitHub repository](https://github.com/tzubertowski/treefrog-ui/issues).

---

## Want TreeFrogUI on another device?

SF3000 V3 (bootloader protection), the **SF3000 Pro** (different firmware — no
rkgame stack, so the autorun hook doesn't apply), other HDMI-out clones, and more
are all on the wishlist.

The catch: porting needs the actual hardware in hand. Bootloaders differ, input
and display wiring differ, the protected variants need live debugging. No way to
do it blind.

Every device supported so far was bought out of my own pocket, and there are far
more clones than I can keep buying.

If you want to see a port happen, chip in: ☕ **[ko-fi.com/proszty](https://ko-fi.com/proszty)**. Donations go straight toward the next device to port to.
