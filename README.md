![TreeFrogUI Logo](logo-readme.png)

# TreeFrogUI for SF3000

A free, custom game-menu (frontend) for the SF3000 and R36SX handhelds. It replaces the stock menu and runs hundreds of retro systems.

![UI Preview on SF3000 Console](console.jpg)

> # ☕ Consider donating to extend device support: [ko-fi.com/proszty](https://ko-fi.com/proszty)
> TreeFrogUI is free and made by one person. Every device I support, I bought with my own money. Donations are what let me buy the next handheld and add support for it (R36SX v2.7, SF3000 V3, SF3500, SF3100, GB350, HDMI clones, and more).
>
> If TreeFrogUI gave you some fun, please consider chipping in. It genuinely decides whether the next port happens.
>
> ### 👉 [**Donate here: ko-fi.com/proszty**](https://ko-fi.com/proszty) 🙏

### New here? Start with these
- 📦 **[How to install it](install.md)** - start here, step by step
- 🕹️ **[How to add games + which folder](#rom-folder-setup)** - where to put your ROMs
- 🎨 **[How to customise it](theme.md)** - themes, fonts, game art / box art / thumbnails, backgrounds
- ⬇️ **[Download the latest version](https://github.com/tzubertowski/treefrog-ui/releases)**
- 💬 **[Report a bug / give feedback](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

> **Words you'll see (plain English):**
> - **SD card** = the little memory card your games live on.
> - **"root of the SD card"** = the **top level** of the card, **not inside any folder**. When you open the card on your PC and see folders like `cubegm`, `roms`, `frogui`, that first screen **is** the root.
> - **folder** = a directory you make on the card (e.g. `roms/GBA`). The folder **name** decides which system it runs.
> - **ROM** = a game file.
> - **BIOS** = an extra system file some consoles need to run (you supply it; see [BIOS files](#bios-files-required)).
> - **keep zips zipped** = for arcade games, do **not** unzip the `.zip`. Drop it in as-is.

---

## What's included

| Component | What it does |
|-----------|-------------|
| **TreeFrogUI** (`frogui_libretro.so`) | ROM browser and launcher, runs inside picoarch |
| **57 emulator cores** | NES, SNES, GBA, Mega Drive, PC Engine, Amiga, Atari ST, and more |
| **build system** | Cross-compile everything from source using the SF3000 toolchain |

See [cores.md](cores.md) for the full folder→core mapping table.

---

## Why TreeFrogUI?

- **Minimalistic but powerful UI** - Clean, fast game selection screen with quick navigation.
- **57 emulator cores** - Now supports 57 emulator cores compared to only 14 in the stock OS. This includes standout additions such as **PICO-8** (via Fake08/Retro8), **Quake** (via Tyrquake), **Cave Story** (via NXEngine), **Doom** (via PrBoom), **PlayStation 1** (via PCSX ReArmed), plus classic computer systems like Commodore Amiga and Atari ST.
- **Highly configurable cores** - Configurable settings for all cores, allowing for retro features like console palette swaps, LCD ghosting emulation, and more.
- **In-game saves** - Fully supported across all compatible cores for seamless session saving and loading.
- **Auto-resume on boot** - Automatically boots back into the last played game or frontend view upon device boot.
- **Clean, configurable menu** - Smooth iPhone-style background crossfades (instant selection), an optional **Hide Empty Folders** setting, and right-stick drift filtering so accidental touches don't trigger phantom presses while navigating.
- **Rich theming options** - Custom background images, fonts, and 30 built-in color themes to fit your style.
- **Game switcher** - Optional OnionOS-style recents carousel: big box art (or the last save-state screenshot if no art), resumes where you left off. Turn it on in Settings (Game Switcher), it replaces the recents list.
- **Play-time stats** - Tracks how long you play each game, shown in the browser.
- **Proper PCSX4ALL support** - Configurable PlayStation 1 emulator core with native support for `.iso`, `.bin`/`.cue`, and other disc formats.
- **Flexible display scaling** - Easily adjust display scaling modes (Zoom, Aspect Ratio, and Integer Scaling) to suit your preference.

---
## ROM folder setup

**How to add games:**
1. On your PC, open the SD card. Find the **`roms`** folder (it's at the root, the top level of the card).
2. Inside `roms`, make a folder named for the system you want, exactly as in the table below. Example: for Game Boy Advance games, make `roms/GBA`.
3. Copy your game files into that folder.
4. Put the card back in, launch TreeFrogUI, and the system shows up.

The **folder name is what picks the emulator** (so `GBA` runs Game Boy Advance, `FC` runs NES, etc). Some systems accept a few different names, all listed below.

| Folder Name(s) | Target Console / System | Core Shared Library (`.so`) |
|---|---|---|
| **FC**, **nes** | NES / Famicom | `fceumm_libretro.so` |
| **NES**, **nesq** | NES / Famicom (fast) | `quicknes_libretro.so` |
| **nest** | NES / Famicom (accurate) | `nestopia_libretro.so` |
| **fds** | Famicom Disk System | `fceumm_libretro.so` |
| **SFC**, **snes** | Super Famicom / SNES | `snes9x2005_plus_libretro.so` |
| **snes02** | SNES (accurate / alt) | `snes9x2002_libretro.so` |
| **GBA**, **gba** | Game Boy Advance | `gpsp_libretro.so` |
| **mgba**, **gbaf** | Game Boy Advance (accurate) | `mgba_libretro.so` |
| **gbav** | Game Boy Advance (alt) | `vba_next_libretro.so` |
| **gb**, **dblcherrygb** | Game Boy / Color | `gambatte_libretro.so` |
| **gbgb** | Game Boy (Gearboy) | `gearboy_libretro.so` |
| **gbb** | Game Boy (TGBDual) | `tgbdual_libretro.so` |
| **MD**, **SMS**, **sega** | Mega Drive / Genesis / Master System | `picodrive_libretro.so` |
| **32x** | Sega 32X (may run slow) | `picodrive_libretro.so` |
| **GG**, **gg** | Game Gear | `gearsystem_libretro.so` |
| **gpgx** | Mega Drive (accurate) | `genesis_plus_gx_libretro.so` |
| **segacd** | Sega CD / Mega CD | `genesis_plus_gx_libretro.so` |
| **PS**, **ps1**, **psx** | PlayStation | `pcsx_rearmed_libretro.so` |
| **pce** | PC Engine / TurboGrafx-16 | `mednafen_pce_fast_libretro.so` |
| **pcesgx** | PC Engine SuperGrafx | `mednafen_supergrafx_libretro.so` |
| **pcfx** | PC-FX | `mednafen_pcfx_libretro.so` |
| **pc8800** | NEC PC-8800 | `quasi88_libretro.so` |
| **ngpc** | Neo Geo Pocket / Color | `race_libretro.so` |
| **geolith** | Neo Geo AES/MVS | `geolith_libretro.so` |
| **wswan** | WonderSwan / Color | `mednafen_wswan_libretro.so` |
| **wsv** | Watara Supervision | `potator_libretro.so` |
| **vb** | Virtual Boy | `mednafen_vb_libretro.so` |
| **a26** | Atari 2600 | `stella2014_libretro.so` |
| **a5200** | Atari 5200 | `a5200_libretro.so` |
| **a78** | Atari 7800 | `prosystem_libretro.so` |
| **a800** | Atari 800 | `atari800_libretro.so` |
| **lnx** | Atari Lynx | `handy_libretro.so` |
| **atari-st** | Atari ST | `castaway_libretro.so` |
| **amiga** | Commodore Amiga | `uae_libretro.so` |
| **c64** | Commodore 64 | `vice_x64_libretro.so` |
| **c64sc** | Commodore 64 (accurate) | `vice_x64sc_libretro.so` |
| **c64f**, **c64fc** | Commodore 64 (Frodo) | `frodo_libretro.so` |
| **vic20** | Commodore VIC-20 | `vice_xvic_libretro.so` |
| **msx** | MSX | `bluemsx_libretro.so` |
| **spec** | ZX Spectrum | `fuse_libretro.so` |
| **zx81** | ZX81 | `81_libretro.so` |
| **col** | ColecoVision | `gearcoleco_libretro.so` |
| **amstrad** | Amstrad CPC | `crocods_libretro.so` |
| **amstradb** | Amstrad CPC (CPC+) | `cap32_libretro.so` |
| **thom** | Thomson MO/TO | `theodore_libretro.so` |
| **xmil** | Sharp X68000 | `x68k_libretro.so` |
| **pico286** | DOS / PC (8086-286, standalone) | `pico286` + `freedos.img` (see below) |
| **Quake** | Quake | `tyrquake_libretro.so` |
| **prboom** | Doom / Heretic | `prboom_libretro.so` |
| **wolf3d** | Wolfenstein 3D | `ecwolf_libretro.so` |
| **outrun** | Out Run | `cannonball_libretro.so` |
| **cavestory** | Cave Story | `nxengine_libretro.so` |
| **flashback** | Flashback | `reminiscence_libretro.so` |
| **xrick** | Rick Dangerous | `xrick_libretro.so` |
| **jnb** | Jump 'n Bump | `jumpnbump_libretro.so` |
| **gw** | Game & Watch | `gw_libretro.so` |
| **pico8** | PICO-8 (fake08) - also accepts legacy `fake08` folder | `fake08_libretro.so` |
| **retro8** | PICO-8 (retro8) | `retro8_libretro.so` |
| **lowres-nx** | LowRes NX | `lowresnx_libretro.so` |
| **tic80** | TIC-80 fantasy console | `tic80_libretro.so` |
| **pokem** | Pokémon Mini | `pokemini_libretro.so` |
| **m2k** | MAME 2000 (MAME 0.37b5 romset) | `mame2000_libretro.so` |
| **cps1** | Capcom CPS-1 arcade | `fbalpha2012_cps1_libretro.so` |
| **cps2** | Capcom CPS-2 arcade | `fbalpha2012_cps2_libretro.so` |
| **neogeo** | Neo Geo arcade | `fbalpha2012_neogeo_libretro.so` |
| **int** | Mattel Intellivision | `freeintv_libretro.so` |
| **fcf** | Fairchild Channel F | `freechaf_libretro.so` |
| **cdg** | CD+G Karaoke | `pocketcdg_libretro.so` |
| **chip8** | CHIP-8 | `jaxe_libretro.so` |
| **arduboy** | Arduboy (Ardens - fast) | `ardens_libretro.so` |
| **arduous** | Arduboy (arduous/simavr - cycle-accurate, slower) | `arduous_libretro.so` |
| **vec** | Vectrex | `vecx_libretro.so` |
| **o2em** | Odyssey² / Videopac | `o2em_libretro.so` |
| **gme** | Game Music Emu | `gme_libretro.so` |
| **gong** | Pong clone | `gong_libretro.so` |
| **vapor** | VaporSpec | `vaporspec_libretro.so` |

See [cores.md](cores.md) for detailed build status and source repositories of TreeFrogUI external cores.

**PICO-8 (fake08):** place carts in `roms/pico8/` (the legacy `roms/fake08/` folder still works). Both `.p8` (text source) and `.p8.png` (cart image) formats are supported.

**Arduboy:** the `arduboy` folder uses the **Ardens** core (a fast custom AVR emulator) and accepts both `.hex` and `.arduboy` files. The `arduous` folder runs the older simavr-based **arduous** core (cycle-accurate but much slower; `.hex` only) - use it only if a game misbehaves under Ardens.

### Arcade (MAME / FB Alpha / Neo Geo)

Arcade games are `.zip` files of a romset. **Keep them zipped** - the core reads the zip directly, do not extract.

| Folder | Core | Romset it needs |
|---|---|---|
| `cps1` | FB Alpha 2012 | Capcom **CPS-1** games |
| `cps2` | FB Alpha 2012 | Capcom **CPS-2** games |
| `neogeo` | FB Alpha 2012 | **Neo Geo** games (also needs `neogeo.zip` BIOS in the folder) |
| `m2k` | MAME 2000 | misc arcade, **MAME 0.37b5** romset |

> [!IMPORTANT]
> **Romsets are version-locked.** Each core only loads ROMs from the matching set:
> the `cps1`/`cps2`/`neogeo` folders need a **FB Alpha 2012** romset, and `m2k`
> needs a **MAME 0.37b5** romset. A zip from a different MAME/FBNeo version will
> **fail to load** even if the game name matches - this is the #1 cause of arcade
> ROMs not working. Neo Geo games also need the **`neogeo.zip`** BIOS placed in
> **`cubegm/bios/`** (the system folder), **not** the rom folder.

Pick the folder by hardware: Street Fighter II etc. → `cps1`, Marvel vs Capcom etc.
→ `cps2`, Metal Slug/KOF etc. → `neogeo`. For Neo Geo you can also use the dedicated
`geolith` core. Heavy CPS-2/Neo Geo titles may run slow on this CPU.

### DOS / PC games (pico286)

`pico286` runs old DOS / PC games (the 8086 to 286 era: Prince of Persia, Digger, Oregon Trail, etc). Games go in `roms/pico286/`.

**Step 1 (do this once): give it FreeDOS.**
A ready-made FreeDOS file already ships with TreeFrogUI at `cubegm/bios/x86BOOT.img`, so you usually do nothing. If it is missing: download the **FreeDOS 1.4 "Floppy Edition"** from [freedos.org/download](https://www.freedos.org/download/), open the zip, take the file **`144m/x86BOOT.img`**, and copy it to **`cubegm/bios/x86BOOT.img`** on the card. (FreeDOS is the little operating system the games run on top of. You only set this up once.)

**Step 2: add a game. The easy way (no tools, works on any computer):**
1. Get the game as **floppy disk images** (files ending in `.img`).
2. Make a folder for it, like `roms/pico286/prince/`.
3. Copy the `.img` files into that folder.
4. Launch it from the menu. It boots FreeDOS and starts the game by itself.

That's it. Most DOS games come as one or a few floppy `.img` files and just work this way.

**Multi-disk games:** if a game asks to "insert disk 2", press **SELECT + START** for the menu, choose **Disk swap**, pick disk 2, press A. Then continue in the game.

**Big games that need a "hard disk" (optional, advanced):**
Some bigger games come as loose files (an `OREGON.EXE` and friends), not floppies. For those you pack the files into one hard-disk image. Make a folder with all the game files, add a text file named `RUN.BAT` inside it containing the command to start the game (for example one line: `OREGON`), then build the image:

- **Linux / macOS:** run the included script (needs `mtools` installed):
  ```
  ./make_dos_img.sh  <game_folder>  oregon.img  16
  ```
- **Windows:** the script does not run on Windows directly. Easiest options:
  1. **WSL** (Windows Subsystem for Linux): install it, `sudo apt install mtools`, then run the same `./make_dos_img.sh` command above. Recommended.
  2. **DOSBox** (works everywhere): `imgmake oregon.img -t hd -size 16`, then mount it and copy the game files in. See DOSBox docs for `imgmake`/`mount`.
  3. Any tool that can **make a FAT16 disk image** and copy files into it (e.g. WinImage: New image, 16 MB, format FAT16, drag the files in, Save As `.img`).

Drop the resulting `oregon.img` into `roms/pico286/oregon/` and launch it.

**Controls / menu:**
- **SELECT + START** - open the pico286 **main menu**: Resume, Keyboard, Disk swap, Mouse mode, Mouse speed, Joystick mode, CPU speed, Frame skip, Reset, Exit to menu. (D-pad navigates, A selects, Left/Right adjusts the speed/skip rows, B closes.)
- **Joystick mode** (menu toggle): D-pad → game-port axes, A/B → joystick buttons 1/2.
- **L + R** - quick on-screen keyboard (D-pad moves, A presses, B closes) for typing DOS commands.
- **Mouse mode** (toggle in the menu): D-pad moves the cursor, A = left click, B = right click. Needs a mouse driver, which the bundled FreeDOS loads automatically (CTMOUSE).
- In-game buttons: A=Enter, B=Esc, X=Space, Y=Ctrl, L=Shift, R=Alt.

---

## Customisation (themes, fonts, game art / box art / thumbnails, backgrounds)

Make it look how you want. Full step-by-step in the 📦 **[Customisation Guide](theme.md)**. The quick version:

**Theme (colors)** - in TreeFrogUI: Settings → Theme, press Left/Right. 30 built-in color themes. (The in-game emulator menu picks up the same theme colors automatically.)

**Font** - Settings → Font, press Left/Right. Or drop a `.ttf`/`.otf` in `frogui/fonts/` and pick it.

**Game art / box art / cover / thumbnail** (the picture shown for each game) - put the image in a hidden `.res/` folder next to the ROM, named after the ROM with a `.rgb565` extension:
```
roms/GBA/Advance Wars.gba
roms/GBA/.res/Advance Wars.rgb565    ← the box art
```
Convert any cover image with:
```
ffmpeg -i cover.png -vf scale=160:160 -f rawvideo -pix_fmt rgb565le "Advance Wars.rgb565"
```
(Rule: `<rom folder>/.res/<rom name without extension>.rgb565`.)

**Background image** (per system / screen) - drop a `854×480` `.png`/`.jpg`/`.bmp` in **`frogui/`**, named after the screen or folder:
```
frogui/main.png          ← main systems list
frogui/recents.png       ← recent games
frogui/favourites.png    ← favorites
frogui/FC.png            ← the FC (NES) folder (name must match the roms folder)
```
Use dark/muted images so menu text stays readable.

See the [Customisation Guide](theme.md) for exact sizes, naming, theme list, and fonts.

---

## Shortcuts

While playing a game, **SELECT** is the function key (like the MENU button on other handhelds). Hotkeys follow the OnionOS layout:

- **`SELECT + START`** - open the in-game menu.
- **`SELECT + R2`** - save state.
- **`SELECT + L2`** - load state.
- **`SELECT + R1`** - fast-forward: off, 2x, 3x, off (audio mutes). Off by default, turn it on per core in the menu (Audio and video).
- **`SELECT + B`** - hold to rewind. Off by default, turn it on per core in the menu (it uses RAM and slows the game).

> Fast-forward and rewind are now **per-core toggles** (menu, Audio and video). They stay off until you enable them, so cores that don't need them keep full RAM and speed.

PCSX4ALL (PS1) is a standalone emulator with its own menu and hotkeys.

---

## BIOS files required

Some cores need BIOS/firmware files. Place them in the system folder the core expects (check individual core docs), typically alongside the ROMs or in a `bios/` subfolder.

> **PlayStation 1 - use a real BIOS.** Drop `scph1001.bin` in `/mnt/sdcard/cubegm/cores/.pcsx4all/`. PCSX4ALL falls back to an HLE BIOS when it's missing, but the HLE path causes **graphical glitches, worse performance, and broken/hanging memory-card saves** (e.g. Harvest Moon). With the real BIOS, saving and compatibility work correctly.

| System | File needed |
|--------|-------------|
| PlayStation 1 (PCSX4ALL) | `scph1001.bin` in `/mnt/sdcard/cubegm/cores/.pcsx4all/` (**strongly recommended** - without it: graphics/perf/save issues) |
| GBA (gpsp) | `gba_bios.bin` (official Nintendo GBA BIOS) |
| Amiga (UAE) | `kick.rom` (Amiga Kickstart ROM) |
| Atari ST (castaway) | TOS ROM image |
| Famicom Disk System (fds) | `disksys.rom` in **`cubegm/bios/`** |
| Neo Geo (geolith / neogeo) | `neogeo.zip` BIOS in **`cubegm/bios/`** |
| Sega CD / Mega CD (segacd) | `bios_CD_U.bin` / `bios_CD_E.bin` / `bios_CD_J.bin` (region BIOS) in **`cubegm/bios/`** |
| PC-FX (beetle-pcfx) | `pcfx.rom` |
| PC-88 (quasi88) | NEC PC-88 BIOS files |

---

## Building from source

### Requirements

- SF3000 cross-toolchain at `~/sf3000-work/sf3000toolchain/`
- `git`, `make`, `nproc`
- `cmake` (only for the cmake-based cores: TIC-80; a static build from
  [Kitware](https://github.com/Kitware/CMake/releases) works, no root needed).
  `build_all.sh` skips those cores with a warning if cmake is absent.

### Steps

```sh
# Workspace root holds all the source repos as siblings
mkdir -p ~/sf3000-work && cd ~/sf3000-work

# Main repo (build scripts, patches, staging, docs)
git clone git@github.com:tzubertowski/treefrog-ui.git sf3000_treefrogui

# Frontend + standalone emulator sources (separate repos, built in place)
git clone -b r36sx git@github.com:tzubertowski/FrogUI.git FrogUI
git clone -b r36sx git@github.com:tzubertowski/TreeFrogUI_picoarch.git picoarch
git clone        git@github.com:tzubertowski/TreeFrogUI_pcsx4all.git pcsx4all
git -C picoarch submodule update --init libretro-common   # libpicofe is vendored

cd sf3000_treefrogui
./clone_cores.sh      # clones all libretro core upstreams into cores/
./build_all.sh        # applies patches/, builds cores + pico286 + TIC-80 (needs cmake)

# .so cores land in build/ ; pico286/pcsx4all binaries go to staging cubegm/
cp build/*.so /mnt/sdcard/cubegm/cores/
```

Repos: **treefrog-ui** (this), **FrogUI** (launcher core), **TreeFrogUI_picoarch**
(libretro frontend, our fork), **TreeFrogUI_pcsx4all** (standalone PS1). pico286
is reconstructed from `patches/pico286-sf3000.patch` onto the upstream `xrip/pico-286`
clone, so it needs no separate repo. BIOS, romsets, and the FreeDOS `x86BOOT.img`
are user-supplied (see the BIOS section).

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

**picoarch** handles display (`/dev/dis` + framebuffer), audio (ALSA), and the libretro core lifecycle. TreeFrogUI is just another `.so` loaded by picoarch - it renders the file browser UI and uses `fork+waitpid` to launch games without losing the display connection.

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
| `vecx` (Vectrex) | ❌ needs OpenGL - not available on SF3000 |
| `ardens` (Arduboy, default) | ✅ built directly (no cmake); C++14 libretro target |
| `arduous` (Arduboy, alt) | ✅ simavr-based, built directly (cycle-accurate, slow) |
| `o2em` (Odyssey²) | ❌ not yet cloned |
| `vice` (C64) | commented out - large build, enable manually in build_all.sh |
| picoarch binary | not included - obtain from SF3000 multicore project |

---

## Device notes

### R36SX

> [!CAUTION]
> **v2.7 owners read this first.** There are **many different v2.7 hardware revisions**, and I don't have access to all of them. Some run TreeFrogUI perfectly (like mine); others get stuck on a **"damaged SD card"** screen. **Your particular v2.7 may or may not work, I can't guarantee it.** I don't currently own one of the newer v2.7 units to test against. Want me to track one down and add support? ☕ **[ko-fi.com/proszty](https://ko-fi.com/proszty)**.

> [!NOTE]
> **Right analog stick.** The right stick **cannot** work as a real analog stick, and no software update can change that. On this console it's physically wired to act **exactly like the X / A / B / Y face buttons**: nudging it is the same as pressing those buttons, just on/off, with no "how far" or "which angle" info. The console never hands analog data to apps like TreeFrogUI. So the right stick simply **mirrors the face buttons** (tiny accidental movements are ignored, so it won't fire on its own). Hardware limitation, not a bug or missing feature.

### SF3000

> [!NOTE]
> Built primarily for the **SF3000**. It **might** also run on similar variants like the **SF3000HD**, **SF3100**, **SF3500**, and **GB350**. I don't own these to test, so compatibility is unverified. Try it and let me know if it works. Want one supported properly? ☕ **[ko-fi.com/proszty](https://ko-fi.com/proszty)**.

---

## Porting TreeFrogUI to other devices

Want TreeFrogUI on a device that isn't supported yet? R36SX v2.7 (bootloader
protection), SF3000 V3 (bootloader protection), SF3500, SF3100, GB350, HDMI-out
clones, and others are all on the wishlist.

The catch: porting needs the actual hardware in hand. Bootloaders differ, input
and display wiring differ, the protected variants need live debugging. There's
no way to do it blind.

Every device supported so far was bought out of my own pocket. There are far
more clones out there than I can reasonably keep buying.

If you want to see a port happen, chip in: **https://ko-fi.com/proszty**.
Donations go straight toward buying the next device to port to.

---

## Credits

- **picoarch** - libretro frontend adapted for SF3000
- **FrogUI** - original launcher by tzubertowski, fork of [FrogUI](https://github.com/tzubertowski/FrogUI)
- **angree** - Amiga (UAE4ALL) and Atari ST (castaway) ports for SF-series handhelds
- **goph-R** - [SF3000-RE](https://github.com/goph-R/SF3000-RE) reverse engineering project and boot logo specs
- **SjslTech** - [YouTube](https://www.youtube.com/@SjslTech) - R36SX testing & contributions
- All libretro core authors

---

## License & Attribution

This project is a compilation of multiple components, each retaining its original license:

- **TreeFrogUI for SF3000 (UI Port)**: Licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)** license. It is a heavily modified fork of [FrogUI](https://github.com/tzubertowski/frogui), created by Tomasz Zubertowski, Desoxyn, and Q_ta.
 - *Attribution*: Changes have been made to support the SF3000 hardware architecture, resolution, input handling, and directory layout.
 - *ShareAlike*: Any modifications or derivations of the UI frontend code must be distributed under the same CC BY-NC-SA 4.0 license.
 - *NonCommercial*: This software is strictly for non-commercial use. Selling or bundling it with commercial devices is prohibited.
  - *Assets & Images*: The logo and font were taken from the upstream [FrogUI](https://github.com/tzubertowski/frogui) repository, while the default system background images were sourced from the **[Art Book Next](https://github.com/anthonycaccese/art-book-next-es)** ES-DE theme by Anthony Caccese. These assets are used under their respective open-source and creative commons licenses.
- **picoarch (Frontend Integration)**: Uses code from `libpicofe` (triple-licensed under GNU GPL v2+, GNU LGPL v2.1+, or the MAME license) and neonloop's wrapper code (licensed under the **BSD 3-Clause License**).
- **Emulator Cores**: Each emulator core located in the `cores/` directory is built from its respective upstream repository and retains its individual open-source license (such as GPL, BSD, MIT, or MAME license). See [cores.md](cores.md) and individual core subdirectories for details.

See the root [LICENSE.md](LICENSE.md) file for the full copyright notices and license texts.
