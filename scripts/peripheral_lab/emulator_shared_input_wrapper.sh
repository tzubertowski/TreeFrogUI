#!/bin/sh
# Test-only: isolated original ROM + unchanged Gambatte in owned VM.
cd /work/synthetic_roms_v1 || exit 2
exec timeout 20 qemu-mipsel -cpu 74Kf /work/mips_emulator_libs_v1/ld.so.1 \
    --library-path /work/mips_emulator_libs_v1 /work/libretro-smoke-mips-v4 \
    /work/gambatte_libretro.so /work/synthetic_roms_v1/input_test.gb --shared-input
