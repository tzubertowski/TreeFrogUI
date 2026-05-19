# TreeFrogUI for SF3000

Complete emulation package for the SF3000 handheld — launcher UI + 57 emulator cores.

---

## What's included

| Component | What it does |
|-----------|-------------|
| **TreeFrogUI** (`frogui_libretro.so`) | ROM browser and launcher, runs inside picoarch |
| **57 emulator cores** | NES, SNES, GBA, Mega Drive, PC Engine, Amiga, Atari ST, and more |
| **build system** | Cross-compile everything from source using the SF3000 toolchain |

See [cores.md](cores.md) for the full folder→core mapping table.

---

## Quick install (pre-built)

1. Download the latest release zip from [Releases](https://github.com/tzubertowski/treefrog-ui/releases)
2. Copy the contents to your SD card:
   ```
   cores/*.so  →  /mnt/sdcard/cubegm/cores/
   icube       →  /mnt/sdcard/cubegm/icube
   ```
3. Make sure `picoarch` is in `/mnt/sdcard/cubegm/picoarch` (from the SF3000 multicore project)
4. Boot the device — TreeFrogUI launches automatically

---

## ROM folder setup

Create folders on the SD card matching these names. TreeFrogUI auto-detects the correct emulator from the folder name.

```
/mnt/sdcard/
├── FC/          ← NES
├── SFC/         ← SNES
├── GBA/         ← Game Boy Advance
├── GB/          ← Game Boy / Color
├── MD/          ← Mega Drive / Genesis
├── SMS/         ← Master System
├── GG/          ← Game Gear
├── pce/         ← PC Engine / TurboGrafx-16
├── a26/         ← Atari 2600
├── Quake/       ← Quake (needs pak0.pak)
├── prboom/      ← Doom (needs WAD file)
├── amiga/       ← Amiga (needs kick.rom BIOS)
├── atari-st/    ← Atari ST (needs TOS ROM)
└── ...
```

Full list: [cores.md](cores.md)

---

## BIOS files required

Some cores need BIOS/firmware files. Place them in the system folder the core expects (check individual core docs), typically alongside the ROMs or in a `bios/` subfolder.

| System | File needed |
|--------|-------------|
| GBA (gpsp) | `gba_bios.bin` (official Nintendo GBA BIOS) |
| Amiga (UAE) | `kick.rom` (Amiga Kickstart ROM) |
| Atari ST (castaway) | TOS ROM image |
| Neo Geo (geolith) | Neo Geo BIOS |
| PC-FX (beetle-pcfx) | `pcfx.rom` |
| PC-88 (quasi88) | NEC PC-88 BIOS files |

---

## Building from source

### Requirements

- SF3000 cross-toolchain at `~/sf3000-work/sf3000toolchain/`
- `git`, `make`, `nproc`

### Steps

```sh
git clone git@github.com:tzubertowski/treefrog-ui.git
cd treefrog-ui

# Clone FrogUI source (submodule)
git submodule update --init frogui

# Clone all emulator core sources
./clone_cores.sh

# Build everything
./build_all.sh

# Results in build/*.so — copy to SD card
cp build/*.so /mnt/sdcard/cubegm/cores/
```

### Build FrogUI only

```sh
cd frogui
make -f Makefile.sf3000 frogui_libretro.so
cp frogui_libretro.so /mnt/sdcard/cubegm/cores/
```

---

## How it works

```
[boot] icube  (/mnt/sdcard/cubegm/icube)
    │
    └─► picoarch frogui_libretro.so    ← TreeFrogUI is a libretro core
              │
              │  user selects ROM
              │
              └─► fork()
                     │
                [parent]            [child]
                waitpid()           picoarch <game_core.so> <rom>
                (blocks)                │
                   │              game runs
                   │              user exits
                   │                  │
                resumes ◄──── child exits
                TreeFrogUI menu
```

**picoarch** handles display (`/dev/dis` + framebuffer), audio (ALSA), and the libretro core lifecycle. TreeFrogUI is just another `.so` loaded by picoarch — it renders the file browser UI and uses `fork+waitpid` to launch games without losing the display connection.

**Input** comes from `cubevol` (SF3000 button daemon) via shared memory at `/tmp/joy_key`. TreeFrogUI reads it directly since picoarch doesn't route input callbacks to cores on this device.

---

## Repository structure

```
treefrog-ui/
├── frogui/          ← FrogUI source (git submodule, sf3000 branch)
├── cores/           ← emulator core sources (populated by clone_cores.sh)
├── build/           ← compiled .so output (gitignored)
├── patches/         ← patches applied to externally-owned core repos at build time
├── build_all.sh     ← build all cores
├── clone_cores.sh   ← clone all core source repos
└── cores.md         ← folder→core mapping reference
```

---

## What's not included / known limitations

| Item | Status |
|------|--------|
| `vecx` (Vectrex) | ❌ needs OpenGL — not available on SF3000 |
| `arduous` (Arduboy) | ❌ needs cmake — not in toolchain |
| `o2em` (Odyssey²) | ❌ not yet cloned |
| `vice` (C64) | commented out — large build, enable manually in build_all.sh |
| `fake-08` (PICO-8) | not yet built |
| picoarch binary | not included — obtain from SF3000 multicore project |

---

## Credits

- **picoarch** — libretro frontend adapted for SF3000
- **FrogUI** — original launcher by tzubertowski, fork of [FrogUI](https://github.com/tzubertowski/FrogUI)
- **angree** — Amiga (UAE4ALL) and Atari ST (castaway) ports for SF-series handhelds
- All libretro core authors
