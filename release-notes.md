> [!IMPORTANT]
> v1.0.13 adds native hardware-decoded video and image playback and polishes navigation, scaling and emulator menus across supported devices.
>
> **[Submit anonymous feedback](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## Offline update packages

- **Automatic offline updates.** Releases now ship both the existing full-install ZIP and a differential `update.zip` built against the preceding numeric release line (for example, `13_b` compares with the newest `12`, not `13_a`). Copy `update.zip` directly to the SD-card root and reboot; TreeFrogUI verifies and installs it, then removes it only after success.
- **Configuration migrations included.** Update packages intentionally refresh FrogUI and emulator configuration so breaking changes and new required options take effect. The previous configs are backed up on the card.
- **Safe recovery behavior.** Updates are checksum-verified, use atomic per-file replacement, retain interrupted or invalid packages for retry, and never delete personal ROMs, BIOS files, saves, screenshots or media.
- **Kudos to devdeve1oper**, who suggested the automatic console-update workflow. 💚

Maintainers keep comparison ZIPs under `release/artifact/`; current staging and both publishable files live under `release/latest/`. Follow [`docs/RELEASING.md`](docs/RELEASING.md) for the complete build, validation, and publishing procedure.

---

## What's New in v1.0.13

- **Native video player.** Put normal MP4, MKV, AVI, MOV, MPEG, TS or WebM files in `roms/videos/`. Playback uses the stock hardware decoder, needs no conversion, and has MinUI-style controls colored by the active TreeFrogUI theme.
- **Correct SF video orientation.** Video and its controls now follow the device profile's panel rotation, fixing 90-degree counter-clockwise playback and reversed/top-aligned controls on SF3000 and SF3500.
- **Native image viewer.** Put JPG, PNG, BMP, GIF, TGA, ICO, WebP or TIFF files in `roms/images/`. The stock picture decoder provides Fit/Fill and rotation, with themed controls and sibling-image browsing.
- **Smoother Integer scaling.** Cached scaling maps remove the v1.0.12 performance regression, while more tolerant audio buffering prevents the associated sound stutter.
- **Vectrex restored.** Games once again use the correct native display envelope instead of opening to a black screen.
- **VICE controls restored.** Keyboard and joystick modes now receive RetroPad input in the VICE x64 core.
- **Safer list navigation.** Scrolling through games no longer opens Search accidentally, and Left/Right stays within the Vertical view instead of changing tabs. Use L1/R1 for tabs.
- **Readable emulator menus.** Selected values that are wider than the screen now scroll so the complete text can be read.
- **Clean menu return.** Select+Start is held back until released after closing the emulator menu, preventing the shortcut from leaking into games and triggering actions such as PCE soft reset.
- **Clearer classic-FPS setup.** The Wolfenstein guide now covers Wolf3D (`.wl1`/`.wl6`) and Spear of Destiny (`.sdm`/`.sod`) data sets. The bundled PrBoom core supports Doom, Heretic and Hexen IWADs from `roms/prboom/`; game data is not bundled.

**Updating from an older build:** copy `cubegm/` and `frogui/` over the card, then copy `install_first/<device>/` again. This one-time manual update installs the offline updater; later releases need only `update.zip` copied to the SD-card root.

---

*Overview, features, install guide, troubleshooting and porting information are in the [README](README.md).*
