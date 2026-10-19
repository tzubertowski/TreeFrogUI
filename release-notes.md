# TreeFrogUI v1.8.0_h prerelease

## Tester focus

- **Nintendo DS performance:** includes the latest DSperate build, with DraStic scanline optimizations ported to the MIPS build and further MIPS JIT improvements. Please test demanding games and report your device and any slowdowns or visual issues.
- **PCSX4ALL PS1 audio:** the standalone player now starts with a 50 ms audio queue, up from 20 ms, to better absorb short scheduling delays that can cause crackling. Please test busy scenes and report whether crackling improves. The larger queue adds about 30 ms of audio latency.

## Other changes included since the v1.0.15 stable base

- Added OpenLara and VVVVVV, then moved port setup guides and the Ports collection into their separate release. See the [Ports Collection](https://github.com/tzubertowski/TreeFrogUI_PortsCollection) for port downloads and game data instructions.
- Added Picante8, experimental Duke Nukem 3D, ClassiCube, Minecraft PE, Captain Claw, Diablo 1, Java Games, Nintendo DS, and experimental QPSX support.
- Added a FrogUI screenshot shortcut, improved translations and Arabic text rendering, and shared volume and battery indicator controls.
- Fixed launcher handoff between games, audio startup and menu tick issues, Java save handling, ebook progress and page turning, and offline update recovery.

For a fresh installation, use the full archive and matching `install_first/<device>/` files. To update an existing installation, copy `update.zip` to the SD-card root and reboot. Back up your card first.
