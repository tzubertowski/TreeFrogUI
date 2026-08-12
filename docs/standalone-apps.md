# Standalone apps in TreeFrogUI

Most "systems" in TreeFrogUI are **libretro cores** (`.so`) run inside picoarch.
A few entries are **standalone binaries** run directly instead - pcsx4all (PS1)
and pico286 (DOS/PC). This doc explains how that path works and how to add a new
standalone app.

## Why standalone

A standalone app is a normal Linux executable in `cubegm/` that owns the
framebuffer, input and audio itself. Use it when an app isn't a libretro core,
or when a purpose-built binary beats the libretro build (pcsx4all vs
pcsx_rearmed on PS1).

Current standalone apps:

| Folder(s)        | Binary             | What it is                         |
|------------------|--------------------|------------------------------------|
| `ps1` `psx` `PS` | `cubegm/pcsx4all`  | PlayStation (preferred over pcsx_rearmed `.so`) |
| `pico286`        | `cubegm/pico286`   | DOS / PC (8086-286), boots FreeDOS |
| `lgpt`           | `cubegm/lgpt`      | LittleGPTracker (music tracker)    |
| `rockbox`        | `cubegm/rockbox.sh`| Rockbox music player               |
| `Ebook`          | `cubegm/ebook`     | Ebook/document reader (MuPDF - EPUB/MOBI/PDF) - [guide](cores/ebook.md) |
| `videos`         | `cubegm/video_player` | Hardware-decoded MP4/MKV/AVI/MOV video player |
| `images`         | `cubegm/image_viewer` | Native hardware-decoded JPG/PNG/BMP/GIF/WebP/TIFF image viewer |

## The launch contract

Everything hinges on one file: `/tmp/frogui_launch.txt`, written by FrogUI when
the user picks a game, then read by picoarch after FrogUI shuts down.

**libretro core launch** - 2 lines:

```
<core_path>
<rom_path>
```

**standalone launch** - 3 lines, first line is the literal word `standalone`:

```
standalone
<binary_path>
<rom_path>
```

## Who does what

```
icube  (loop)                FrogUI core               picoarch
  │                             │                          │
  └─ picoarch frogui ───────────┤                          │
                                │ user picks game          │
                                │ write frogui_launch.txt  │
                                │ RETRO_ENVIRONMENT_SHUTDOWN
                                ▼                          │
                          (frogui exits) ─────────────────►│ reads launch file
                                                           │ line1 == "standalone"?
                                                           │   yes → execl(bin, bin, rom)
                                                           │   no  → execl(picoarch, core, rom)
                                                           ▼
                                                     standalone binary runs
                                                     (exits → back to icube loop → frogui)
```

- **icube** (`sdcard/cubegm/icube`) only ever loops `picoarch frogui`. It does
  **not** parse the launch file and needs **no** change for standalone apps.
- **FrogUI** (`frogui_libretro.c`) decides core-vs-standalone and writes the file.
- **picoarch** (`main.c`, ~line 1023-1069) reads the file on quit and `execl`s
  the next process. Standalone path:
  `execl(bin_path, bin_path, rom_path, NULL)` - replaces picoarch with the
  binary. When the binary exits, control returns to the icube loop, which
  relaunches FrogUI.

picoarch's standalone dispatch is **generic** - it execs whatever binary the
launch file names. So adding a new standalone app is purely a FrogUI + binary
job; picoarch and icube are untouched.

## How to add a new standalone app

All edits are in `FrogUI/frogui_libretro.c` (branch `r36sx`), plus dropping the
built binary in staging.

1. **Define the binary path** (near the other `*_BIN` defines):

   ```c
   #define LGPT_BIN  SDCARD_BASE "/cubegm/lgpt"
   ```

2. **Map the ROM folder.** Either add a `console_mappings[]` row pointing at the
   binary (like `{"pico286", PICO286_BIN}`), or add a folder predicate when the
   binary should override a libretro fallback (like `is_ps1_folder`):

   ```c
   static bool is_lgpt_folder(const char *folder) {
       return folder && strcasecmp(folder, "lgpt") == 0;
   }
   ```

3. **Mark it standalone** so favorites/recent relaunch it correctly:

   ```c
   static bool is_standalone_bin(const char *name) {
       return name && (strcmp(name, PCSX4ALL_BIN) == 0 ||
                       strcmp(name, PICO286_BIN)  == 0 ||
                       strcmp(name, LGPT_BIN)     == 0);
   }
   ```

4. **Route the launch.** There are **three** dispatch sites - update all three or
   the app only launches from some entry points:
   - main A-button handler (browser)
   - favorites / recent-games handler
   - `search_launch`

   Each looks like:

   ```c
   if (is_ps1_folder(folder) && access(PCSX4ALL_BIN, F_OK) == 0)
       request_standalone_launch(PCSX4ALL_BIN, path);
   else if (is_pico286_folder(folder) && access(PICO286_BIN, F_OK) == 0)
       request_standalone_launch(PICO286_BIN, path);
   else if (is_lgpt_folder(folder) && access(LGPT_BIN, F_OK) == 0)   /* new */
       request_standalone_launch(LGPT_BIN, path);
   else
       request_game_launch(core, path);
   ```

5. **Drop the binary** in `sdcard/cubegm/<name>` (and any config/BIOS dirs it
   needs; PCSX4ALL uses `cubegm/cores/.pcsx4all/`, while
   `cubegm/.pcsx4all/` remains supported for old cards). Rebuild `release/`; a full
   `deploy.sh <device>` copies standalone binaries included by
   `build_release.sh`. For quick iteration, use a named payload when available,
   such as `deploy.sh r36sx pcsx4all`.

6. Rebuild FrogUI (`frogui/make -f Makefile.sf3000 frogui_libretro.so`), deploy.

## What a standalone binary must do itself

picoarch hands the binary one argv: the ROM/project path. The binary owns:

- **Display** - use the hardware display driver, the firmware media plane (as
  the video/image viewers do), or the sysroot's SDL 1.2 (`libSDL-1.2`). Do not
  assume `/dev/fb0` reports the panel's logical geometry on these devices.
- **Input** - the gamepad. picoarch/FrogUI read cubevol's `/tmp/joy_key` shared
  memory; an SDL app can instead use SDL's joystick/keyboard. `hcprojector`
  (stock evdev owner) is not running. See `stock_r36sx.md`.
- **Audio** - ALSA (`libasound`) directly, or SDL_audio.
- **Return cleanly** - exit when the user quits so the icube loop returns to
  FrogUI.

## Video player

Drop ordinary video files into `roms/videos/`; no conversion step is required.
The player uses the stock firmware's `libffplayer` hardware decoder and accepts
MP4, MKV, AVI, MOV/M4V, MPEG/MPG, TS and WebM containers. Actual codec support
is determined by the firmware decoder.

Its MinUI-style controls are drawn as a transparent overlay and inherit the
active TreeFrogUI theme colors. A/Start pauses, Left/Right seeks 10 seconds,
L/R seeks 60 seconds, and B/Select returns to TreeFrogUI.

## Image viewer

Drop JPG/JPEG, PNG, BMP, GIF, TGA, ICO, WebP or TIFF images into
`roms/images/`. The viewer passes the files directly to `libffplayer`'s native
picture decoder and hardware video plane; no conversion or bundled software
image codec is used.

Left/Right or L1/R1 browses adjacent images, A switches between Fit and Fill,
X rotates clockwise, Y toggles the themed controls, and B/Select returns to
TreeFrogUI.
