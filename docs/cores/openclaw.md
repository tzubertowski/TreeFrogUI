# Captain Claw / OpenClaw

TreeFrogUI includes the OpenClaw libretro core for playing Captain Claw on
supported MIPS devices.

## Installation

Copy the following files into the SD card's `roms/openclaw/` directory:

```text
roms/openclaw/
├── CLAW.REZ
├── ASSETS.ZIP
├── clacon.ttf
└── Start Captain Claw.claw
```

The release already supplies `ASSETS.ZIP`, `clacon.ttf`, and the small
`Start Captain Claw.claw` launcher. Obtain `CLAW.REZ` from a legally owned
Captain Claw installation, or from the matching asset package in the
[FroggyClaw repository](https://github.com/tzubertowski/FroggyClaw).

Do not rename `CLAW.REZ`; the core looks for that exact filename. Start the
game by selecting **OpenClaw / Kapitan Pazur** in FrogUI and choosing **Start
Captain Claw**.

## Notes

- The core is currently an experimental SF3000/R36HD port.
- Saves are stored under the OpenClaw content directory on the SD card.
- The core renders the 640×480 game window into the device's panel while
  preserving the game's aspect ratio.
