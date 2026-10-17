# TreeFrogUI v1.8.0_d prerelease

## AUDIO TEST: LESS CRACKLY AUDIO

PicoArch audio should crackle less across cores. This build fixes the SF3000 audio buffer prefill, adapts playback slightly when emulation slows, and fades sound back in more gently after an underrun. It also removes periodic and per-underrun SD-card logging from the audio path. The change is in both `picoarch` and `picoarch_hi`.

**Testers:** Please replay places that crackled in `v1.8.0_c`, especially Super Metroid, OpenLara, and other demanding games. Tell us the device, game/core, whether the crackle is less frequent or softer, and whether the audio pitch or video smoothness feels different. Long stalls can still leave audible gaps; this prerelease aims to make common underruns less harsh.

## Other changes included since the v1.0.15 stable base

- Added OpenLara and VVVVVV under **Games → Ports**, with setup guides for user-supplied game data. The Ports catalogue also includes per-port launchers and migration from older ROM folders.
- Added Picante8, experimental Duke Nukem 3D, ClassiCube, Minecraft PE, Captain Claw, Diablo 1, Java Games, Nintendo DS, and experimental QPSX support in the intervening prereleases. The latest DS emulator build is included.
- Added a FrogUI screenshot shortcut, improved translations and Arabic text rendering, and shared volume and battery indicator controls.
- Fixed launcher handoff between games, several audio startup and menu-tick problems, Java save handling, ebook progress and page turning, and offline update recovery.

The [v1.6.0_s notes](https://github.com/tzubertowski/TreeFrogUI/releases/tag/v1.6.0_s) and [v1.7.0 notes](https://github.com/tzubertowski/TreeFrogUI/releases/tag/v1.7.0_a) contain the detailed earlier changes. The [OpenLara](docs/cores/openlara.md) and [VVVVVV](docs/cores/vvvvvv.md) guides explain required game files.

For a fresh installation, use the full archive and matching `install_first/<device>/` files. To update an existing installation, copy `update.zip` to the SD-card root and reboot. Back up your card first.
