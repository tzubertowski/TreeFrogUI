## What's new

### Video and device fixes

- SF3000/SF3500 integer scaling uses a cached 640×480 canvas with black bars; the hot 2× path keeps the work on the fast pixel-copy path while HCGE handles panel presentation.

### Experimental PSP support

- Added a `roms/psp/` entry and PSP theme artwork.
- PSP launch prefers an optional `cubegm/ppsspp` standalone binary and falls back to `ppsspp_libretro.so` when it is absent.
- The standalone source is tracked through <https://github.com/DevBobby-REP/PPSSPP-DATAFROGSF3000>.
- PPSSPP remains experimental and is not enabled as a guaranteed working emulator; see [the development investigation](docs/dev/ppsspp-investigation.md).

### Install or update

Recommended: use the [TreeFrogUI Installer](https://github.com/tzubertowski/TreeFrogUI-installer/releases/latest).

Manual fallback:

- Fresh install: apply `install_first/<device>/` from the full package.
- Update: copy `update.zip` to the SD-card root and reboot.

Keep the original SD-card backup before applying an update.
