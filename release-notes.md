> [!IMPORTANT]
> v1.0.15 adds the FrogShell file manager on top of the v1.0.14 audio, aspect-ratio, image-viewer, Rockbox, and music-player improvements.
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

## What's New in v1.0.15

- **Automatic audio recovery.** Picoarch now performs a clean same-thread AUDDEC/I2SO cycle on startup and reopens the driver if a sample write fails. This automates the recovery previously achieved by briefly launching a PS1 game.
- **Faster custom aspect ratios.** Forced 4:3, 5:4, 8:7 and other ratios retain their corrected pixel geometry without a redundant CPU bilinear pass. The hardware still filters the final enlargement, leaving substantially more CPU time for QuickNES, Nestopia and SNES9x 2005.
- **Simple music player.** Put MP3, M4A, AAC, WAV, FLAC, OGG or Opus files in `roms/music/`. It uses the themed video-player controls: A/Start pauses, Left/Right seeks 10 seconds, L/R seeks 60 seconds, and B/Select exits.
- **Correct image-viewer orientation.** The image HUD now uses the device's explicit rotation profile instead of guessing from framebuffer dimensions, fixing upside-down informational text on SF3000HD-class devices.
- **Image Fit restoration.** Fit mode keeps the firmware picture background active so letterboxed images are no longer promoted to the same full-screen presentation as Fill on affected firmware.
- **Correct Rockbox colors.** The hardware presenter now reads Rockbox's 24-bit framebuffer in its actual BGR byte order, removing the yellow cast from saved and default themes after a cold boot.
- **PCE menu reset fix.** Select+Start remains suppressed until both buttons are released after closing the emulator menu, preventing a PCE hardware reset when changing settings.
- **FrogShell file manager.** Apps now include an offline VitaShell-style SD-card manager with folder icons, file types, updated timestamps, on-demand recursive folder sizes, copy/cut/paste, multi-select, rename, delete, and safe same-name handling. Conflicts offer Skip, numbered copies (`name (1).ext`), or an explicit rewrite confirmation. START+SELECT exits FrogShell.

**Updating from an older build:** copy `cubegm/` and `frogui/` over the card, then copy `install_first/<device>/` again. This one-time manual update installs the offline updater; later releases need only `update.zip` copied to the SD-card root.

---

*Overview, features, install guide, troubleshooting and porting information are in the [README](README.md).*
