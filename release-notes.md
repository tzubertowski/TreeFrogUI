> [!TIP]
> **Consider donating to keep this going:** ☕ **[ko-fi.com/proszty](https://ko-fi.com/proszty)**
> Most supported devices were bought out of pocket (the SF3500 was funded by the community). These days tips go toward ongoing maintenance and buying new clones to port to.

> [!IMPORTANT]
> v1.0.5 overhauls the **audio pipeline** (cleaner sound on Genesis, SNES, PS1, GBA, arcade - anything not natively 48kHz - plus a fix for sound cutting out until reboot), fixes **Amiga games crashing on launch**, adds **Heretic & Hexen** support and the **snes9x2010** SNES core. It's been tested mostly by one person, so depending on your exact hardware revision you may still hit bugs, quirks, or compatibility issues.
> 
> Please help improve the project by leaving your feedback, bug reports, and suggestions here:
> 📋 **[Submit Anonymous Feedback (Google Forms)](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v1.0.5

### ✨ New

- **🧙 Heretic & Hexen.** The Doom core (`prboom` folder) was updated to the latest upstream, which now includes full Heretic and Hexen game logic - drop `heretic.wad` / `hexen.wad` (or the shareware `heretic1.wad`) next to your Doom WADs in `roms/prboom/`.
- **🎮 snes9x2010 core.** A more accurate (but heavier) SNES core, selectable per game via the core picker in the game options - try it on games where the default core glitches.

### 🩹 Fixes

- **Amiga (UAE): fixed games crashing to a black screen on launch.** Launching any Amiga game killed the frontend right after the core finished loading: the audio driver was being re-initialized from the emulator thread while the audio thread was still playing (Amiga's load-time warmup made that overlap a certainty). The driver is now initialized once, on the audio thread only, and never touched again mid-session.
- **🔊 Better audio on most systems (Genesis, SNES, PS1, GBA, Doom, arcade...).** The hardware audio driver was previously re-initialized at each emulator's native sample rate and left to do the rate conversion itself - and its internal resampler is poor (crackle, rough pitch). The DAC now always runs at 48kHz and TreeFrogUI does the conversion with a proper linear resampler, so every core gets the same clean output path. Systems that are natively 48kHz (NES, Game Boy) were always fine and are unchanged.
- **🔇 Fixed sound sometimes cutting out entirely** (no audio in any game until a reboot). Starting a game could catch the audio daemon while it was still tearing down the previous session; a failed first init was treated as permanent. The DAC init now retries for up to 2 seconds.

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
