> [!IMPORTANT]
> v1.0.11_k adds Odyssey² support, background dimming and complete theme artwork, with cleaner shutdown and battery overlays.
> 
> **[Submit anonymous feedback](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v1.0.11_k

- **Odyssey² / Videopac support.** The missing O2EM core is now included. Put `o2rom.bin` in `cubegm/bios/` and `.bin` games in `roms/o2em/`.
- **Background controls.** Background Image Fit now defaults to Stretch. Background Dim defaults to 15% and can be adjusted from 0-100% under theming options.
- **Complete theme artwork.** The default Art Book artwork and Canvas Pastel include polished backgrounds for every supported system instead of generic fallbacks.
- **Smaller download.** Canvas Pastel now ships only the backgrounds TreeFrogUI uses. Unused ES-DE systems and duplicate high-resolution files have been removed.
- **Shutdown screen cleanup.** TreeFrogUI no longer remains visible around the shutdown logo corners.
- **Battery overlay cleanup.** The stock battery icon is covered only around TreeFrogUI's custom indicator, without affecting the rest of the top-right corner.
- **C64 setup clarified.** VICE already includes its standard C64 and drive ROM data. Games in `roms/c64/` do not need a separate BIOS pack.

- **Vectrex support.** Added a software VecX core for `.vec` games. No 3D GPU is required.
- **TIC-80 startup fix.** Static Lua runtime is now included, fixing first-frame crashes.
- **Vectrex display fix.** Native portrait frames no longer get expanded into an oversized 16:9 buffer.
- **R36SX battery gauge.** Battery display now uses three broad states: low, mid and full, with a wider full range.
- **Folder navigation.** Exiting a system folder returns to that system in the parent list instead of resetting to the first item.

- **SF3500 stability.** Menu frames are staged before display DMA. The screen no longer repeatedly blanks and resets the cursor to the first item.
- **Ebook reader fix.** EPUB books no longer freeze after turning several pages. Exiting with SELECT + START remains responsive.
- **Ebook page fit and clean library.** MuPDF reserves space for the status bar so the final line is not cut off. Reading positions now live under a hidden `.positions/` folder instead of appearing beside every book.
- **MAME 2000 ROM loading.** Wrong or incomplete MAME 0.37b5 sets return to the menu instead of crashing after a failed load.
- **Horizontal style.** Style can be switched between Vertical and Horizontal independently of the selected theme. Horizontal scrolls the system list left and right with animated names and background crossfades.
- **Friendly system names.** An independent toggle expands folder codes such as `ps` and `gba` in both Vertical and Horizontal styles.
- **Themed Game Switcher.** The header and battery use the theme's subdued colours. The selected game's name and play information use the active accent. Screenshots keep their full geometry beneath the overlays; press Y to toggle a minimal fullscreen view.
- **File cache control.** File caching is off by default. Settings now includes a rebuild action for clearing stale entries and regenerating the library index.
- **PCSX4ALL BIOS detection.** The recommended `cubegm/bios/` path takes priority. Old `.pcsx4all` locations work again, including their `bios/` subfolders.
- **Loose BIOS naming.** PCSX4ALL accepts any 512 KiB PS1 BIOS, matches names without case sensitivity and prefers `scph*` files.
- **Correct full-charge reading.** FrogUI, the pause menu and PCSX4ALL now show 100% at the battery ADC's real full-charge level instead of waiting for an unreachable maximum value.
- **Charging indicator cleanup.** The stock battery glyph stays hidden when charging, including on rotated and double-buffered SF3500-class displays.
- **Amstrad CPC compatibility.** The standard Amstrad folder now uses Cap32, including zipped disks. Oversized core frames respect Native, forced and Fill aspect-ratio settings.

**Updating:** copy `cubegm/` and `frogui/` over your card, then copy your device's `install_first/<device>/` folder again. ROMs, saves, and settings are untouched.

---

*Overview, features, install guide, troubleshooting, and porting info live in the [README](README.md).*
