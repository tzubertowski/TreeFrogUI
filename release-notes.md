> [!TIP]
> **Consider donating to keep this going:** ☕ **[ko-fi.com/proszty](https://ko-fi.com/proszty)**
> Most supported devices were bought out of pocket (the SF3500 was funded by the community). These days tips go toward ongoing maintenance and buying new clones to port to.

> [!IMPORTANT]
> v1.0.8a fixes the **SF3500 pause-menu text glitch**, makes **brightness apply in games** (and stop flashing on boot), fixes **PlayStation games launching the wrong emulator from Favourites**, fixes the **PlayStation resolution-change freeze** properly, and adds support for **newer SF3500 hardware revisions**.
> 
> 📋 **[Submit Anonymous Feedback (Google Forms)](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v1.0.8a

- **🔆 Brightness now applies in games.** Your brightness setting only affected the frontend before — games ran at default brightness, and the frontend flashed to default for a moment on boot and when returning from a game. Brightness is now applied in games too and synced so there's no flash. (SF3500-class.)
- **🎮 PlayStation launches the right emulator from Favourites/Recents.** A PS1 game added to Favourites (or in Recents) booted the wrong core instead of the standalone PCSX4ALL it uses from the folder. All launch paths now agree, so Favourites/Recents launch PS1 exactly like browsing does.
- **🩹 PlayStation resolution-change freeze fixed (properly).** Games that switch internal resolution mid-play (menus, FMVs — Colin McRae Rally, etc.) could freeze the display while the game kept running. The display driver was reading each frame from a buffer the emulator was still writing; frames are now staged so the driver always reads a stable copy. No performance cost.
- **🩹 SF3500 pause-menu text fixed.** In the in-game menu, letters could randomly jump half a row out of place (the "T" of EXIT sitting above its line, etc.) and heal themselves as you navigated. Each character is now rasterized once and cached instead of every frame, so the text stays put. Menus are a touch faster too. No visible change on other devices.
- **📦 Newer SF3500 revisions supported.** Some later SF3500 units won't boot the standard stock backup. A new **[SF3500 v1.1 stock backup](https://github.com/Q-ta-s/q-ta-s.github.io/releases/tag/sf3500_1)** boots on those; restore it instead of the standard one (same `install_first/sf3500/` folder, everything else identical). See the [install guide](install.md).

*Also in the v1.0.7 line: per-game scaling-filter save, SF3500 miniature-picture fix, Disable Sleep on by default, and Auto-Resume split into Quick Resume + Auto-Save/Auto-Load.*

**Updating:** copy `cubegm/` and `frogui/` over your card, then copy your device's `install_first/<device>/` folder again. ROMs, saves, and settings are untouched.

---

## High-Level Overview

TreeFrogUI is a heavily modified fork of FrogUI, ported to run within the `picoarch` environment on the MIPS-based Hichip handhelds (R36SX, SF3000, SF3000 HD, SF3100, SF3500, GB350). It provides a clean, minimalistic emulation frontend while supporting a massive range of retro gaming platforms.

### Key Features Included:

- **Minimalist & Fast Interface**: A distraction-free ROM browser with vertical system list navigation and intuitive controls.
- **70 Emulator Cores**: Upgraded from only 14 stock cores, adding compatibility for systems like **PlayStation 1**, **Neo Geo / CPS-1 / CPS-2 arcade**, **MS-DOS PC** (via pico286), **PICO-8** (via Fake08/Retro8), **Quake** (via Tyrquake), **Cave Story** (via NXEngine), **Doom** (via PrBoom), and classic computers like Commodore Amiga and Atari ST. See [`cores.md`](cores.md) for the full folder-to-system list.
- **Highly Configurable Cores**: Full support for tweaking libretro core options directly, enabling retro features like system color palette swaps, LCD ghosting emulation, and key mappings.
- **Proper PCSX4ALL Integration**: A configurable PlayStation 1 emulator core supporting `.iso`, `.bin`/`.cue`, `.pbp`, and other standard disc formats. **PS1 needs a real BIOS to save**: drop `scph1001.bin` in `cubegm/cores/.pcsx4all/` (PS1 folder). Without it the emulator runs on HLE, where memory-card saves are broken. See the [install guide](install.md#playstation-1-bios-strongly-recommended).
- **In-Game Save Support**: Battery saves and in-game saves are fully supported across all compatible cores.
- **Quick Resume**: Automatically launches you back into your last-played game when you boot up your device, skipping the frontend menu.
- **Auto-Save/Auto-Load**: Auto-saves state on pause/quit and auto-loads it on any game launch (Quick Resume boot or a manual pick from the frontend).
- **Rich Theming Options**: Includes 30 built-in color themes (selectable in-app) and support for custom fonts and per-system/per-folder background images (`PNG`, `JPG`, `BMP`).
- **Flexible Aspect Ratio Scaling**: Switch between Zoom, Aspect Ratio, and Integer Scaling display modes on the fly.
- **Useful In-Game Shortcuts** (`SELECT` is the function key): **`SELECT + START`** opens the in-game menu (PCSX4ALL opens its own), **`SELECT + R2`** saves a state, **`SELECT + L2`** loads a state, **`SELECT + R1`** cycles fast-forward, hold **`SELECT + B`** to rewind, and **`SELECT + L1`** takes a screenshot (saved to the `screenshots/` folder).
- **Custom Boot Logo**: Includes a custom-fit, top-down `xgame-logo.bmp` splash screen to replace the stock boot logo on your device.

---

## Installation Summary

For step-by-step setup instructions, please refer to the [Installation Guide](install.md).

*Note: You must have the original **stock OS** for your device installed on your SD card as a prerequisite. Clean backups: [SF3000](https://github.com/Q-ta-s/q-ta-s.github.io/releases/download/sf3000/SF3000_sdcard.7z) · [R36SX v2.6](https://drive.google.com/file/d/1xTCNNRKfQmFJr2Zkd1oCBRChuWiidIBD) · [R36SX v2.7](https://drive.google.com/file/d/12G3CQAWkaRMWbrY_YmGH8nstGbs1hB-O) · [SF3000 HD / SF3100 / SF3500 / GB350](https://github.com/Q-ta-s/q-ta-s.github.io/releases). The [install guide](install.md) maps each device to its backup + `install_first/` folder.*

---

## Troubleshooting & Feedback

- **Read the [install guide](install.md) first.** Most problems come from a wrong or skipped step. It has a tab per device with the exact stock backup and the `install_first/<device>/` folder to copy. Follow your device's section.
- **Black screen / only battery icon after the boot logo:** you didn't start from a clean **stock OS** card for your device, or you copied the wrong device's `install_first/` folder. Restore the stock backup ([links in the install guide](install.md)), then copy the TreeFrogUI files and your device's `install_first/` folder again.
- **"sdcard is damaged":** make sure you copied **your** device's `install_first/` folder and did not modify the stock `icube` / `rkgame`. The unified boot leaves those untouched precisely so this error doesn't happen.
- **PS1 won't save:** you're running on the HLE BIOS. Drop a real `scph1001.bin` in the BIOS folder (see the [PS1 BIOS section](install.md#playstation-1-bios-strongly-recommended)).
- **Sleep mode / power button standby (R36SX, SF3500-class):** not supported by TreeFrogUI, can hang the display on wake. Disable Sleep is on by default to prevent this. Use **Quick Resume** (+ **Auto-Save/Auto-Load**) instead - it covers the same use case as real hibernation.
- **Give feedback / report a bug:** please do, it is the fastest way to get your device's quirks fixed.
  - 📋 [Anonymous Feedback Form](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)
  - 🐛 [GitHub Issues](https://github.com/tzubertowski/treefrog-ui/issues)

---

## Want TreeFrogUI on another device?

Six devices are supported today (R36SX v2.6/v2.7, SF3000, SF3000 HD, SF3100, SF3500, GB350). The **SF3000 Pro** is a different beast: it runs entirely different firmware with no rkgame stack, so the boot hook doesn't apply and it needs its own port. Other Hichip-based clones and HDMI-out variants are candidates too.

The catch: porting needs the actual hardware in hand. Bootloaders, input wiring, and displays all differ between clones, and the protected variants need live debugging. There's no way to do it blind.

Most devices supported so far were bought out of my own pocket (the SF3500 was funded by the community), and there are far more clones out there than I can keep buying. If you want to see a port happen, chip in: ☕ **[ko-fi.com/proszty](https://ko-fi.com/proszty)**. Tips go toward ongoing maintenance and buying the next clone to port to.
