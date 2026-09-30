# J2ME / MIDP 2.0

Create `roms/j2me/` and copy `.jar` or `.jad` games there. TreeFrogUI uses
`j2me_libretro.so`, built by `build_all.sh` from FroggyKVM's `sf3000` target.

FroggyKVM needs its bundled CLDC/MIDP classes archive at
`cubegm/bios/classes.zip`; release builds include it automatically.

MIDI uses FluidLite with `cubegm/bios/Roland_SC-55.sf2` when present. Release
staging copies that SoundFont from `cores/scummvm/dists/soundfonts/`; without
it, the core falls back to its basic built-in synth.

The core renders a 320×240 J2ME framebuffer; picoarch handles scaling and the
device-specific display path.
