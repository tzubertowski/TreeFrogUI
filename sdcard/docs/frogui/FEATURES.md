# FrogUI - Current Features Documentation

## Overview
FrogUI is a MinUI-inspired libretro file browser core for SF2000/GB300 handheld devices. It provides an elegant interface for navigating ROM collections and launching games through various emulator cores.

---

## 1. UI/MENU SYSTEM

### Display Layout
- **Screen Resolution**: 320x240 pixels (RGB565 format)
- **Menu Style**: MinUI-inspired clean typography interface
- **Header Display**: Shows current folder name or branded titles (e.g., "FROGUI: SYSTEMS")
- **7-Item Menu Display**: Shows 7 visible menu items at a time with automatic scrolling
- **Font**: Custom bitmap font implementation with configurable sizes
  - Character Width: 18px
  - Character Height: 16px
  - Character Spacing: 13px

### Navigation Features
- **Up/Down Navigation**: Move between menu items with immediate response
- **Boundary Wrapping**: 30-frame delay before wrapping from top to bottom (or vice versa) to prevent accidental wrapping
- **Quick Jump Navigation**:
  - L Button: Jump up 10 entries
  - R Button: Jump down 10 entries
- **Scroll Offset Management**: Automatically keeps selected item visible in viewport
- **Text Scrolling**: Long filenames scroll horizontally when selected
  - Delay before scroll: 60 frames (1 second at 60fps)
  - Scroll speed: 8 frames per character movement
  - Max display length for selected items: 20 characters
  - Max display length for unselected items: 10 characters (to avoid thumbnail overlap)

### Visual Elements
- **Header Area**: Displays folder/section title at top
- **Legend Area**: Bottom-right corner shows "SEL - SETTINGS" with rounded pill styling
- **Selection Highlight**: Selected items have rounded pillbox styling with contrasting colors
- **Folder Indicators**: Directories shown in distinct color from files
- **Menu Item Rendering**: 
  - Text-based pillbox highlighting for selected items
  - Distinct colors for folders vs. files
  - 24px height per menu item

---

## 2. SETTINGS & CONFIGURATION

### Settings System
- **Config File Format**: `.opt` files with comment-based option definitions
- **Option Parsing**: Reads options from comment lines: `### [option_name] :[current] :[val1|val2|val3]`
- **Value Cycling**: Left/Right buttons cycle through available values
- **Settings Persistence**: Auto-saves to configuration files

### Multicore Settings (`multicore.opt`)
- **Location**: `/mnt/sda1/configs/multicore.opt`
- **Accessible Via**: SELECT button on main menu
- **Features**:
  - Global emulation settings
  - Theme selection (stored as `frogui_theme` setting)
  - Supports unlimited setting options

### Core-Specific Settings
- **Location**: `/mnt/sda1/configs/[core_name]/[core_name].opt`
- **Accessible Via**: SELECT button in console folders
- **Example Cores with Settings**: Gambatte, gpSP, Snes9x, PicoDrive, and others
- **Features**: Each core can have its own configuration options

### Settings Menu UI
- **Layout**: Shows 3 settings options at a time with scrolling
- **Display Format**: 
  - Setting name on one line
  - Current value in pill-shaped button on next line
  - Left/Right arrows indicate change capability: `< current_value >`
- **Input Handling**:
  - Up/Down: Navigate between settings
  - Left/Right: Cycle through values
  - A Button: Save and exit
  - B Button: Save and exit
- **Legend**: "A - SAVE   B - EXIT" displayed at bottom

---

## 3. GAME LAUNCHING & ROM MANAGEMENT

### Directory Structure
- **Main ROM Path**: `/mnt/sda1/ROMS/`
- **Console Folders**: Each console type has its own folder (gb, gba, nes, snes, etc.)
- **Special Folders**: 
  - `frogui/` - Hidden from browser
  - `js2000/` - JavaScript/utility games (accessible via Utils menu)
  - `saves/` - Save files (hidden from browser)

