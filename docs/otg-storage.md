# Use OTG storage for games

TreeFrogUI can browse and launch games directly from a USB drive connected to
the console through a USB-C OTG adapter. Your regular microSD remains the
system card; OTG is an optional, separate game library.

## What you need

- A USB-C OTG adapter or hub compatible with your console.
- A FAT32-formatted USB flash drive. For a hard drive or SSD, use a powered hub
  if the console cannot supply enough power.
- ROMs arranged like the normal SD card layout:

```text
USB drive
└── roms
    ├── gba
    ├── nes
    ├── ps1
    └── snes
```

Use the same system folder names as the SD-card [ROM folder list](../README.md#rom-folder-setup).

## Select the OTG library

1. Start TreeFrogUI with the system microSD inserted.
2. Connect the prepared USB drive through the OTG adapter. You can connect it
   before booting or while TreeFrogUI is open.
3. Open **Settings → Library**.
4. Confirm that **OTG Storage: connected** is shown.
5. Change **ROM Source** from **SD** to **OTG**, then leave Settings.

The Games tab now shows the USB drive's `roms/` folder. Change **ROM Source**
back to **SD** at any time to return to the microSD library.

## If OTG is unavailable

The Settings screen deliberately greys out **ROM Source: SD** and shows
**OTG Storage: not connected** until a compatible drive with a `roms/` folder
is mounted. Check the adapter, cable, drive format, and folder spelling.

## Safe removal

Exit a running game and switch back to **SD** before unplugging the OTG drive.
Do not disconnect a drive while a game is loading or running from it.

This is different from **USB Mode** in Apps: USB Mode lets a PC access the
console's microSD; OTG storage lets the console read games from an external USB
drive.
