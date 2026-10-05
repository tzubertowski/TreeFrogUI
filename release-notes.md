## TreeFrogUI v1.6.0 prerelease

Changes since v1.5.0:

- Added the ClassiCube / Minecraft SF3000 core and `roms/classicube/` launch
  entry, with friendly localized system naming.
- Added ClassiCube / Minecraft support based on
  [Sajnaps / FroggyCraft](https://github.com/Synaps33/FroggyCraft), including
  themed backgrounds and the packaged `texpacks/default.zip`.
- Added **Java Games** support through the FroggyKVM J2ME / MIDP 2.0 emulator.
  Put `.jar` or `.jad` files in `roms/j2me/`; the release includes the core,
  runtime classes, artwork, and the `roms/j2me/` folder.
- Added FluidLite MIDI synthesis for Java Games, with the SoundFont accepted
  from either `bios/` or `cubegm/bios/`.
- Added the experimental QPSX PlayStation core and packaged it as
  `cubegm/cores/qpsx_libretro.so`.
- Added Nintendo DS through the experimental standalone DSperate emulator in
  `roms/nds`.
- Language selection now discovers locales from installed translation JSON
  files; adding a locale no longer requires C registration. German and Turkish
  translations are included.
- Completed the built-in translations across the supported locales and fixed
  remaining untranslated or wrong-language labels in the existing catalogs.
- Added Arabic support and improved complex Unicode rendering through HarfBuzz
  and SheenBidi, with the required font and license files bundled.
- Added optional Allium-inspired colour palettes, the Nunito font, and an
  adjustable UI font size from 18 to 26 px.
- Audio fixes suppress idle speaker static, fix silent PS1 launches and media
  playback after audio handoff, and make launcher menu ticks audible.
- System volume is shared between FrogUI Settings, the in-game menu, and the
  physical volume buttons.
- FrogShell gains an optional Developer Mode with a terminal, command history,
  script and executable launching, and USB keyboard input where supported.
- FrogShell's on-screen keyboard adds caps, symbols, and modifier keys.
- The ebook reader includes upstream progress-saving improvements and local
  fixes for page-turn freezes, hidden progress files, and page fitting.
- Added 117 newly tested PS1 games to the compatibility list.
- Release builds now compile FrogShell and the ebook reader from source.
- Fixed release CI dependency ordering and packaging for the new cores,
  runtime assets, fonts, artwork, and licenses.

Thanks to [Sajnaps](https://github.com/Synaps33) for FroggyCraft and FroggyKVM,
[MartStartIV](https://github.com/MartStartIV) for the German and Turkish
translations in [PR #43](https://github.com/tzubertowski/FrogUI/pull/43) and
[PR #44](https://github.com/tzubertowski/FrogUI/pull/44),
[ozkaoz](https://github.com/ozkaoz) for audio fixes and FrogShell Developer
Mode, [Maheshivara](https://github.com/Maheshivara) for ebook reader
improvements and translation updates, [spanscape](https://github.com/spanscape)
for Japanese translation updates, and
[Trademarked69](https://github.com/Trademarked69) for Picoarch build and
logging fixes.

This is a prerelease for testing. Copy `update.zip` to the SD-card root and
reboot, or use the full ZIP and matching `install_first/<device>/` files for a
fresh installation. Keep a backup of your card.
