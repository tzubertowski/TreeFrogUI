# FrogUI Quick Start Guide

## What is FrogUI?

FrogUI is a file browser core for SF2000/GB300 multicore that lets you browse your ROMS folders and launch games directly. It's designed to mimic MinUI's clean interface.

## Quick Setup

### 1. Build the Core
```bash
cd /app
make CONSOLE=menu CORE=cores/FrogOS
```

### 2. The core is automatically installed to:
- `sdcard/cores/menu/core_87000000`

### 3. Launch FrogUI

To launch FrogUI, you need a stub file. The multicore system recognizes files in the format:
```
[corename];[filename].extension
```

For example, create a stub file:
```bash
# In any ROMS subfolder (e.g., /mnt/sda1/ROMS/gba/)
touch "menu;m.gba"
```

When multicore sees this file, it will load the `menu` core.

## How to Use FrogUI

1. **Navigate**: Use D-Pad Up/Down to move through the list
2. **Enter Folders**: Press A to enter a folder
3. **Go Back**: Press B to go to the parent folder
4. **Launch Games**: Select a game file and press A to launch it

### Main Screen (ROMS Root)
- Shows only folders (gba, nes, snes, etc.)
- No files are shown at the root level
- Select a folder and press A to enter it

### Inside a Folder
- Shows subdirectories (if any) at the top
- Shows game files below
- ".." entry goes to parent folder

## Integration with Multicore Boot

### Method 1: Manual Launch
Place the stub file in any ROM folder and select it from the stock firmware's game list.

```

## Understanding the Format

The multicore system expects ROM files in this format:
```
corename;filename.extension
```

Examples:
- `menu;m.gba` - Loads FrogUI core

## File Structure

```
/mnt/sda1/
├── ROMS/
│   ├── gba/
│   │   ├── pokemon.gba
│   ├── menu/
│   │   └── m  <- Stub file to launch FrogUI
│   └── snes/
├── cores/
│   ├── menu/
│   │   └── core_87000000       <- FrogUI core binary
│   ├── gba/
│   └── nes/
```

## Troubleshooting

### FrogUI won't start
- Make sure `core_87000000` exists in `/mnt/sda1/cores/menu/`
- Verify the stub file name matches the pattern `menu;[anything].[ext]`

### No folders show up
- Ensure your ROMS are in `/mnt/sda1/ROMS/`
- Check folder permissions

### Games won't launch
- The parent folder name must match a valid core name
- For example, games in `/mnt/sda1/ROMS/gba/` will try to launch with the `gba` core
- Make sure the target core exists in `/mnt/sda1/cores/[corename]/`

## Controls Reference

| Button | Action |
|--------|--------|
| D-Pad Up | Move selection up |
| D-Pad Down | Move selection down |
| A | Enter folder / Launch game |
| B | Go back to parent folder |

## Building from Source

```bash
# Clean build
cd /app
make clean CONSOLE=menu CORE=cores/FrogOS

# Build
make CONSOLE=menu CORE=cores/FrogOS

# Or use the build script (add to buildcoresworking.sh)
echo "-- FrogUI make (File Browser) --"
make clean CONSOLE=menu CORE=cores/FrogOS
make CONSOLE=menu CORE=cores/FrogOS
```

## Next Steps

- Try launching FrogUI using the stub file
- Navigate your ROMS folders
- Launch a game and verify it works
- Consider integrating FrogUI as the default launcher for your multicore setup

Enjoy your new file browser! 🐸
