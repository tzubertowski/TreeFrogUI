# TreeFrogUI v1.8.0_p prerelease

## Changes since v1.8.0_o

- **FrogUI:** The selected-item pill now animates consistently through the system list and nested menus. System backgrounds begin loading in the background at startup, so browsing no longer has to trigger image loads. PICO-8 aliases use the PICO-8 artwork. The `zsnes` folder selects Snes9x-Z, shows a friendly system name, and reuses SNES artwork and backgrounds. Startup avoids a theme-color flash while backgrounds load; when background images are disabled, the theme color appears immediately.
- **PicoArch:** Fixed pill alignment and width in submenus, and made long option labels scroll smoothly at a slower pace.

## Other changes included since the v1.0.15 stable base

- Added Snes9x-Z as a slower, compatibility-oriented alternative SNES core, plus Picante8, experimental Duke Nukem 3D, ClassiCube, Minecraft PE, Captain Claw, Diablo 1, Java Games, Nintendo DS and experimental QPSX support. Added OpenLara and VVVVVV under **Games → Ports**, with setup guides for user-supplied game data; ports have a separate release collection.
- Added support profiles and install guidance for R36SX/R36 HD variants, SF3000, SF3000 HD, SF3000HD without HDMI, SF3100, SF3500 and GB350.
- Added FrogUI menu-frame screenshots, Nunito, improved translations and Arabic text rendering, shared volume and battery indicators, and PICO-8 system alternatives.
- Improved game handoff, PicoArch audio startup and underrun handling, Java saves and game exit, ebook progress and page turning, and offline update recovery.

For a fresh installation, use the full archive and matching `install_first/<device>/` files. To update an existing installation, copy `update.zip` to the SD-card root and reboot. Back up your card first.
