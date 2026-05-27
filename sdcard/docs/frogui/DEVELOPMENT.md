# FrogUI Development Guide

This guide covers building, compiling, and developing FrogUI for SF2000/GB300 handhelds.

---

## Table of Contents
- [Building from Source](#building-from-source)
- [Technical Details](#technical-details)
- [Development Guidelines](#development-guidelines)
- [Directory Structure](#directory-structure)
- [Debugging](#debugging)

---

## Building from Source

### Prerequisites
- SF2000/GB300 multicore toolchain
- Make
- GCC for ARM (cross-compilation)

### Build Commands

```bash
# From the multicore root directory
make CONSOLE=frogos CORE=cores/FrogOS
```

Or use the build script from the project root:

```bash
# Single build
./buildcoresworking.sh

# Clean build
./cleancoresworking.sh && ./buildcoresworking.sh
```

### Build Outputs

This will create:
- `cores/FrogOS/_libretro_sf2000.a` - The core library
- `core_87000000` - The loadable core binary
- `sdcard/cores/frogos/core_87000000` - Installed core

---

## Technical Details

### Screen Resolution
- 320x240 pixels
- RGB565 color format

### Input Handling
- Supports RETRO_DEVICE_JOYPAD on port 0
- Button mapping:
  - Up/Down: Navigate menu
  - L/R: Jump by 7 entries
  - A: Select/Enter
  - B: Back
  - Select: Settings menu
  - X: Theme settings
  - Y: Recent games

### File System
- Uses custom `dirent.h` implementation for SF2000
- Scans `/mnt/sda1/ROMS` for directories and files
- No limit on entries per directory (dynamic allocation)
- Supports hidden folders (starting with `.` or named `save`)

### Core Integration
- No ROM loading required (supports `RETRO_ENVIRONMENT_SET_SUPPORT_NO_GAME`)
- Runs at 60 FPS
- No audio output
- Integrates with multicore save state system

### Typography
- Font: ZenMaru Gothic (embedded TrueType)
- Font size: 20px
- Supports text scrolling for long filenames

### Thumbnail System
- Format: Raw RGB565 files (.rgb565 extension)
- Location: `.res` subdirectories alongside ROMs
- Supported dimensions: 64x64, 128x128, 160x160, 200x200, 250x200, 200x250

---

## Development Guidelines

### Code Style
- Follow existing code conventions and patterns
- Use descriptive variable names
- Add logging with `xlog()` for debugging
- Prefer static buffers over dynamic allocation on SF2000

### Git Commit Guidelines
- All commit messages must be single line only
- Never mention Claude, AI assistance, or automated generation
- Use present tense, imperative mood (e.g., "Add feature", "Fix bug")
- Keep messages concise and descriptive

### Testing
- Test on actual SF2000/GB300 hardware when possible
- Verify memory usage (avoid malloc/free in critical paths)
- Test with various ROM collections and filename lengths
- Check navigation edge cases (empty folders, long names, etc.)

---

## Directory Structure

### On Device
```
/mnt/sda1/
├── ROMS/
│   ├── gba/          <- FrogUI shows this folder
│   │   ├── game.gba
│   │   └── .res/
│   │       └── game.rgb565
│   ├── nes/
│   ├── snes/
│   └── ...
├── cores/
│   └── frogos/
│       └── core_87000000
├── app/
│   ├── log.txt       <- Debug logs
│   └── game_history.txt  <- Recent games
└── frogos_boot.txt   <- Created when launching a game
```

### Source Structure
```
FrogUI/
├── frogos.c          <- Main browser logic
├── theme.c           <- Theme definitions
├── settings.c        <- Settings management
├── font/             <- Font resources
├── Makefile          <- Build configuration
└── README.md
```

---

## Debugging

### Debug Logs
On the device, check `LOG.TXT` on the SD card root for runtime debugging information.

### Common Issues

**Build fails:**
- Ensure multicore toolchain is properly installed
- Check that you're building from the correct directory
- Verify all dependencies are available

**Core doesn't load:**
- Check that the core file is at `sd:/cores/frogos/core_87000000`
- Verify multicore is properly installed
- Check device firmware version (GB300 requires v2)

**Navigation issues:**
- Check log files for filesystem errors
- Verify directory permissions
- Test with simpler directory structures first

### Adding Features

When adding new features:
1. Follow existing patterns in the codebase
2. Add debug logging for new functionality
3. Test thoroughly on hardware
4. Update documentation in README.md
5. Consider memory constraints of the device

---

## Contributing

Contributions are welcome! Please:
1. Follow the development guidelines above
2. Test changes on actual hardware when possible
3. Write clear, single-line commit messages
4. Document new features in appropriate README sections

---

## License

See [LICENSE](LICENSE) for licensing information.

FrogUI is licensed under CC BY-NC-SA 4.0. For commercial licensing inquiries, contact the project maintainers.
