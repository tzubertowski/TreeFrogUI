## TreeFrogUI v1.6.0 prerelease

Changes since v1.6.0_m:

- Improved SF3000 PicoArch audio delivery with a larger buffer, longer prefill, and best-effort real-time audio-thread scheduling to reduce underruns under CPU load.
- Disabled automatic frameskip by default in PCSX-ReARMed, PicoDrive, Beetle PCE Fast, SNES9x 2002, and SNES9x 2005; it remains available as a manual option.
- Fixed Activity Tracker long ROM titles so they marquee within their available row width without covering the play-time bar.
- Added Captain Claw through the [FroggyClaw](https://github.com/tzubertowski/FroggyClaw) libretro core; place a legally obtained `CLAW.REZ` in `roms/openclaw/`.
- Fixed OpenClaw SF3000 loading by isolating its SDL compatibility layer from PicoArch's host SDL and removing firmware-only runtime symbol dependencies.

Changes since v1.5.0:

- Added **Minecraft Pocket Edition 0.6.1** through the [FroggyPE](https://github.com/Synaps33/FroggyPE) libretro core, with a one-click `roms/mcpe/` launcher, packaged assets, localized system naming, and theme-matched Minecraft artwork.
- Added **ClassiCube / Minecraft** support based on [Synaps33 / FroggyCraft](https://github.com/Synaps33/FroggyCraft), with a `roms/classicube/` launch entry, friendly localized system naming, themed backgrounds, and the packaged `texpacks/default.zip`.
- Added **Java Games** support through the FroggyKVM J2ME / MIDP 2.0 emulator. Put `.jar` or `.jad` files in `roms/j2me/`; the release includes the core, runtime classes, artwork, and ROM folder.
- Added FluidLite MIDI synthesis for Java Games, with the SoundFont accepted from either `bios/` or `cubegm/bios/`.
- Fixed Java Games crashes caused by unsupported SF3000 CPU instructions, reduced launcher and Java heap memory pressure, and added centered aspect-preserving scaling for portrait and low-resolution games.
- Fixed Java Games RMS save enumeration on SF3000 so existing Doom RPG and other J2ME saves are visible and load correctly; removed temporary RMS diagnostics from the release build.
- Added the experimental QPSX PlayStation core as `cubegm/cores/qpsx_libretro.so`.
- Added Nintendo DS through the latest locally tested DSperate SF3000 package in `roms/nds`, with the audited MIPS JIT enabled by default.
- Language selection now discovers locales from installed translation JSON files, so adding a locale no longer requires C registration. German and Turkish translations are included.
- Completed the built-in translations across supported locales and fixed remaining untranslated or wrong-language labels.
- Added Arabic support and improved complex Unicode rendering through HarfBuzz and SheenBidi, including the required fonts and licenses.
- Added optional Allium-inspired colour palettes, the Nunito font, and adjustable UI font sizes from 18 to 26 px.
- Fixed idle speaker static, silent PS1 launches, media playback after audio handoff, and inaudible launcher menu ticks.
- Shared system volume between FrogUI Settings, the in-game menu, and physical volume buttons.
- Added a selectable stock or TreeFrogUI battery indicator shared by FrogUI and PicoArch; the stock overlay now appears in menus without covering gameplay.
- Restored the calibrated TreeFrogUI battery curve from v1.5.0_l so the custom indicator reports gradual percentages consistently in FrogUI and PicoArch.
- Improved offline-update recovery with explicit same-version repair installs and safe FAT32 document-name migration that only removes a case-conflicting file when its verified replacement is present.
- Added an optional FrogShell Developer Mode with a terminal, command history, script and executable launching, and USB keyboard input where supported.
- Added caps, symbols, and modifier keys to FrogShell's on-screen keyboard.
- Included upstream ebook-reader progress saving and local fixes for page-turn freezes, hidden progress files, and page fitting.
- Added 117 newly tested PS1 games to the compatibility list.
- Release builds now compile FrogShell and the ebook reader from source.
- Fixed release CI dependency ordering and packaging for new cores, runtime assets, fonts, artwork, and licenses.

Thanks to [Synaps33](https://github.com/Synaps33) for FroggyPE, FroggyCraft, and FroggyKVM; [MartStartIV](https://github.com/MartStartIV) for the German and Turkish translations in [PR #43](https://github.com/tzubertowski/FrogUI/pull/43) and [PR #44](https://github.com/tzubertowski/FrogUI/pull/44), and for the updater recovery ideas in [PR #75](https://github.com/tzubertowski/TreeFrogUI/pull/75); [ozkaoz](https://github.com/ozkaoz) for audio fixes and FrogShell Developer Mode; [Maheshivara](https://github.com/Maheshivara) for ebook-reader improvements and translation updates; [spanscape](https://github.com/spanscape) for Japanese translation updates; and [Trademarked69](https://github.com/Trademarked69) for Picoarch build and logging fixes.

This is a prerelease for testing. Copy `update.zip` to the SD-card root and reboot, or use the full ZIP with the matching `install_first/<device>/` files for a fresh installation. Keep a backup of your card.
