# Ports

Ports are distributed separately by the TreeFrogUI Ports Collection and installed
with TreeFrogUI Installer. Select either standalone ports or ports requiring
game data during installation or update. They appear under one **Ports** entry
in the Games view. Put each port's required files in its named folder; leave the
supplied launcher at the root. The UI shows only the launcher name (not `.sh`)
and hides data folders:

```text
roms/ports/
├── <Port name>.sh
├── .res/
│   └── <Port name>.png    # boxart for that launcher
└── <port>/                # hidden data and saves
```

For example, **Captain Claw** is launched by `roms/ports/Captain Claw.sh`, while
its game data goes in `roms/ports/openclaw/`. Do not move the `.sh` launcher into
the data folder. FrogUI uses the launcher's matching `.res/<Port name>.png`
floppy-disk box art in the active theme's standard artwork panel.

## Setup

1. Install a port category from TreeFrogUI Installer or download an archive from
   the [Ports Collection releases](https://github.com/tzubertowski/TreeFrogUI_PortsCollection/releases).
2. Copy any required game data into the exact folder and filenames shown by the
   missing-files screen. Commercial game files are not included.
3. Open **Games → Ports** and select the port's friendly name. If required files
   are missing, the device displays the missing filenames and a QR code to the
   matching setup guide.

Launchers share one required-file checker. If port data is missing, FrogUI
shows the missing filenames and a QR code linking to that port's setup guide;
the game is not started.

On first boot after updating, TreeFrogUI migrates supported old port folders
from `roms/<port>/` into `roms/ports/<port>/`. It shows per-port progress, moves
user game data (not old launchers or binaries), and keeps release-provided files
authoritative on name conflicts. The old folder is removed only after its data
has merged successfully. If migration is interrupted, reboot to let it resume.

Each launcher's missing-files prompt links to its setup guide in the Ports
Collection.
