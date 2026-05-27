# FrogUI - How to Use

FrogUI is a modern file browser interface for the SF2000/GB300 that provides access to multiple emulator cores with thumbnails, recent games, and customizable themes.

## Basic Navigation

- **D-Pad**: Navigate through files and folders
- **A Button**: Select/launch items, confirm in menus
- **B Button**: Go back, cancel in menus  
- **SELECT**: Access per-core settings (in console folders)
- **START**: Access main settings
- **L/R Buttons**: Navigate between sections (Recent, Tools, etc.)

## Adding ROMs

1. **Create Console Folders**: Place ROMs in `/ROMS/[console]/` folders on your SD card. FrogUI automatically maps folder names to the correct emulator core.

2. **Console Mapping**: The folder name determines which core is used. See the complete list below.

### Complete Supported Systems List

| Folder | System | Core | File Extensions |
|--------|--------|------|-----------------|
| **Nintendo Handhelds** ||||
| `gb` | Game Boy / Game Boy Color | Gambatte | `.gb`, `.gbc` |
| `gbb` | Game Boy (alt) | TGBDual | `.gb`, `.gbc` |
| `gbgb` | Game Boy (alt) | Gearboy | `.gb`, `.gbc` |
| `dblcherrygb` | Game Boy (alt) | DoubleCherryGB | `.gb`, `.gbc` |
| `gba` | Game Boy Advance | gpSP | `.gba` |
| `gbaf` | Game Boy Advance (safe) | gpSP | `.gba` |
| `gbaff` | Game Boy Advance (fast) | gpSP | `.gba` |
| `gbav` | Game Boy Advance (alt) | VBA-Next | `.gba` |
| `mgba` | Game Boy Advance (alt) | mGBA | `.gba` |
| `pokem` | Pokemon Mini | PokeMini | `.min` |
| `vb` | Virtual Boy | Beetle-VB | `.vb`, `.vboy` |
| **Nintendo Consoles** ||||
| `nes` | NES / Famicom | FCEUmm | `.nes`, `.fds` |
| `nesq` | NES (alt) | QuickNES | `.nes` |
| `nest` | NES (alt) | Nestopia | `.nes`, `.fds` |
| `snes` | Super Nintendo | Snes9x 2005 | `.sfc`, `.smc` |
| `snes02` | Super Nintendo (alt) | Snes9x 2002 | `.sfc`, `.smc` |
| **Sega Systems** ||||
| `sega` | Mega Drive / Genesis | PicoDrive | `.md`, `.gen`, `.smd` |
| `gpgx` | Mega Drive (alt) | Genesis-Plus-GX | `.md`, `.gen` |
| `gg` | Game Gear / Master System | Gearsystem | `.gg`, `.sms` |
| **Atari Systems** ||||
| `a26` | Atari 2600 | Stella 2014 | `.a26`, `.bin` |
| `a5200` | Atari 5200 | a5200 | `.a52`, `.bin` |
| `a78` | Atari 7800 | ProSystem | `.a78`, `.bin` |
| `a800` | Atari 800 | Atari800lib | `.atr`, `.xex` |
| `lnx` | Atari Lynx | Handy | `.lnx` |
| `lnxb` | Atari Lynx (alt) | Beetle-Lynx | `.lnx` |
| **NEC Systems** ||||
| `pce` | PC Engine / TurboGrafx-16 | Beetle-PCE-Fast | `.pce`, `.cue` |
| `pcesgx` | PC Engine SuperGrafx | Beetle-SuperGrafx | `.pce`, `.sgx` |
| `pcfx` | PC-FX | Beetle-PCFX | `.cue`, `.ccd` |
| **SNK Systems** ||||
| `ngpc` | Neo Geo Pocket Color | RACE | `.ngp`, `.ngc` |
| `geolith` | Neo Geo | Geolith | `.zip` |
| **Other Handhelds** ||||
| `wswan` | WonderSwan | Beetle-WonderSwan | `.ws`, `.wsc` |
| `wsv` | Watara Supervision | Potator | `.sv` |
| `gw` | Game & Watch | libretro-gw | `.mgw` |
| `arduboy` | Arduboy | Arduous | `.hex` |
| **Home Computers** ||||
| `amstrad` | Amstrad CPC | CrocoDS | `.dsk`, `.sna` |
| `amstradb` | Amstrad CPC (alt) | Cap32 | `.dsk`, `.sna` |
| `c64` | Commodore 64 | VICE x64 | `.d64`, `.t64`, `.prg` |
| `c64sc` | Commodore 64 (cycle) | VICE x64sc | `.d64`, `.t64`, `.prg` |
| `vic20` | Commodore VIC-20 | VICE xvic | `.d64`, `.prg` |
| `zx81` | Sinclair ZX81 | 81 | `.p`, `.81` |
| `spec` | ZX Spectrum | Fuse | `.tzx`, `.tap`, `.z80` |
| `msx` | MSX | blueMSX | `.rom`, `.dsk` |
| `thom` | Thomson MO/TO | Theodore | `.fd`, `.k7` |
| `pc8800` | NEC PC-8800 | Quasi88 | `.d88` |
| `xmil` | Sharp X1 | X Millennium | `.2d`, `.2hd` |
| **Arcade & MAME** ||||
| `m2k` | Arcade (MAME 2000) | MAME 2000 | `.zip` |
| **Other Consoles** ||||
| `col` | ColecoVision | Gearcoleco | `.col` |
| `int` | Intellivision | FreeIntv | `.int`, `.bin` |
| `o2em` | Odyssey 2 / Videopac | O2EM | `.bin` |
| `fcf` | Fairchild Channel F | FreeChaF | `.bin`, `.chf` |
| `vec` | Vectrex | vecx | `.vec`, `.bin` |
| **Fantasy Consoles** ||||
| `chip8` | CHIP-8 | JAXE | `.ch8` |
| `retro8` | PICO-8 | Retro8 | `.p8`, `.png` |
| `fake08` | PICO-8 (alt) | Fake-08 | `.p8`, `.png` |
| `lowres-nx` | LowRes NX | LowRes NX | `.nx` |
| `vapor` | VaporSpec | VaporSpec | `.vaporbin` |
| **Ports & Games** ||||
| `prboom` | Doom | PrBoom | `.wad` |
| `quake` | Quake | TyrQuake | `.pak` |
| `wolf3d` | Wolfenstein 3D | ECWolf | `.wl6` |
| `outrun` | OutRun | Cannonball | game files |
| `flashback` | Flashback | REminiscence | game files |
| `xrick` | Rick Dangerous | XRick | game files |
| `cavestory` | Cave Story | NXEngine | game files |
| `jnb` | Jump'n'Bump | Jump'n'Bump | game files |
| `gong` | Pong | Gong | - |
| **Media Players** ||||
| `mp3` | MP3 Audio Player | [FroggyMP3](https://github.com/tzubertowski/froggyMP3) ([source](https://github.com/GrGadam/froggyMP3)) | `.mp3` |
| `videos` | Video Player | [SF2000-Video-Player](https://github.com/angree/sf2000-video-player/releases/tag/v0.75-sf2000) | `.avi`, `.mjpeg` |
| `gme` | Game Music | GME | `.nsf`, `.spc`, `.vgm`, `.gbs` |
| `cdg` | CD+G Karaoke | PocketCDG | `.cdg` |

### Quick Setup Examples

```
/ROMS/
├── gb/                 ← Game Boy games (.gb, .gbc)
├── gba/                ← GBA games (.gba)
├── nes/                ← NES games (.nes)
├── snes/               ← SNES games (.sfc, .smc)
├── sega/               ← Genesis/Mega Drive (.md, .gen)
├── pce/                ← PC Engine (.pce)
├── mp3/                ← MP3 music files (.mp3)
├── videos/             ← Video files (.avi, .mjpeg)
└── m2k/                ← Arcade ROMs (.zip)
```

## Playing Videos

FrogUI includes a video player core that can play MJPEG videos on your device.

### Video Requirements

- **Format**: MJPEG in AVI container (`.avi`) or raw MJPEG (`.mjpeg`)
- **Resolution**: 320×240 recommended for best performance
- **Audio**: MP3 audio track supported

### Converting Videos

Videos must be converted to MJPEG format before they can be played. Use FFmpeg to convert your videos:

```bash
ffmpeg -i input.mp4 -vf "scale=320:240" -c:v mjpeg -q:v 5 -c:a mp3 -b:a 128k output.avi
```

For detailed conversion instructions and options, see the [SF2000 Video Player conversion guide](https://github.com/angree/sf2000-video-player?tab=readme-ov-file#converting-videos).

### Adding Videos

Place converted video files in the `videos` folder:
```
/ROMS/videos/my_video.avi
/ROMS/videos/another_video.mjpeg
```

## Adding Thumbnails

Thumbnails enhance your gaming experience by showing preview images of your games.

### Thumbnail Requirements

- **Format**: RGB565 raw format (no headers)
- **Supported Resolutions**: 
  - 64×64 pixels (8,192 bytes)
  - 128×128 pixels (32,768 bytes) 
  - 160×160 pixels (51,200 bytes) - **Recommended**
  - 200×200 pixels (80,000 bytes)
  - 250×200 pixels (100,000 bytes)

### Thumbnail Placement

Place thumbnail files alongside your ROMs with `.rgb565` extension:
```
/ROMS/nes/Super Mario Bros.nes
/ROMS/nes/Super Mario Bros.rgb565

/ROMS/gb/Tetris.gb
/ROMS/gb/Tetris.rgb565
```

### Converting Thumbnails

FrogUI includes automatic conversion scripts in the `scripts/` folder:

**Windows Users:**
```batch
scripts\convert_thumbnails_simple.bat D:\roms
```

**Linux/Mac Users:**
```bash
./scripts/convert_thumbnails_simple.sh /path/to/roms
```

The scripts will:
1. Find all PNG images in `.res` subdirectories
2. Automatically resize them (200×200 for square images, 250×200 for wide)
3. Convert to RGB565 raw format
4. Save with `.rgb565` extension

**Requirements:**
- Python 3 with Pillow (PIL) library
- PNG source images in `.res` folders alongside your ROMs

**Manual Conversion:**
If you prefer manual conversion:
1. Resize image to 160×160 pixels (or 200×200/250×200)
2. Convert to RGB565 raw format (5 bits R, 6 bits G, 5 bits B)
3. Save as raw binary file with `.rgb565` extension

## Settings and Configuration

### Main Settings (START Button)

Access global multicore settings:
- **Tearing Fix**: Adjust display sync
- **RGB Clock**: Display timing settings
- **Screen Scaling**: Choose scaling modes
- **Theme**: Select from 19 beautiful themes
- **Show FPS**: Toggle FPS display

### Per-Core Settings (SELECT Button)

When in a console folder, press SELECT to access core-specific settings:
- Each core has its own configuration file
- Settings are saved to `/configs/[CoreName]/[CoreName].opt`
- Examples: `/configs/Gambatte/Gambatte.opt`, `/configs/QuickNES/QuickNES.opt`

### Available Themes

Choose from 19 carefully crafted themes:

**Modern Themes:**
- MinUI Style (classic black/white)
- Emerald, Orange, Golden, Rose
- Purple, Prosty's Pink, Green, Red

**Retro Themes:**
- Commodore 64 (blue/purple classic)
- Game Boy (classic green monochrome)
- NES (gray/red Nintendo colors)
- Famicom (red/yellow Japanese colors)
- SNES (purple/gray Super Nintendo)

**CRT/Terminal Themes:**
- Amber CRT (orange on black)
- Green CRT (green on black) 
- DOS (blue background, white text)
- Matrix (green digital rain style)

## Tools and Utilities

### Tools Menu (L/R to navigate)

Access various system tools:

**Recent Games**: Quick access to recently played games
- Automatically tracks your last 10 games
- Shows game name and console
- Press A to launch directly

**Tools**: System utilities and core management
- Access to various system tools
- Core-specific utilities

**Utils**: JavaScript utilities (js2000 core)
- Run `.js` files from `/ROMS/js2000/` folder  
- JavaScript utilities for system management
- Configuration scripts and tools

### Folder Navigation Shortcuts

- **Boundary Delay**: When scrolling to the beginning or end of long file lists, FrogUI pauses briefly to prevent accidental wrap-around
- **Alphabetical Sorting**: All folders and files are sorted alphabetically
- **Folder Filtering**: System folders (frogui, js2000) are hidden from ROM lists

## Tips and Tricks

1. **Organize by Console**: Keep ROMs organized in console-specific folders for best experience

2. **Use Thumbnails**: 160×160 RGB565 thumbnails provide the best quality-to-size ratio

3. **Recent Games**: Your most-played games appear in the Recent section for quick access

4. **Theme Switching**: Experiment with different themes to find your preferred style

5. **Per-Core Settings**: Each emulator core can have different settings optimized for that system

6. **Utils Section**: Explore the JavaScript utilities for advanced system management

## File Structure Overview

```
/ROMS/
├── gb/           - Game Boy ROMs
├── gba/          - Game Boy Advance ROMs  
├── nes/          - NES ROMs
├── snes/         - SNES ROMs
├── js2000/       - JavaScript utilities
└── [console]/    - Other console ROMs

/configs/
├── multicore.opt     - Main FrogUI settings
├── Gambatte/         - Game Boy core settings
├── QuickNES/         - NES core settings  
└── [CoreName]/       - Other core settings

/bios/
└── bisrv.asd         - FrogUI firmware
```

## Troubleshooting

**Problem**: ROM doesn't launch
- **Solution**: Check ROM is in correct console folder with proper file extension

**Problem**: No thumbnail showing  
- **Solution**: Ensure thumbnail is RGB565 format and matches ROM filename exactly

**Problem**: Settings not saving
- **Solution**: Make sure SD card is not write-protected

**Problem**: Core not working
- **Solution**: Check if core is included in your FrogUI build (see buildcoresworking.sh)

Enjoy your enhanced gaming experience with FrogUI!