### Console & Core Mappings
FrogUI supports 105+ consoles mapped to their respective cores:
- **Game Boy**: gb → Gambatte, gbb → TGBDual, gbgb → Gearboy, mgba → mGBA
- **Game Boy Advance**: gba → gpSP, gbaf → gpSP, gbaff → gpSP, gbav → VBA-Next, mgba → mGBA
- **NES**: nes → FCEUmm, nesq → QuickNES, nest → Nestopia
- **SNES**: snes → Snes9x2005, snes02 → Snes9x2002
- **Sega**: sega → PicoDrive, gg → Gearsystem, gpgx → Genesis-Plus-GX
- **PC Engine**: pce → Beetle-PCE-Fast, pcesgx → Beetle-SuperGrafx
- **And 80+ more supported systems** (Lynx, WonderSwan, Pokemon Mini, Atari, MSX, etc.)

### Game Launching
- **File Selection**: A button launches selected ROM
- **Game Queuing**: Games are queued before core loading to prevent crashes
- **Core Loading**: Uses SF2000-specific `load_and_run_core()` function
- **Multi-core Support**: Different cores can be active simultaneously depending on system configuration

### File Filtering
- **Root ROMS View**: Shows only folders (console folders)
- **Console Folder View**: Shows all ROM files and subdirectories
- **Auto-sorting**: All entries sorted alphabetically by name
- **Hidden Files**: Files starting with '.' are automatically hidden

---

## 4. RECENT GAMES / FAVORITES FUNCTIONALITY

### Recent Games List
- **Location**: Accessible from main menu as first entry "Recent games"
- **Storage File**: `/mnt/sda1/game_history.txt`
- **Maximum Entries**: 10 most recent games
- **Data Format**: `core_name|game_name|full_path` (with backward compatibility for old format)

### Features
- **Auto-tracking**: Every launched game is automatically added to recent list
- **Move to Top**: Previously played game moves to top when replayed
- **Display Format**: "game_name (core_name)" - shows both game and emulator
- **Persistence**: List saved to disk after each game launch
- **Thumbnail Support**: Recent games display thumbnails (with full path tracking)

### Recent Games Menu
- **Back Option**: ".." entry returns to main ROMS directory
- **Quick Access**: Recent games displayed as read-only list (no modification)
- **Display Name Format**: Game filename + core name for identification
- **Thumbnails**: Full paths tracked for accurate thumbnail lookups

---

## 5. FILE BROWSING CAPABILITIES

### Directory Navigation
- **Browse Structure**: Standard hierarchical folder navigation
- **Parent Directory Entry**: ".." at top of folder to go back one level
- **Current Path Display**: Shows in header area
- **Path Limits**: MAX_PATH_LEN = 512 characters

### File Display
- **Max Entries**: No limit (dynamic allocation)
- **Sorting**: Alphabetical by name (case-sensitive)
- **Directory First**: Directories added to entries, then files
- **Entry Information Stored**:
  - Full path
  - Display name (filename)
  - Directory flag

### Entry Type Indicators
- **Folders**: Displayed in distinct color (configurable by theme)
- **Files**: Regular text color
- **Selection**: Highlighted with pillbox background

### Special Views
- **Recent Games**: Special virtual folder showing recent play history
- **Tools**: Meta menu with shortcuts, credits, and utilities
- **Utils**: List of js2000 utility files
- **Shortcuts**: Info screen showing emulator control shortcuts
- **Credits**: Attribution for FrogUI developers and designers

---

## 6. THUMBNAIL / PREVIEW SYSTEM

### Thumbnail Format
- **File Format**: Raw RGB565 binary files
- **File Extension**: `.rgb565`
- **Color Depth**: 16-bit RGB565 (5 bits red, 6 bits green, 5 bits blue)
- **Location**: `.res` subdirectories alongside ROM files
  - Example: `/mnt/sda1/ROMS/gb/.res/pokemon_red.rgb565`

### Supported Dimensions
- 64x64 pixels
- 128x128 pixels
- 160x160 pixels
- 200x200 pixels
- 250x200 pixels
- 200x250 pixels

### Thumbnail Display
- **Position**: Right side of screen (background layer)
- **Area**: 160px max width, 200px max height
- **Rendering**: On-the-fly scaling using nearest neighbor interpolation
- **Scaling**: Maintains aspect ratio, fills available space
- **Centering**: Vertically centered on screen, aligned to right edge
- **Frame**: Dark gray border with dark gray background fill
- **Black Pixel Transparency**: Black pixels (0x0000) allow background to show through

