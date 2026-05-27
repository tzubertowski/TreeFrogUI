# FrogUI Development Guidelines

## Project Overview

FrogUI is a libretro-based file browser core for SF2000/GB300 handheld devices. It provides a MinUI-style interface for navigating ROM collections and launching games.

## Key Features

- MinUI-inspired design with clean typography (ZenMaru Gothic font)
- Recent games tracking and management
- Settings system with persistent configuration
- RGB565 thumbnail support for game previews
- Text scrolling for long filenames
- 7-item menu display with proper spacing

## Development Guidelines

### Build System
- Use `make platform=sf2000` for single builds
- Main build script: `./buildcoresworking.sh` (from project root)
- Clean builds: `./cleancoresworking.sh && ./buildcoresworking.sh`

### Code Style
- Follow existing code conventions and patterns
- Use descriptive variable names
- Add logging with `xlog()` for debugging
- Prefer static buffers over dynamic allocation on SF2000

### Thumbnail System
- Format: Raw RGB565 files (.rgb565 extension)
- Location: `.res` subdirectories alongside ROMs
- Supported dimensions: 64x64, 128x128, 160x160, 200x200, 250x200, 200x250
- Conversion: Use `convert_thumbnails_simple.bat` (Windows) or `convert_thumbnails_simple.sh` (Linux/Mac)
- Requirements: Python 3 with Pillow (PIL) library

### Git Commit Guidelines
- All commit messages must be single line only
- Never mention Claude, AI assistance, or automated generation in commits
- Use present tense, imperative mood (e.g., "Add feature", "Fix bug")
- Keep messages concise and descriptive
- Author: Tomasz Zubertowski <tzubertowski@gmail.com>

### Testing and Debugging
- Test on actual SF2000 hardware when possible
- Debug logs written to `/app/log.txt` during development
- Use `tail -f /app/log.txt` to monitor real-time FrogUI logging
- Check LOG.TXT on device for runtime debugging information
- Verify memory usage (avoid malloc/free in critical paths)
- Test with various ROM collections and filename lengths