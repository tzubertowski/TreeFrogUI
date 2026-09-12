## TreeFrogUI v1.5.0 prerelease

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
