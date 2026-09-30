# J2ME / MIDP 2.0

Create `roms/j2me/` and copy `.jar` or `.jad` games there. TreeFrogUI uses
`j2me_libretro.so`, built by `build_all.sh` from FroggyKVM's `sf3000` target.

FroggyKVM needs its bundled CLDC/MIDP classes archive at
`cubegm/bios/classes.zip`; release builds include it automatically.

The core renders a 320×240 J2ME framebuffer; picoarch handles scaling and the
device-specific display path.
