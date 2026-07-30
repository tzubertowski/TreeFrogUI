> [!IMPORTANT]
> v1.0.11 fixes SF3500 menu crashes and ebook reader lockups. It also includes the menu, PS1, display and interface improvements from v1.0.10_f.
> 
> **[Submit anonymous feedback](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v1.0.11

- **SF3500 stability.** Menu frames are staged before display DMA. The screen no longer repeatedly blanks and resets the cursor to the first item.
- **Ebook reader fix.** EPUB books no longer freeze after turning several pages. Exiting with SELECT + START remains responsive.
- **Faster menus.** Browsing, scrolling and Settings no longer pause after each input. Holding a direction repeats normally.
- **Faster PS1 emulation.** PCSX4ALL has a new optimized MIPS build and lower-overhead audio settings. Tekken 3 improved from about 26.6 to 29.7 displayed FPS in the same R36SX fight test. Full lighting and blending remain enabled. Results vary by game.
- **Large libraries load faster.** ROM folders are sorted and cached. Changes to folder contents refresh the cache automatically.
- **Updated interface.** Larger bold text, cleaner spacing and matching PCSX4ALL menus.
- **Custom wallpapers.** Add images to `frogui/wallpapers/` and choose Fill, Fit, Stretch, Center or Tile.
- **Recents screenshots.** Gameplay captures now fill the game switcher. PS1 modes no longer appear as squashed wide strips.
- **Reworked Settings.** Options are grouped by category. New controls include Hide Extensions, Background Images and Folder Cache.
- **More aspect ratios.** Choose Integer, Native, 4:3, 16:9, 3:2, 5:4, 8:7, 16:10 or Fill from the in-game Video menu.
- **PS1 display fixes.** Hi-res modes used by games such as Colin McRae Rally and Worms Armageddon no longer freeze or black out the display.
- **PS1 setup fixes.** Face buttons now match their physical positions on fresh setups. Real `scph*.bin` BIOS files in `cubegm/bios/` are detected automatically.
- **Battery fixes.** FrogUI and the in-game menu show the real charge level. The stock battery icon is removed from games and no longer returns when booting into Recents.
- **Battery Colour Mode.** Optionally show a green, blue or red status indicator instead of the fill bar.
- **Volume fix.** Volume buttons continue working after launching and exiting games.

*Known issue: the Nearest video filter can still corrupt the menu on some devices.*

**Updating:** copy `cubegm/` and `frogui/` over your card, then copy your device's `install_first/<device>/` folder again. ROMs, saves, and settings are untouched.

---

*Overview, features, install guide, troubleshooting, and porting info live in the [README](README.md).*
