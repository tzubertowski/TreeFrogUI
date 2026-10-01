## TreeFrogUI v1.6.0_d prerelease

Changes since v1.6.0_c:

- Language selection now discovers locales from the installed translation JSON files, restoring Arabic, French, and Italian automatically.

## TreeFrogUI v1.6.0_c prerelease

Changes since the v1.6.0_a build:

- Fixed release CI so FroggyKVM is built and packaged as
  `cubegm/cores/j2me_libretro.so`.
- Bundled the J2ME runtime classes, `roms/j2me/`, theme artwork, and the
  `Roland_SC-55.sf2` SoundFont at `cubegm/bios/Roland_SC-55.sf2`.
- Fixed the FluidLite build dependency ordering so clean release builds are
  reproducible.

## TreeFrogUI v1.6.0_a prerelease

Changes since the v1.5.0 release:

- Fixed QPSX packaging: the SF3000 QPSX core is now built during release CI,
  included in `cubegm/cores/` as `qpsx_libretro.so`, and selected by FrogUI.

Changes since the v1.5.0_j build:

- Added the experimental QPSX PlayStation core in `roms/qpsx`. It is not fully
  integrated yet; hold **START for about one second** while playing to open
  its core menu.

- Completed the built-in translations across all 10 supported locales. Every
  locale now contains the full 250-string catalog, including the Picoarch
  player controls, emulator menu labels, settings, remapping prompts, and
  language names.
- Corrected remaining untranslated or wrong-language labels in the French,
  Italian, Portuguese, Spanish, Russian, and Chinese catalogs.

Changes since the v1.5.0_i build:

- Restored opt-in diagnostics on SF3000: `log.txt` is no longer created or
  written unless the user creates it first.

User-facing changes since the stable `v1.4.0_q` release:

- Battery status uses the calibrated curve and adds an option to restore the stock battery indicator.
- Fixed localized Picoarch player-control labels, the missing volume percent sign, and volume value alignment.
- Picoarch reports the fail count correctly when audio starvation is detected.

- Nintendo DS is available in the new `roms/nds` folder through the
  experimental standalone DSperate emulator. It uses the bounded MIPS JIT
  with safe native ALU forms and interpreter fallback for unsupported forms;
  Select + Start exits back to TreeFrogUI.
- Audio fixes suppress idle speaker static, fix silent PS1 launches and media
  playback after audio handoff, and make launcher menu ticks audible.
- System volume is shared between FrogUI Settings, the in-game menu, and the
  physical volume buttons, with changes followed live during gameplay.
- Appearance settings add optional Allium-inspired colour palettes, the Nunito
  font used by Allium, and an adjustable UI font size from 18 to 26 px. The
  existing default colour theme remains unchanged.
- Added French and Italian translations, updated Brazilian Portuguese, and
  expanded the Japanese locale with the custom-aspect-ratio setting.
- Arabic language support and improved complex Unicode text rendering via
  HarfBuzz and SheenBidi, with the required font and license files bundled.
- FrogShell gains an optional Developer Mode with a terminal, command history,
  script and executable launching, and USB keyboard input where supported.
  Hold L1 + R1 + X + Y for about two seconds to toggle it, or create
  `frogui/developer.flag` on the SD card.
- FrogShell's on-screen keyboard adds caps, symbols, and modifier keys.
- The ebook reader combines upstream progress-saving improvements with the
  local fixes for page-turn freezes, hidden progress files, and page fit above
  the status bar. Saves use checked atomic replacement and are deferred until
  navigation settles; the MuPDF cache remains limited to 16 MB.
- Updated PS1 compatibility reports.
- Added 117 newly tested PS1 games to the compatibility list.
- Picoarch now uses portable build paths, restores core logging under `/logs`,
  reduces log spam, and builds its PNG reader against libpng16.
- Release builds now compile FrogShell and the ebook reader from source so the
  packages include their latest changes.

Thanks to [ozkaoz](https://github.com/ozkaoz) for the audio fixes and FrogShell
Developer Mode, and
[Maheshivara](https://github.com/Maheshivara) for ebook reader improvements and
Brazilian Portuguese updates,
[MartStartIV](https://github.com/MartStartIV) for the Spanish translation
updates plus the French and Italian translations,
[spanscape](https://github.com/spanscape) for Japanese translation updates,
and [Trademarked69](https://github.com/Trademarked69) for picoarch build and
logging fixes.

This is a prerelease for testing. Copy `update.zip` to the SD-card root and
reboot, or use the full ZIP and the matching `install_first/<device>/` files
for a fresh installation. Keep a backup of your card.
## TreeFrogUI v1.6.0_b prerelease

Changes since the v1.6.0_a build:

- Added **Java Games** support through the FroggyKVM J2ME / MIDP 2.0 emulator.
  Put `.jar` or `.jad` files in `roms/j2me/`; the release includes the
  `j2me_libretro.so` core, runtime classes, Java Games artwork, and the
  `roms/j2me/` folder.
- Added FluidLite MIDI synthesis for J2ME games, with the SoundFont accepted
  from either `bios/` or `cubegm/bios/`.

J2ME emulator credit: [Sajnaps / FroggyKVM](https://github.com/Synaps33/FroggyKVM).
