# Arcade (MAME / FB Alpha / Neo Geo)

← [back to README](../../README.md)

Arcade games are `.zip` files of a romset. **Keep them zipped** - the core reads the zip directly, do not extract.

| Folder | Core | Romset it needs |
|---|---|---|
| `cps1` | FB Alpha 2012 | Capcom **CPS-1** games |
| `cps2` | FB Alpha 2012 | Capcom **CPS-2** games |
| `cps3` | FB Alpha 2012 | Capcom **CPS-3** games (experimental - CPS-3 emulation is heavy, expect low fps) |
| `neogeo` | FB Alpha 2012 | **Neo Geo** games (also needs `neogeo.zip` BIOS, see note below) |
| `m2k` | MAME 2000 | misc arcade, **MAME 0.37b5** romset |

> [!IMPORTANT]
> **Romsets are version-locked.** Each core only loads ROMs from the matching set:
> the `cps1`/`cps2`/`neogeo` folders need a **FB Alpha 2012** romset, and `m2k`
> needs a **MAME 0.37b5** romset. A zip from a different MAME/FBNeo version will
> **fail to load** even if the game name matches - this is the #1 cause of arcade
> ROMs not working. Neo Geo games also need the **`neogeo.zip`** BIOS. Put it in
> **`roms/neogeo/`** (next to the games). Keeping a copy in **`cubegm/bios/`** too
> does no harm if you are unsure.

Pick the folder by hardware: Street Fighter II etc. → `cps1`, Marvel vs Capcom etc.
→ `cps2`, Metal Slug/KOF etc. → `neogeo`. For Neo Geo you can also use the dedicated
`geolith` core. Heavy CPS-2/Neo Geo titles may run slow on this CPU.