### Thumbnail Management
- **Cache System**: Static buffer for current selection (no malloc/free)
- **Smart Loading**: Only loads when selection changes
- **Memory Efficient**: Uses static 250x200 buffer (50KB fixed allocation)
- **Fallback**: Works if thumbnail doesn't exist (shows default background)

### Thumbnail Conversion Tools
- **Windows**: `convert_thumbnails_simple.bat`
- **Linux/Mac**: `convert_thumbnails_simple.sh`
- **Requirements**: Python 3 with Pillow (PIL) library
- **Input Format**: PNG images
- **Output**: RGB565 raw files in `.res` directories

---

## 7. THEME SYSTEM

### Available Themes
FrogUI includes 16 built-in themes:

1. **MinUI Style** - Classic black/white interface
2. **Emerald** - Green forest theme
3. **Orange** - Warm orange tones
4. **Golden** - Yellow/gold accent theme
5. **Rose** - Soft pink/brown tones
6. **Purple** - Deep purple vibrant
7. **Prosty's Pink** - Hot pink custom
8. **Green** - Lime green theme
9. **Red** - Bold red theme
10. **Commodore 64** - Retro C64 blue/purple
11. **Game Boy** - Classic GB green/black
12. **NES** - Authentic NES color scheme
13. **Amber CRT** - Monochrome amber monitor
14. **Green CRT** - Monochrome green terminal
15. **DOS** - DOS era blue/yellow
16. **Famicom** - Classic Famicom red/white
17. **SNES** - Super Nintendo colors
(And potentially more)

### Theme Customization
- **Colors Per Theme**:
  - Background color
  - Text color
  - Selection background
  - Selection text color
  - Header color
  - Folder color
  - Legend text color
  - Legend background color
  - Disabled/inactive color
- **Selection Method**: Via Settings menu (frogui_theme option)
- **Persistence**: Theme selection saved to multicore.opt

### Theme Functions
- `theme_init()` - Initialize theme system
- `theme_load_from_settings()` - Load theme by name
- `theme_apply()` - Apply theme by index
- `theme_get_current()` - Get current theme structure
- Color accessor functions for all theme colors

---

## 8. INPUT HANDLING

### Button Mapping
| Button | Function |
|--------|----------|
| **Up** | Move selection up / Wrap to bottom with delay |
| **Down** | Move selection down / Wrap to top with delay |
| **Left** | Cycle setting to previous value (in settings menu) |
| **Right** | Cycle setting to next value (in settings menu) |
| **L** | Jump up 10 entries |
| **R** | Jump down 10 entries |
| **A** | Select item / Save settings |
| **B** | Go back one level / Exit settings |
| **SELECT** | Open settings menu (or core-specific settings in console folders) |

### Input Polling
- **Method**: Libretro input state callbacks
- **State Tracking**: Maintains previous frame input state to detect button release events
- **Release Events**: Most actions trigger on button release (prevents repeated actions)

### Special Input Handling
- **Settings Menu**: When active, settings-specific input handler takes priority
- **Game Queuing**: Input ignored while game is loading (shows "LOADING..." screen)
- **Shortcuts Menu**: Display-only screen (B button returns to tools)
- **Credits Menu**: Display-only screen (B button returns to tools)

---

## 9. SPECIAL FEATURES & UTILITIES

### Tools Menu
Accessible from main menu, provides access to:

#### Shortcuts Screen
- Displays emulator button combinations:
  - SAVE STATE: L + R + X
  - LOAD STATE: L + R + Y
  - NEXT SLOT: L + R + >
  - PREV SLOT: L + R + <
- Read-only display, no interaction

#### Credits Screen
- Attribution sections:
  - **FrogUI Dev & Idea**: Prosty & Desoxyn
  - **Design**: Q_ta
- Styled with section headers and regular text

#### Utils Submenu
- Shows files from `/mnt/sda1/ROMS/js2000/` directory
- Launches js2000 core for utility/JavaScript games
- File launching with automatic extension handling

### Text Scrolling Animation
- **Trigger**: Selected item with long filename (>20 chars)
- **Behavior**:
  - 60-frame initial delay before scrolling
  - Bounces back and forth at ends
  - 8-frame speed for smooth animation

