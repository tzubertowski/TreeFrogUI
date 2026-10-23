# TreeFrogUI v1.8.0_l prerelease

## Changes since v1.8.0_k

- **FrogUI:** System background images now warm into the existing render cache in a background worker after launch and when the active background settings change. Later system navigation can use pre-rendered images instead of waiting for image decode and resizing.
- **SNES:** Added Snes9x-Z in `roms/snesz` as a newer, compatibility-oriented alternative. It runs slower than the default Snes9x 2005 core on R36SX.

## Other changes included since the v1.0.15 stable base

- Added Picante8, experimental Duke Nukem 3D, ClassiCube, Minecraft PE, Captain Claw, Diablo 1, Java Games, Nintendo DS and experimental QPSX support. Added OpenLara and VVVVVV under **Games → Ports**, with setup guides for user-supplied game data; ports have a separate release collection.
- Added support profiles and install guidance for R36SX/R36 HD variants, SF3000, SF3000 HD, SF3000HD without HDMI, SF3100, SF3500 and GB350.
- Added FrogUI menu-frame screenshots, Nunito, improved translations and Arabic text rendering, shared volume and battery indicators, and PICO-8 system alternatives.
- Improved game handoff, PicoArch audio startup and underrun handling, Java saves and game exit, ebook progress and page turning, and offline update recovery.

For a fresh installation, use the full archive and matching `install_first/<device>/` files. To update an existing installation, copy `update.zip` to the SD-card root and reboot. Back up your card first.
