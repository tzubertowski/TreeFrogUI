# Heroes II

TreeFrogUI includes the SF3000 libretro core from
[FroggyHeroes2](https://github.com/tzubertowski/FroggyHeroes2).

The game data is not bundled. Supply the freely redistributable H2DEMO data or
your own legally obtained copy. A GOG Windows installer can be unpacked with
[innoextract](https://constexpr.org/innoextract/) (or 7-Zip on Windows):

```sh
innoextract setup_homm2_gold_win_2.0.0.7.exe
```

Copy only the game data from the extracted `app` directory. Do not copy the
installer, Windows executable, or other Windows-specific files:

```text
roms/fheroes2/DATA/HEROES2.AGG
roms/fheroes2/MAPS/*.MP2 and *.MX2
roms/fheroes2/GAMES/*.GM1
roms/fheroes2/fheroes2.cfg
```

For the GOG release, the source paths are `app/DATA/HEROES2.AGG`,
`app/MAPS/*.(MP2|MX2)`, and `app/GAMES/*.GM1`. The included `fheroes2.cfg`
already uses the correct SF3000 paths; keep it in the `fheroes2` folder.

Open **Heroes II** in TreeFrogUI. The core accepts the game data file from the
`fheroes2` folder and locates the accompanying `DATA`, `MAPS`, and `GAMES`
directories beside it.