### Menu State Management
- **Entry Count**: Tracks number of items in current directory
- **Selected Index**: Current selection position (0-based)
- **Scroll Offset**: Viewport starting position
- **Boundary Delay**: Prevents accidental wrapping with 30-frame delay

---

## 10. TECHNICAL FEATURES

### Libretro Integration
- **API Version**: RETRO_API_VERSION
- **Content Type**: No-game core (RETRO_ENVIRONMENT_SET_SUPPORT_NO_GAME)
- **Pixel Format**: RGB565 (RETRO_PIXEL_FORMAT_RGB565)
- **FPS**: 60.0
- **Sample Rate**: 44100.0 Hz
- **Aspect Ratio**: 4:3 (320:240)

### Memory Management
- **Static Framebuffer**: 320x240 RGB565 = 153,600 bytes
- **Static Thumbnail Buffer**: 250x200 maximum = 50,000 bytes
- **No Dynamic Allocation in Loops**: All buffers pre-allocated
- **SF2000 Optimization**: Uses static buffers to avoid malloc/free issues on embedded systems

### File I/O
- **Settings File Read/Write**: Preserves comment structure
- **Game History**: Sequential file read/write
- **Thumbnail Loading**: File validation with size checking
- **Safe File Operations**: Temp files + atomic replacement for settings

### Rendering System
- **Double Buffering**: Full framebuffer maintained in memory
- **Layered Rendering**:
  1. Clear screen with background color
  2. Render thumbnail (background layer)
  3. Render menu items (foreground layer)
  4. Render UI elements (header, legend)
- **Color Conversion**: RGB888 to RGB565 conversion support

### Custom Font System
- **Multiple Font Variants**: ChillRound, GamePocket, GamePocket Serif
- **Character Data**: Bitmap data for all printable characters
- **Per-Pixel Control**: Full bitmap control for rendering

### SF2000-Specific Features
- **Core Loading Function**: SF2000 firmware integration at address 0x800016d0
- **Game File Queueing**: Deferred core loading to prevent crashes
- **ROM Path Convention**: `/mnt/sda1/ROMS/` standard location
- **Config Paths**: `/mnt/sda1/configs/` for settings

---

## 11. CONFIGURATION & CUSTOMIZATION

### Directory Paths
```
/mnt/sda1/
  ROMS/
    [console folders]/
      .res/              [thumbnails here]
      [rom files]
    js2000/             [utility games]
    frogui/             [hidden]
    saves/              [hidden]
  configs/
    multicore.opt       [global settings]
    [core_name]/
      [core_name].opt   [core-specific settings]
  game_history.txt      [recent games list]
```

### Editable Configuration Files
- **multicore.opt**: Global settings including theme
- **Core .opt files**: Core-specific emulation settings
- **game_history.txt**: Recent games list (auto-managed)

---

## 12. PERFORMANCE OPTIMIZATIONS

### Directory Scanning
- **Fast Path Detection**: Uses `d_type` field from `dirent` when available
- **Stat Call Avoidance**: Minimizes system calls for directory detection
- **Single Pass**: Collects all entries, then sorts once
- **Filtering**: Skips hidden files and special directories in one pass

### Rendering Optimization
- **Selective Thumbnail Loading**: Only loads thumbnail when selection changes
- **Static Buffer Reuse**: No malloc/free per frame
- **Viewport Culling**: Only renders visible menu items
- **Scaled Rendering**: Thumbnails scaled to fit display area

### Input Handling
- **Edge-Case Delay**: 30-frame delay prevents accidental menu wrapping
- **State Tracking**: Previous input state prevents repeated actions
- **Release Events**: Most inputs trigger on release, not press

---

## Summary of Features

FrogUI provides a complete MinUI-inspired file browser experience with:
- Clean, responsive 320x240 interface
- 7-item menu with automatic scrolling
- 105+ console/core support
- Recent games tracking (10 slots)
- Game thumbnails with RGB565 format
- 16+ built-in themes with customization
- Settings menu for both global and per-core configuration
- Text scrolling for long filenames
- Quick navigation (L/R for 10-item jumps)
- Tools menu with shortcuts, credits, and utilities
- SF2000-optimized code with static buffers
- Theme persistence and selection
- Boundary wrapping protection with delay
- Modular rendering system
- Efficient memory management

