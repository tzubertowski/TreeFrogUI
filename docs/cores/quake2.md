# Quake II (vitaquake2)

← [back to README](../../README.md)

`quake2` runs Quake II via the [vitaquake2](https://github.com/fgsfdsfgs/vitaquake2) libretro core (software renderer - these handhelds have no GPU). It's **heavy** for the hardware: expect **~25-40 fps** at 320×240. It plays, but it's not smooth.

## Folder structure (important)

The game data goes in a **`baseq2/` subfolder**, not loose in `roms/quake2/`:

```
roms/quake2/baseq2/pak0.pak
```

> [!IMPORTANT]
> The `baseq2/` subdirectory is **required**. The core derives the game's base
> directory from the pak's parent folder - a flat `roms/quake2/pak0.pak` fails
> with *"Error: Quake II (baseq2) game files required"*.

## Getting the game data

- **Shareware demo** (free, legal): the id Software demo `q2-314-demo-x86.exe` (a self-extracting zip) contains `Install/Data/baseq2/pak0.pak`. Mirror: [id Software FTP archive](https://ftp.gwdg.de/pub/misc/ftp.idsoftware.com/idstuff/quake2/). Extract and copy that `pak0.pak` to `roms/quake2/baseq2/`.
- **Retail**: copy `pak0.pak` (and `pak1.pak`, `pak2.pak` if you have them) from your Quake II CD/GOG/Steam install's `baseq2/` folder.

**Mission packs** also work - put their data in their own subfolders next to `baseq2/`: `xatrix/` (The Reckoning), `rogue/` (Ground Zero), `zaero/`.

## Controls

Quake II normally needs an analog stick to move; these handhelds don't have one, so movement is remapped to the **D-pad**:

- **D-pad UP / DOWN** - move forward / back
- **D-pad LEFT / RIGHT** - turn left / right
- Face + shoulder buttons - fire, jump, weapon switch, etc. (standard retropad)

So it's playable without an analog stick, though turning-by-dpad is coarse.

## Performance

The bottleneck is the **CPU software rasterizer**, not the frontend - the game logic is cheap, drawing is the wall. There's no magic setting that makes it 60fps on this CPU. Lower in-core resolution or frameskip options (if exposed) trade quality for a steadier feel.
