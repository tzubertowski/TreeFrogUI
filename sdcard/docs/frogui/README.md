![FrogUI Logo](res/logo.jpg)

# FrogUI - Minimalistic Launcher for SF2000/GB300 consoles

FrogUI is a libretro-based launcher that provides a simple, clean interface for browsing and launching games on SF2000/GB300 handhelds.

📦 **[Installation Guide](INSTALLATION.md)** - Start here to install FrogUI on your device

⬇️ **[Latest Release](https://github.com/tzubertowski/FrogUI/releases)** - Download the latest version

📖 **[How to Use Guide](HOW_TO_USE.md)** - Complete setup and usage instructions

## Features
- **60+ emulator cores**: Support for Game Boy, GBA, NES, SNES, Genesis, Arcade, and [many more systems](HOW_TO_USE.md#complete-supported-systems-list)
- **Ease of use, no additional scripts required, just drag and drop**: Simple installation and ROM management
- **Hotkeys for Save State, Load and state index change**: Quick access to save states via hotkeys
- **Thumbnails**: Display game preview images in RGB565 format
- **Multiple themes**: Choose from various color schemes to customize your experience
- **Screenshots**: you can now take screenshots both in games and in the menu

## How It Works

### Directory Navigation
- When you start FrogUI, it shows only the folders in `/mnt/sda1/ROMS`
- Use **D-Pad Up/Down** to select a folder
- Press **A** to enter a folder
- Inside a folder, you'll see both subdirectories and game files
- Press **B** to go back to the parent directory
- Press **Select** to access settings:
  - **Main menu (folders)** + Select = Multicore/FrogUI settings
  - **Inside folder** + Select = Core settings for that system

### Launching Games
- Select a game file and press **A** to launch it directly
- FrogUI automatically determines which core to use based on the folder name
- The game boots immediately with the appropriate emulator

## SF3000 Architecture

How the whole stack fits together on SF3000:

```
[boot] icube script (/mnt/sdcard/cubegm/icube)
         │
         └─► picoarch frogui_libretro.so    ← FrogUI runs AS a libretro core
                  │
                  │  user selects ROM
                  │
                  └─► fork()
                         │
                    [parent]          [child]
                    waitpid()         picoarch <game_core.so> <rom>
                    (blocks)               │
                       │             game plays
                       │             user exits
                       │                  │
                    resumes ◄─── child exits
                    FrogUI menu
```

### Why fork+exec?

picoarch holds `/dev/dis` (SF3000 display driver) open. A direct `exec()` would
try to reinit the display on an already-open fd and get a black screen.
`fork()` lets the parent keep `/dev/dis` alive while the child inherits it.
`RETRO_ENVIRONMENT_SHUTDOWN` is silently ignored by picoarch on SF3000, so
`fork+waitpid` is the only clean way to launch a game and return to the menu.

### Input

SF3000 button input comes from `cubevol` - a daemon that writes a bitmask to
shared memory at `/tmp/joy_key`. FrogUI reads it directly via `shmget/shmat`
because picoarch does not route `input_state_cb` to libretro cores on this device.

### sf3000_treefrogui

Separate repo that builds ~57 libretro emulator cores as MIPS32r2 Linux `.so`
files using the SF3000 cross-toolchain. These are the actual emulators picoarch
loads when a game is launched. See
[sf3000_treefrogui/cores.md](https://github.com/tzubertowski/sf3000_treefrogui/blob/master/cores.md)
for the full folder→core mapping table.

### File layout on SD card

```
/mnt/sdcard/
├── cubegm/
│   ├── icube                  ← boot loop (starts cubevol, runs picoarch+frogui)
│   ├── picoarch               ← libretro frontend binary
│   ├── cores/
│   │   ├── frogui_libretro.so ← this launcher
│   │   ├── gpsp_libretro.so   ← GBA emulator (MIPS dynarec)
│   │   └── ... (~57 cores)
│   └── lib/                   ← shared libs for picoarch
├── frogui/
│   └── settings.txt           ← theme + font config
├── FC/                        ← NES ROMs  → fceumm
├── SFC/                       ← SNES ROMs → snes9x2005+
├── GBA/                       ← GBA ROMs  → gpsp
└── ...                        ← other systems
```

## For Developers

🔧 **[Development Guide](DEVELOPMENT.md)** - Building from source, technical details, and contribution guidelines

## License

FrogUI is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). See [LICENSE](LICENSE) for full details.

**Non-Commercial Use Only** - You may not sell FrogUI or bundle it with devices for sale without explicit permission. For commercial licensing inquiries, contact the project maintainers.

## Credits

- Inspired by MinUI's clean interface design
- Built on the SF2000/GB300 multicore framework
- Uses the custom SF2000 filesystem implementation
