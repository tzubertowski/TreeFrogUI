# Wolfenstein 3D (ecwolf)

← [back to README](../../README.md)

`wolf3d` runs [ecwolf](https://maniacsvault.net/ecwolf/), a source port of Wolfenstein 3D (and Spear of Destiny). It needs **two separate things** to work, which is the usual source of confusion:

1. **The engine's own resource pack, `ecwolf.pk3`** (fonts/menus for the source port itself - not id Software's game data). This already ships with TreeFrogUI at `cubegm/bios/ecwolf.pk3`, so you don't need to do anything for this part.
2. **The actual game data** - the original `.wl1`/`.wl6` files (`VSWAP`, `GAMEMAPS`, `MAPHEAD`, `AUDIOHED`, `AUDIOT`, `VGAHEAD`, `VGAGRAPH`, `VGADICT`). Drop the full set in `roms/wolf3d/`.
   - The **shareware episode** (`.wl1`) is freely distributable by id Software - e.g. [archive.org/details/wolf3dsw](https://archive.org/details/wolf3dsw).
   - The **full/retail game** (`.wl6`) needs your own legally-owned copy.

> [!NOTE]
> Since every `.wl1`/`.wl6` file is individually a "valid" ROM as far as the folder browser is concerned, you'll see all 8 data files listed separately in the menu. **It doesn't matter which one you pick** - the engine reads the whole directory regardless of which specific file launched it.

If `ecwolf.pk3` is somehow missing (e.g. building from source without running `build_all.sh`'s ecwolf step), the game fails instantly with `Could not open ecwolf.pk3!` and bounces back to the menu. It can also be dropped directly in `roms/wolf3d/` next to the game data as a fallback.
