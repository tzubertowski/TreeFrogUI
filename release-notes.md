# TreeFrogUI v1.8.0_g prerelease

## TEST: PCSX4ALL PS1 audio

PCSX4ALL's standalone PS1 audio now uses a buffered 48 kHz output path with underrun recovery. On R36SX/R36HD, startup also reopens the validated speaker amplifier output, fixing runs where the game produced audio samples but the speaker stayed silent.

**Testers:** Please launch a PS1 game on your device and report whether audio starts, whether it crackles during busy scenes, and your device model. On R36SX/R36HD, the standalone log should include `audio amp: R36 speaker output enabled`. Underruns can still cause audible gaps; this build aims to make output reliable and reduce the crackle around them.

## Other changes included since the v1.0.15 stable base

- Added OpenLara and VVVVVV, then moved port setup guides and the Ports collection into their separate release. See the [Ports Collection](https://github.com/tzubertowski/TreeFrogUI_PortsCollection) for port downloads and game data instructions.
- Added Picante8, experimental Duke Nukem 3D, ClassiCube, Minecraft PE, Captain Claw, Diablo 1, Java Games, Nintendo DS, and experimental QPSX support. The latest DS emulator build is included.
- Added a FrogUI screenshot shortcut, improved translations and Arabic text rendering, and shared volume and battery indicator controls.
- Fixed launcher handoff between games, audio startup and menu tick issues, Java save handling, ebook progress and page turning, and offline update recovery.

For a fresh installation, use the full archive and matching `install_first/<device>/` files. To update an existing installation, copy `update.zip` to the SD-card root and reboot. Back up your card first.
