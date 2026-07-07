# Commodore Amiga (UAE)

← [back to README](../../README.md)

`amiga` runs the [angree/sf2000-uae-amiga-emulator](https://github.com/angree/sf2000-uae-amiga-emulator) core (a stripped-down UAE4ALL port). Games go in `roms/amiga/` as `.adf` or `.adz` disk images (a `.zip` of one works too - it's unzipped on the fly, same as arcade cores).

**BIOS required: a Kickstart ROM.** Amiga hardware can't boot without one, and it's copyrighted (not something this project can ship). Drop your own dump in `cubegm/bios/`, named exactly:

| Filename | Kickstart version |
|---|---|
| `kick13.rom` | 1.3 - **recommended**, best compatibility |
| `kick20.rom` | 2.0 |

Kickstart 3.0/3.1 is not supported by this core. If you don't have a real Amiga to dump your own ROM from, Cloanto's [Amiga Forever](https://www.amigaforever.com/) is the legitimate commercial source.

**Multi-disk games:** **L** / **R** switch to the previous/next disk.

**Mouse mode:** hold **L+R** for 3 seconds to toggle. D-pad moves the cursor, A = left click, B = right click.
