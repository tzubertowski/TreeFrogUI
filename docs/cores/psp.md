# PSP / PPSSPP (experimental)

TreeFrogUI recognizes `roms/psp/` and uses the bundled `ppsspp_libretro.so`
when available. If the optional standalone binary `cubegm/ppsspp` is present,
the launcher prefers it for PSP entries.

The standalone port is the experimental [PPSSPP Data Frog SF3000 project](https://github.com/DevBobby-REP/PPSSPP-DATAFROGSF3000).
Clone it with `clone_cores.sh` when preparing a development checkout. The
project currently reports very low performance and does not publish a ready
binary in this repository, so it is not shipped by default. Place a compatible
executable at `cubegm/ppsspp` to opt in.

Put PSP content (`.iso`, `.cso`, `.pbp`, or supported homebrew formats) under
`roms/psp/`. Compatibility and speed depend heavily on the game; this is an
experimental port for testing rather than a generally playable PSP emulator.
