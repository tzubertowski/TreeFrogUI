> [!IMPORTANT]
> v1.0.13 adds native hardware-decoded video playback and polishes navigation, scaling and emulator menus across supported devices.
>
> **[Submit anonymous feedback](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v1.0.13

- **Native video player.** Put normal MP4, MKV, AVI, MOV, MPEG, TS or WebM files in `roms/videos/`. Playback uses the stock hardware decoder, needs no conversion, and has MinUI-style controls colored by the active TreeFrogUI theme.
- **Smoother Integer scaling.** Cached scaling maps remove the v1.0.12 performance regression, while more tolerant audio buffering prevents the associated sound stutter.
- **Vectrex restored.** Games once again use the correct native display envelope instead of opening to a black screen.
- **VICE controls restored.** Keyboard and joystick modes now receive RetroPad input in the VICE x64 core.
- **Safer list navigation.** Scrolling through games no longer opens Search accidentally, and Left/Right stays within the Vertical view instead of changing tabs. Use L1/R1 for tabs.
- **Readable emulator menus.** Selected values that are wider than the screen now scroll so the complete text can be read.
- **Clean menu return.** Select+Start is held back until released after closing the emulator menu, preventing the shortcut from leaking into games and triggering actions such as PCE soft reset.

**Updating:** copy `cubegm/` and `frogui/` over the card, then copy `install_first/<device>/` again. ROMs, saves and settings are untouched.

---

*Overview, features, install guide, troubleshooting and porting information are in the [README](README.md).*
