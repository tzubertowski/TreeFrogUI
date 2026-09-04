## What's new

### USB and storage

- **USB MTP mode:** guided **Apps → USB Mode** screen for connecting the console to a PC and managing SD-card files.
- MTP exposes complete object metadata, supports KDE/libmtp and host-to-console writes, and has safer repeated entry/exit handling.
- Windows device-identification and compatibility metadata were corrected so the console is recognised as a standard MTP device.
- **OTG ROM library:** a FAT32 USB drive with a matching `roms/` tree can be selected as the Games-library source. The UI shows when OTG is unavailable and falls back to SD.
- USB Mode is grouped under **Apps**, alongside the other utilities.

### UI and input

- **R36SX FN button:** the mapping wizard detects the physical FN key and adds it as the fifteenth bindable button; other devices retain the normal layout.
- Settings categories are collapsible and remember their open/collapsed state across reboots.
- Extension filters are applied per system folder, hide non-launchable PS1 companion files by default, and allow additional extensions to be configured.
- Folder results and filter data are cached so entering Games and Apps does not rescan the SD card unnecessarily.
- Long core/settings menus remain scrollable on the 854×480 display.

### Video, audio, and device fixes

- SF3000/SF3500 integer scaling uses a cached 640×480 canvas with black bars; the hot 2× path keeps the work on the fast pixel-copy path while HCGE handles panel presentation.
- Restored the SF3000 media-player rotation profile.
- Reduced idle SF-class speaker noise by keeping the amplifier muted when no audio is playing, while preserving game and menu audio handoff.
- Volume settings are synchronised with the physical volume-button value and legacy standalone frontends.
- USB and FrogUI diagnostics use the existing opt-in `log.txt` switch.
- Updates remain cumulative across supported 1.x installations.

### Experimental PSP support

- Added a `roms/psp/` entry and PSP theme artwork.
- PSP launch prefers an optional `cubegm/ppsspp` standalone binary and falls back to `ppsspp_libretro.so` when it is absent.
- The standalone source is tracked through <https://github.com/DevBobby-REP/PPSSPP-DATAFROGSF3000>.
- PPSSPP remains experimental and is not enabled as a guaranteed working emulator; see [the development investigation](docs/dev/ppsspp-investigation.md).

### Contributors

- **[@ozkaoz](https://github.com/ozkaoz)** — R36SX FN-button implementation and physical validation.
- **Jose Silva** and **[MartStartIV](https://github.com/MartStartIV)** — USB OTG storage and external-ROM-library work. [MartStartIV on YouTube](https://www.youtube.com/@MartStartIV)

### Install or update

Recommended: use the [TreeFrogUI Installer](https://github.com/tzubertowski/TreeFrogUI-installer/releases/latest).

Manual fallback:

- Fresh install: apply `install_first/<device>/` from the full package.
- Update: copy `update.zip` to the SD-card root and reboot.

Keep the original SD-card backup before applying an update.
