# Arcade cores on SF3000 (74Kc)

## TLDR

Shipped lightweight split cores stay the defaults. Two modern cores
(FBNeo, mame2003-plus) were added as opt-in picker options only. Neither beats
the defaults on this hardware: FBNeo is too slow, mame2003-plus needs different
romsets. Use them only as fallbacks.

## Defaults (auto-mapped, keep these)

| Folder | Core | Romset |
|--------|------|--------|
| cps1   | fbalpha2012_cps1   | FBA |
| cps2   | fbalpha2012_cps2   | FBA |
| neogeo | fbalpha2012_neogeo | FBA |
| m2k    | mame2000           | 0.37b5 |

These are ~2MB each, purpose-built for weak hardware. Fastest option for the
74Kc. Match the romsets already on the card.

## Modern cores (built, picker-only, NOT default)

Added to the frogui per-game core picker via `extra_picker_cores[]` in
`frogui_libretro.c` (build_core_choices appends them). No folder maps to them,
so there is zero regression. Users opt in per game from the core menu.

- **fbneo** (FBNeo, 63MB): best CPS/NeoGeo compat. Verified on device:
  **too slow on 74Kc**. Value = last-resort fallback for games fbalpha2012
  cannot run at all (slow-but-works beats does-not-boot).
- **mame2003_plus** (32MB): big general-MAME library. Core works, but needs
  **MAME-2003-plus-format romsets** (~0.78 era). The card's arcade sets are
  FBA / 0.37b5 format, so games fail with "Required files are missing /
  readroms failed" (confirmed: a Neo Geo set's 201-c1.bin, mamelo.lo NOT
  FOUND). Useful only if matching romsets are sourced.

## Key facts

- Romset versions are NOT interchangeable: mame2000 = 0.37b5, mame2003-plus =
  ~0.78, fbalpha2012 = FBA format. A rom that boots in one will not boot in
  another. "Core supports the system" does not mean "your romset boots."
- For Neo Geo specifically, fbalpha2012_neogeo is the right core: lighter and
  matches the FBA sets already present. mame2003-plus can emulate Neo Geo
  hardware but needs MAME-format romsets + a MAME-format neogeo.zip BIOS.
- Both modern cores are large (32MB / 63MB stripped) vs ~2MB splits. RAM at
  dlopen time is the on-device risk; FBNeo's size + CPU cost rule it out as a
  default.

## Build

`clone_cores.sh` clones both repos; `build_all.sh` cross-compiles them.
mame2003-plus and FBNeo both need the -shared LDFLAGS passed explicitly (our
command-line LDFLAGS overrides the Makefile's own); FBNeo additionally needs
-lpthread (Cave CV1000 epic12 threaded blitter). See the entries in
build_all.sh.

## Verdict

The lightweight fbalpha2012 splits + mame2000 remain the right call for the
74Kc. The modern cores are available as fallbacks but do not displace the
defaults. No further arcade-core work unless matching mame2003-plus romsets are
sourced.
