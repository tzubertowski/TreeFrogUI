Welcome to **TreeFrogUI** (v1.0.4): one build for **seven** handhelds: R36SX (v2.6 & v2.7), R36 HD, SF3000, SF3000 HD, SF3100, SF3500, and GB350

> [!TIP]
> **Consider donating to keep this going:** ☕ **[ko-fi.com/proszty](https://ko-fi.com/proszty)**
> Most supported devices were bought out of pocket (the SF3500 was funded by the community). These days tips go toward ongoing maintenance and buying new clones to port to.

> [!IMPORTANT]
> v1.0.4 fixes a **game-speed regression** (arcade / Wolfenstein 3D ran too fast), the Amiga core (was unplayable - hard-hung on load), and Wolfenstein 3D (failed to launch entirely), plus adds a **Disable Sleep** option, a **Quake II** setup, and the core name shown in the pause menu. It's been tested mostly by one person, so depending on your exact hardware revision you may still hit bugs, quirks, or compatibility issues.
> 
> Please help improve the project by leaving your feedback, bug reports, and suggestions here:
> 📋 **[Submit Anonymous Feedback (Google Forms)](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v1.0.4

### ✨ New

- **😴 Disable Sleep option.** A short press of the power button used to sleep the device (and on some units wake to a black screen). There's now a **Settings → Disable Sleep** toggle (default off). Turn it on and **restart** — the power button no longer sleeps, but a long press still powers off normally. Works by live-patching the sleep code in memory, so nothing on the card is modified (safe even on the boot-verified SF3500-class devices). Currently effective on R36SX and SF3500-class; SF3000/GB350 have a different sleep path.
- **🔫 Quake II.** Play Quake II via the vitaquake2 core (software renderer, heavy — ~25-40fps). Game data goes in a **required `baseq2/` subfolder**: `roms/quake2/baseq2/pak0.pak`. D-pad moves (no analog stick needed). See the [setup guide](docs/cores/quake2.md).
- **🕹️ Core name in the pause menu.** The in-game menu now shows the emulator core's name and version (e.g. `mame4all 0.37b5`) under the thumbnail, so you always know exactly which core is running.
- **🥊 CPS-3 arcade** (`cps3` folder, FB Alpha 2012) — experimental and heavy (Street Fighter III etc. emulate an SH-2 CPU; expect low fps), for the curious.

### 🩹 Fixes

- **Fixed games running too fast (arcade / Wolfenstein 3D / anything not exactly 60fps).** Two bugs compounded: the frame pacer was hardcoded to 60fps (so cores with a different native rate — Wolf3D at 35fps, various arcade games — ran fast), and it only paced *displayed* frames, so cores that skip frames (MAME) ran their skipped frames unthrottled. Pacing now follows each core's true frame rate and runs once per emulated frame. Also: MAME (`m2k`) now ships with frame-skipping **off** so it renders every frame. This also clears up the audio desync those games had.
- **Amiga (UAE): fixed a hard hang on launching any game.** Any Amiga game froze solid (black screen, no audio) a few seconds after launch — the hardware audio driver hangs when asked to init at Amiga's 44.1kHz. The core now emits **48kHz** natively so the driver is happy, with no frontend hacks (which had side-effects on other cores' audio). Also fixed: `.zip` files in `roms/amiga/` weren't being unzipped, and the core's crash/debug logging (silently compiled out) is restored for diagnosability.
- **Wolfenstein 3D: fixed "Could not open ecwolf.pk3!" - the game failed to launch at all.** ecwolf needs its own engine resource pack (separate from the game data) that was never built or shipped. It's now built automatically and ships in `cubegm/bios/ecwolf.pk3`. See the [setup guide](docs/cores/wolf3d.md) - Wolf3D needs **both** this file and your own game data.
- **In-game menu: selection highlight no longer corrupts text in the row above it** (the white pill bled 2px into the previous row, eating thin letter strokes like the "I" in "BIOS").
- **Controls / key-bind screen: selected row is no longer invisible** (it drew white-on-white; now dark text on the pill like the rest of the menu).

### 📖 Docs

- **Per-system setup guides** now live in `docs/cores/` (Arcade, DOS/pico286, Rockbox, Amiga, Wolfenstein 3D, PlayStation 1, **Quake II**) and are linked from the ROM folder table, instead of one long wall of text.
- Fixed stale `cores.md` entries (wrong Atari Lynx core name; leftover "needs wiring up" notes for Amiga/Atari ST) and a missing custom-font note in `theme.md`.

**Updating from v1.0.x:** copy `cubegm/` and `frogui/` from the new package over your card, then copy your device's `install_first/<device>/` folder again. Your ROMs, saves, and settings are untouched.

---

## High-Level Overview

TreeFrogUI is a heavily modified fork of FrogUI, ported to run within the `picoarch` environment on the MIPS-based Hichip handhelds (R36SX, SF3000, SF3000 HD, SF3100, SF3500, GB350). It provides a clean, minimalistic emulation frontend while supporting a massive range of retro gaming platforms.

### Key Features Included:

- **Minimalist & Fast Interface**: A distraction-free ROM browser with vertical system list navigation and intuitive controls.
- **70 Emulator Cores**: Upgraded from only 14 stock cores, adding compatibility for systems like **PlayStation 1**, **Neo Geo / CPS-1 / CPS-2 arcade**, **MS-DOS PC** (via pico286), **PICO-8** (via Fake08/Retro8), **Quake** (via Tyrquake), **Cave Story** (via NXEngine), **Doom** (via PrBoom), and classic computers like Commodore Amiga and Atari ST. See [`cores.md`](cores.md) for the full folder-to-system list.
- **Highly Configurable Cores**: Full support for tweaking libretro core options directly, enabling retro features like system color palette swaps, LCD ghosting emulation, and key mappings.
- **Proper PCSX4ALL Integration**: A configurable PlayStation 1 emulator core supporting `.iso`, `.bin`/`.cue`, `.pbp`, and other standard disc formats. **PS1 needs a real BIOS to save**: drop `scph1001.bin` in `cubegm/cores/.pcsx4all/` (PS1 folder). Without it the emulator runs on HLE, where memory-card saves are broken. See the [install guide](install.md#playstation-1-bios-strongly-recommended).
- **In-Game Save Support**: Battery saves and in-game saves are fully supported across all compatible cores.
- **Auto-Resume on Boot**: Automatically launches you back into your last-played game or the system frontend menu when you boot up your device.
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
- **Give feedback / report a bug:** please do, it is the fastest way to get your device's quirks fixed.
  - 📋 [Anonymous Feedback Form](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)
  - 🐛 [GitHub Issues](https://github.com/tzubertowski/treefrog-ui/issues)

---

## Want TreeFrogUI on another device?

Six devices are supported today (R36SX v2.6/v2.7, SF3000, SF3000 HD, SF3100, SF3500, GB350). The **SF3000 Pro** is a different beast: it runs entirely different firmware with no rkgame stack, so the boot hook doesn't apply and it needs its own port. Other Hichip-based clones and HDMI-out variants are candidates too.

The catch: porting needs the actual hardware in hand. Bootloaders, input wiring, and displays all differ between clones, and the protected variants need live debugging. There's no way to do it blind.

Most devices supported so far were bought out of my own pocket (the SF3500 was funded by the community), and there are far more clones out there than I can keep buying. If you want to see a port happen, chip in: ☕ **[ko-fi.com/proszty](https://ko-fi.com/proszty)**. Tips go toward ongoing maintenance and buying the next clone to port to.
