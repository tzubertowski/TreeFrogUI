# OnionOS gap analysis

Where TreeFrogUI stands vs OnionOS (Miyoo Mini), for the SF3000 / R36SX
(MIPS 74Kc, single core, ~590 BogoMIPS, no cpufreq, typically no WiFi).

TLDR: core coverage is already broad (~60 systems, 90 folder mappings) and
beats OnionOS in a few spots. Real gaps are ScummVM, a couple near-free folders,
and the network-dependent features we can't do (no WiFi).

## Cores / systems

### Worth adding (runs on this CPU)
| System | Core | Effort | Value |
|---|---|---|---|
| ScummVM | scummvm | High (toolchain port: Makefile ignores --sysroot, needs engine trimming for RAM) | High, whole point-and-click genre |
| Famicom Disk System | fceumm (already shipped) | Near-free: add `fds` folder + FDS BIOS | Medium |
| Sega 32X | picodrive (already shipped) | Near-free: add `32x` folder | Low, runs slow, marginal |
| Neo Geo CD | neocd | Medium build | Medium, NGCD + CD audio |
| TIC-80 | tic80 | Medium build | Medium, fantasy console / homebrew |
| OpenBOR | openbor | Medium-high | Medium, large homebrew beat-em-up scene |

### Niche (low priority)
Wasm-4, Uzebox, Lutro / ChaiLove (Lua engines), Mega Duck / SameDuck, Sharp X1,
Tandy CoCo / Dragon (xroar), tiny freebies (2048, MrBoom, Dinothawr).

### Skip, too heavy for ~590 BogoMIPS single core
N64, PSP, NDS, Saturn, Dreamcast, 3DO, Atari Jaguar. OnionOS lists some but
they are experimental even on the stronger Miyoo, worse here.

### We have that OnionOS does not emphasise
Quake (tyrquake), DOS (pico286 standalone with FreeDOS auto-boot, on-screen
keyboard, mouse, joystick, disk-swap), Arduboy (Ardens fast core), PICO-8,
LowRes NX, GME, Cave Story, Flashback, plus the full home-computer set
(Amiga, C64, MSX, Amstrad CPC, X68000, ZX, Thomson, PC-88).

## Features

| Feature | OnionOS | TreeFrogUI | Notes |
|---|---|---|---|
| Themes (colors) | Yes | Yes | FrogUI themes; picoarch in-game menu now syncs theme colors |
| Custom fonts | Yes | Yes | picoarch menu uses the FrogUI font choice |
| Per-folder backgrounds / box art | Yes | Yes (manual) | per-system/per-folder images; game thumbnails (.res/*.rgb565) |
| Box-art scraper | Yes | No | needs WiFi, our devices have none. Manual art only |
| Save states + slots | Yes | Yes | slots + screenshot thumbnails |
| Auto-resume on boot | Yes | Yes | Quick Resume boots into last game; Auto-Save/Auto-Load restores state (reserved slot), independent toggles |
| In-game menu | Yes | Yes | picoarch menu, frozen-frame bg at correct aspect |
| Fast-forward | Yes | Yes | SELECT+R1 cycle |
| Rewind | Yes | Yes | hold SELECT+B (disabled on cores with unreliable state size) |
| Cheats | Yes | Yes | picoarch cheat support |
| Favorites | Yes | Yes | FrogUI favorites |
| Recent games | Yes | Yes | FrogUI recents |
| Search | Yes | Yes | FrogUI search |
| Button remap | Yes | Yes (global) | per-game remap not yet |
| Scaling modes | Yes | Yes | Zoom / Aspect / Integer |
| Multi-disc (m3u) | Yes | Partial | disc-control present; m3u playlist UX limited |
| Standalone apps / PAKs | Yes | Yes | standalone bins (pico286, pcsx4all) |
| RetroAchievements | Yes | No (N/A) | needs WiFi, devices have none |
| Netplay | Yes | No (N/A) | needs WiFi |
| Play-time / activity stats | Yes | No | minor; could add locally |
| Bluetooth audio | Plus only | No (N/A) | no BT hardware |
| Overclock / CPU governor | Yes | No (N/A) | fixed bootloader clock, no cpufreq |

### Feature gaps actually worth doing
1. Per-game button remap (we have global only).
2. m3u multi-disc playlist UX (engine support exists).
3. Local play-time stats (nice-to-have).

Everything else OnionOS has beyond us needs WiFi/BT/cpufreq the hardware lacks,
so it is not applicable rather than missing.

## Recommended order
1. Near-free cores: `fds` + `32x` folders (cores already shipped).
2. ScummVM (dedicated toolchain port).
3. Neo Geo CD / TIC-80 / OpenBOR for completeness.
