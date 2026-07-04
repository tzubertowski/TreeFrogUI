Welcome to **TreeFrogUI** (v1.0.3): one build for **six** handhelds: R36SX (v2.6 & v2.7), SF3000, SF3000 HD, SF3100, SF3500, and GB350

> [!TIP]
> **Consider donating to keep this going:** ☕ **[ko-fi.com/proszty](https://ko-fi.com/proszty)**
> Most supported devices were bought out of pocket (the SF3500 was funded by the community). These days tips go toward ongoing maintenance and buying new clones to port to.

> [!IMPORTANT]
> v1.0.3 is a small stability release on top of the 1.0 line. It's been tested mostly by one person, so depending on your exact hardware revision you may still hit bugs, quirks, or compatibility issues.
> 
> Please help improve the project by leaving your feedback, bug reports, and suggestions here:
> 📋 **[Submit Anonymous Feedback (Google Forms)](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v1.0.3

### 🩹 Fixes

- **Auto-resume can no longer soft-brick your boot.** If the last-played marker pointed at a ROM that no longer exists (or a game that dies instantly), every boot relaunched it forever: black screen, only fixable by editing the card on a PC. Auto-resume now validates that the game actually exists before resuming, and after two failed resume attempts in one boot it clears the marker and drops you safely into the menu.
- **Menu no longer crash-loops when the `roms` folder is missing.** Cards without a `roms/` folder (or with it named `ROMS`, which some card formats treat as a different name) crashed before the game list could ever appear. The menu now accepts `roms/` or `ROMS/`, creates the folder if it is missing entirely, and always shows at least the Settings row.
- **R36SX: display driver now selects itself.** Hardware revisions vary more than version numbers suggest (some 2.6 and 2.7 units share traits), so the previous v2.7 detection broke boot for some 2.7 owners (black screen with only the battery icon). TreeFrogUI now simply tries the full driver, and if it crashes twice, switches permanently to the safe driver on that card. Worst case you see two brief flickers on the very first boot, then every boot after is clean. Delete `cubegm/driver27.flag` if you ever want it to re-test the full driver.
- **In-game (battery) saves are no longer lost on power-off.** Saves like Game Boy / Pokemon / Harvest Moon are written to the card periodically while you play (every ~10s when they change), instead of only when you open the pause menu or exit. Power off straight from a game and your save survives.
- **SF3000: menu renders in hardware from a cold boot.** The main menu could come up squished (wrong aspect) until you'd launched a game once. It now uses the hardware display path from the first frame, correct aspect every boot. Units that genuinely can't do hardware fall back to software automatically.
- **Fixed: save states froze the console on Mega Drive / Genesis (picodrive).** Saving a state on Sega cores hard-locked the device. The picodrive core's internal save routine shares a function name with TreeFrogUI's own, and the two got crossed, sending the save into an infinite loop. Save and load states now work on Sega cores. (Also hardened the save/load hotkeys so a flaky button press can't trigger a save storm.)

### 🙏 Credits

- **[@patrick-oliveira-ch](https://github.com/patrick-oliveira-ch)** for the excellent auto-resume soft-brick report, exact repro, log evidence, and the safeguard design.
- **[@Jankosx7](https://github.com/Jankosx7)** for pinpointing the missing/`ROMS`-cased roms folder crash, including the exact functions at fault.

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
