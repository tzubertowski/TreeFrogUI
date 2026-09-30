# J2ME / MIDP 2.0

Create `roms/j2me/` and copy `.jar` or `.jad` games there. TreeFrogUI uses
`j2me_libretro.so`, built by `build_all.sh` from FroggyKVM's `sf3000` target.

FroggyKVM also needs its CLDC/MIDP classes archive. Copy the upstream
`classes.zip` to `bios/classes.zip`; it is intentionally not included in the
source repository or release because it is a separate generated/runtime asset.

The core renders a 320×240 J2ME framebuffer; picoarch handles scaling and the
device-specific display path.
