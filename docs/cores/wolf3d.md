# Wolfenstein 3D (ecwolf)

← [back to README](../../README.md)

`wolf3d` runs [ecwolf](https://maniacsvault.net/ecwolf/), a source port of Wolfenstein 3D (and Spear of Destiny). It needs **two separate things** to work, which is the usual source of confusion:

1. **The engine's own resource pack, `ecwolf.pk3`** (fonts/menus for the source port itself - not id Software's game data). This already ships with TreeFrogUI at `cubegm/bios/ecwolf.pk3`, so you don't need to do anything for this part.
2. **The actual game data** - a complete matching set (`VSWAP`, `GAMEMAPS`, `MAPHEAD`, `AUDIOHED`, `AUDIOT`, `VGAHEAD`, `VGAGRAPH`, `VGADICT`). Drop each game set in its own subfolder under `roms/wolf3d/`.
   - The **shareware episode** (`.wl1`) is freely distributable by id Software - e.g. [archive.org/details/wolf3dsw](https://archive.org/details/wolf3dsw).
   - The **full/retail game** (`.wl6`) needs your own legally-owned copy.
   - The **Spear of Destiny demo** uses `.sdm`; the retail game uses `.sod`. Mission packs may use `.sd2` and `.sd3`.

> [!NOTE]
> Since every data file is individually a "valid" ROM as far as the folder browser is concerned, you'll see all eight files listed separately. Launch `VSWAP.WL1` for Wolf3D shareware or `VSWAP.SDM` for the Spear demo; ECWolf reads the companion files from the same directory.

Example layout:

```text
roms/wolf3d/Wolfenstein 3D Shareware/VSWAP.WL1
roms/wolf3d/Wolfenstein 3D Shareware/GAMEMAPS.WL1
roms/wolf3d/Spear of Destiny Demo/VSWAP.SDM
roms/wolf3d/Spear of Destiny Demo/GAMEMAPS.SDM
```

If `ecwolf.pk3` is somehow missing (e.g. building from source without running `build_all.sh`'s ecwolf step), the game fails instantly with `Could not open ecwolf.pk3!` and bounces back to the menu. It can also be dropped directly in `roms/wolf3d/` next to the game data as a fallback.
