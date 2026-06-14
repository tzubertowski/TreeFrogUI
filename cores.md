# SF3000 Core Mappings

ROM folder name → core .so file. Built = present in `build/`. ❌ = not built (see notes).

---

## Nintendo

| Folder | System | Core .so | Source |
|--------|--------|----------|--------|
| `nes`, `FC` | NES | `fceumm_libretro.so` | [tzubertowski/libretro-fceumm](https://github.com/tzubertowski/libretro-fceumm) |
| `fds` | Famicom Disk System (needs `disksys.rom`) | `fceumm_libretro.so` | [tzubertowski/libretro-fceumm](https://github.com/tzubertowski/libretro-fceumm) |
| `nesq`, `NES` | NES (fast) | `quicknes_libretro.so` | [libretro/QuickNES_Core](https://github.com/libretro/QuickNES_Core) |
| `nest` | NES (accurate) | `nestopia_libretro.so` | [libretro/nestopia](https://github.com/libretro/nestopia) |
| `snes`, `SFC` | SNES | `snes9x2005_plus_libretro.so` | [tzubertowski/snes9x2005](https://github.com/tzubertowski/snes9x2005) |
| `snes02` | SNES (2002) | `snes9x2002_libretro.so` | [tzubertowski/snes9x2002](https://github.com/tzubertowski/snes9x2002) |
| `gb` | Game Boy | `gambatte_libretro.so` | [tzubertowski/libretro-gambatte](https://github.com/tzubertowski/libretro-gambatte) |
| `gbgb` | Game Boy | `gearboy_libretro.so` | [drhelius/Gearboy](https://github.com/drhelius/Gearboy) |
| `gbb`, `dblcherrygb` | GB (link cable) | `tgbdual_libretro.so` | [libretro/tgbdual-libretro](https://github.com/libretro/tgbdual-libretro) |
| `gba`, `GBA` | GBA | `gpsp_libretro.so` | [libretro/gpsp](https://github.com/libretro/gpsp) (upstream) |
| `gbac` | GBA (multicore) | `gpsp_multicore_libretro.so` | [tzubertowski/gpsp_multicore](https://github.com/tzubertowski/gpsp_multicore) |
| `gbav` | GBA | `vba_next_libretro.so` | [libretro/vba-next](https://github.com/libretro/vba-next) |
| `mgba`, `gbaf` | GBA (accurate) | `mgba_libretro.so` | [libretro/mgba](https://github.com/libretro/mgba) |
| `pokem` | Pokémon Mini | `pokemini_libretro.so` | [libretro/PokeMini](https://github.com/libretro/PokeMini) |
| `vb` | Virtual Boy | `mednafen_vb_libretro.so` | [libretro/beetle-vb-libretro](https://github.com/libretro/beetle-vb-libretro) |
| `gw` | Game & Watch | `gw_libretro.so` | [libretro/gw-libretro](https://github.com/libretro/gw-libretro) |

---

## Sega

| Folder | System | Core .so | Source |
|--------|--------|----------|--------|
| `sega`, `MD`, `SMS` | Mega Drive / Master System | `picodrive_libretro.so` | [libretro/picodrive](https://github.com/libretro/picodrive) |
| `32x` | Sega 32X (may run slow) | `picodrive_libretro.so` | [libretro/picodrive](https://github.com/libretro/picodrive) |
| `gpgx` | Mega Drive (accurate) | `genesis_plus_gx_libretro.so` |
| `segacd` | Sega CD / Mega CD (needs BIOS) | `genesis_plus_gx_libretro.so` | [libretro/Genesis-Plus-GX](https://github.com/libretro/Genesis-Plus-GX) |
| `gg`, `GG` | Game Gear | `gearsystem_libretro.so` | [drhelius/Gearsystem](https://github.com/drhelius/Gearsystem) |

---

## Atari

| Folder | System | Core .so | Source |
|--------|--------|----------|--------|
| `a26` | Atari 2600 | `stella2014_libretro.so` | [libretro/stella2014-libretro](https://github.com/libretro/stella2014-libretro) |
| `a5200` | Atari 5200 | `a5200_libretro.so` | [libretro/a5200](https://github.com/libretro/a5200) |
| `a78` | Atari 7800 | `prosystem_libretro.so` | [libretro/prosystem-libretro](https://github.com/libretro/prosystem-libretro) |
| `a800` | Atari 800/XL/XE | `atari800_libretro.so` | [libretro/libretro-atari800](https://github.com/libretro/libretro-atari800) |
| `lnx` | Atari Lynx | `mednafen_lynx_libretro.so` | [libretro/beetle-lynx-libretro](https://github.com/libretro/beetle-lynx-libretro) |
| `atari-st` | Atari ST | `castaway_libretro.so` | [angree/sf2000-atarist-emulator](https://github.com/angree/sf2000-atarist-emulator) |

---

## NEC / PC Engine

| Folder | System | Core .so | Source |
|--------|--------|----------|--------|
| `pce` | PC Engine / TurboGrafx-16 | `mednafen_pce_fast_libretro.so` | [libretro/beetle-pce-fast-libretro](https://github.com/libretro/beetle-pce-fast-libretro) |
| `pcesgx` | PC Engine SuperGrafx | `mednafen_supergrafx_libretro.so` | [libretro/beetle-supergrafx-libretro](https://github.com/libretro/beetle-supergrafx-libretro) |
| `pcfx` | PC-FX | `mednafen_pcfx_libretro.so` | [libretro/beetle-pcfx-libretro](https://github.com/libretro/beetle-pcfx-libretro) |
| `pc8800` | NEC PC-88 | `quasi88_libretro.so` | [libretro/quasi88-libretro](https://github.com/libretro/quasi88-libretro) |

---

## SNK

| Folder | System | Core .so | Source |
|--------|--------|----------|--------|
| `ngpc` | Neo Geo Pocket / Color | `race_libretro.so` | [libretro/RACE](https://github.com/libretro/RACE) |
| `geolith` | Neo Geo AES/MVS | `geolith_libretro.so` | [libretro/geolith-libretro](https://github.com/libretro/geolith-libretro) |

---

## Bandai

| Folder | System | Core .so | Source |
|--------|--------|----------|--------|
| `wswan` | WonderSwan / Color | `mednafen_wswan_libretro.so` | [libretro/beetle-wswan-libretro](https://github.com/libretro/beetle-wswan-libretro) |
| `wsv` | Watara Supervision | `potator_libretro.so` | [libretro/potator](https://github.com/libretro/potator) |

---

## Home Computers

| Folder | System | Core .so | Source |
|--------|--------|----------|--------|
| `spec` | ZX Spectrum | `fuse_libretro.so` | [libretro/fuse-libretro](https://github.com/libretro/fuse-libretro) |
| `zx81` | ZX81 | `81_libretro.so` | [libretro/81-libretro](https://github.com/libretro/81-libretro) |
| `amstrad` | Amstrad CPC | `crocods_libretro.so` | [libretro/crocods-core](https://github.com/libretro/crocods-core) |
| `amstradb` | Amstrad CPC (CPC+) | `cap32_libretro.so` | [libretro/libretro-cap32](https://github.com/libretro/libretro-cap32) |
| `col` | ColecoVision | `gearcoleco_libretro.so` | [drhelius/Gearcoleco](https://github.com/drhelius/Gearcoleco) |
| `thom` | Thomson MO/TO | `theodore_libretro.so` | [Zlika/theodore](https://github.com/Zlika/theodore) |
| `xmil` | Sharp X68000 | `x68k_libretro.so` | [libretro/xmil-libretro](https://github.com/libretro/xmil-libretro) |
| `amiga` | Amiga | `uae_libretro.so` | [angree/sf2000-uae-amiga-emulator](https://github.com/angree/sf2000-uae-amiga-emulator) |
| `msx` | MSX | ❌ `bluemsx_libretro.so` | [tzubertowski/libretro-blueMSX](https://github.com/tzubertowski/libretro-blueMSX) |
| `c64`, `c64sc` | Commodore 64 | ❌ `vice_x64_libretro.so` | [libretro/vice-libretro](https://github.com/libretro/vice-libretro) |
| `c64f`, `c64fc` | Commodore 64 (Frodo) | `frodo_libretro.so` | [tzubertowski/libretro-frodo](https://github.com/tzubertowski/libretro-frodo) |
| `vic20` | Commodore VIC-20 | ❌ `vice_xvic_libretro.so` | [libretro/vice-libretro](https://github.com/libretro/vice-libretro) |

---

## PC / DOS Games

| Folder | System | Core .so | Source |
|--------|--------|----------|--------|
| `Quake` | Quake | `tyrquake_libretro.so` | [libretro/tyrquake](https://github.com/libretro/tyrquake) |
| `wolf3d` | Wolfenstein 3D | `ecwolf_libretro.so` | [libretro/ecwolf](https://github.com/libretro/ecwolf) |
| `prboom` | Doom / Heretic | `prboom_libretro.so` | [libretro/libretro-prboom](https://github.com/libretro/libretro-prboom) |
| `outrun` | Out Run (arcade) | `cannonball_libretro.so` | [libretro/cannonball](https://github.com/libretro/cannonball) |
| `m2k` | MAME 2000 (MAME 0.37b5 romset) | `mame2000_libretro.so` | [libretro/mame2000-libretro](https://github.com/libretro/mame2000-libretro) |
| `cps1` | Capcom CPS-1 (FB Alpha 2012) | `fbalpha2012_cps1_libretro.so` | [libretro/fbalpha2012_cps1](https://github.com/libretro/fbalpha2012_cps1) |
| `cps2` | Capcom CPS-2 (FB Alpha 2012) | `fbalpha2012_cps2_libretro.so` | [libretro/fbalpha2012_cps2](https://github.com/libretro/fbalpha2012_cps2) |
| `neogeo` | Neo Geo (FB Alpha 2012) | `fbalpha2012_neogeo_libretro.so` | [libretro/fbalpha2012_neogeo](https://github.com/libretro/fbalpha2012_neogeo) |
| `pico286` | DOS / PC (8086–286) — **standalone** binary, boots via FreeDOS | `pico286` (+ `cubegm/bios/x86BOOT.img`) | [xrip/pico-286](https://github.com/xrip/pico-286) + `patches/pico286-sf3000.patch` |

---

## Open-Source / Homebrew Games

| Folder | System | Core .so | Source |
|--------|--------|----------|--------|
| `cavestory` | Cave Story | `nxengine_libretro.so` | [libretro/nxengine-libretro](https://github.com/libretro/nxengine-libretro) |
| `flashback` | Flashback | `reminiscence_libretro.so` | [libretro/REminiscence](https://github.com/libretro/REminiscence) |
| `xrick` | Rick Dangerous | `xrick_libretro.so` | [libretro/xrick-libretro](https://github.com/libretro/xrick-libretro) |
| `jnb` | Jump 'n Bump | `jumpnbump_libretro.so` | [libretro/jumpnbump-libretro](https://github.com/libretro/jumpnbump-libretro) |
| `gong` | Pong clone | `gong_libretro.so` | [libretro/gong](https://github.com/libretro/gong) |
| `pico8` (or legacy `fake08`) | PICO-8 | `fake08_libretro.so` | [tzubertowski/fake-08](https://github.com/tzubertowski/fake-08) (branch `sf3000`) |
| `ps1r` | PlayStation (lightrec JIT) | `pcsx_rearmed_libretro.so` | [libretro/pcsx_rearmed](https://github.com/libretro/pcsx_rearmed) + `patches/pcsx_rearmed-sf3000-lightrec.patch` |
| `retro8` | PICO-8 compat | `retro8_libretro.so` | [libretro/retro8](https://github.com/libretro/retro8) |
| `lowres-nx` | LowRes NX | `lowresnx_libretro.so` | [timoinutilis/lowres-nx](https://github.com/timoinutilis/lowres-nx) |
| `tic80` | TIC-80 fantasy console (.tic carts) | `tic80_libretro.so` | [nesbox/TIC-80](https://github.com/nesbox/TIC-80) |
| `arduboy` | Arduboy (default) | `ardens_libretro.so` | [tiberiusbrown/Ardens](https://github.com/tiberiusbrown/Ardens) + `patches/ardens-sf3000.patch` - fast custom AVR core, C++14 libretro target, built directly (no cmake) |
| `arduous` | Arduboy (alt, cycle-accurate) | `arduous_libretro.so` | [libretro/arduous](https://github.com/libretro/arduous) - simavr submodule, built directly (no cmake); much slower than Ardens |
| `chip8` | CHIP-8 | ❌ `jaxe_libretro.so` | [libretro/jaxe](https://github.com/libretro/jaxe) |
| `vapor` | VaporSpec | ❌ `vaporspec_libretro.so` | [libretro/vaporspec](https://github.com/libretro/vaporspec) |

---

## Misc / Other

| Folder | System | Core .so | Source |
|--------|--------|----------|--------|
| `int` | Mattel Intellivision | `freeintv_libretro.so` | [libretro/FreeIntv](https://github.com/libretro/FreeIntv) |
| `fcf` | Fairchild Channel F | `freechaf_libretro.so` | [libretro/FreeChaF](https://github.com/libretro/FreeChaF) |
| `o2em` | Odyssey² / Videopac | ❌ `o2em_libretro.so` | [libretro/o2em-libretro](https://github.com/libretro/o2em-libretro) |
| `vec` | Vectrex | ❌ `vecx_libretro.so` | [libretro/libretro-vecx](https://github.com/libretro/libretro-vecx) - needs OpenGL |
| `cdg` | CD+G Karaoke | `pocketcdg_libretro.so` | [libretro/libretro-pocketcdg](https://github.com/libretro/libretro-pocketcdg) |
| `gme` | Game Music Emu | `gme_libretro.so` | [libretro/libretro-gme](https://github.com/libretro/libretro-gme) |

---

## Not mapped (built, no folder yet)

| Core .so | System | Source |
|----------|--------|--------|
| `snes9x2005_libretro.so` | SNES (alt build) | same as snes9x2005_plus |
| `mednafen_lynx_libretro.so` | Atari Lynx | via `lnx` folder |

---

## Notes

- Folders are case-sensitive on picoarch - match exactly
- Multiple folders can map to same core (e.g. `nes` and `FC` both → fceumm)
- ❌ cores not in `build/` - either missing dependency or not cloned
- `uae_libretro.so` - add `amiga` folder mapping to frogui_libretro.c to use it
- `castaway_libretro.so` - add `atari-st` folder mapping to use it
