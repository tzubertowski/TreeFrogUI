# Virtual Boy

Put Virtual Boy games in `roms/vb/`. TreeFrogUI prefers [Red Viper for Libretro](https://github.com/tzubertowski/libretro-red-viper/tree/port/mips-libretro) when its core is installed. It falls back to Beetle VB on cards without Red Viper. Existing core assignments take precedence, so clear a Virtual Boy core override if you want TreeFrogUI to choose automatically.

## Install Red Viper

Check out the `port/mips-libretro` branch of the fork and build it with the TreeFrogUI MIPS SDK. From the fork checkout, run:

```sh
git submodule update --init source/common/inih
make -f Makefile.mipsel-libretro NATIVE=1 MIPS_PREFIX=/path/to/sdk/opt/ext-toolchain/bin/mips-mti-linux-gnu- SYSROOT=/path/to/sdk/mipsel-buildroot-linux-gnu/sysroot
```

Copy `red-viper-mipsel_libretro.so` to `cubegm/cores/` on the SD card. Keep `mednafen_vb_libretro.so` if you want to use Beetle VB as an alternative.

The Red Viper Libretro shim is experimental and has been tested on the R36SX. It does not include Libretro core options or savestates yet. Red Viper binaries are not bundled while redistribution permission is being clarified.
