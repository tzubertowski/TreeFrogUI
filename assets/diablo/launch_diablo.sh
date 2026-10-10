#!/bin/sh
set -eu

# TreeFrogUI passes the selected .diablo marker as argv[1]. DevilutionX uses
# its working directory for the MPQ files, so deliberately ignore that marker.
cd /mnt/sdcard/roms/diablo
{
    echo "=== Diablo startup $(date 2>/dev/null) ==="
    echo "pid=$$ cwd=$(pwd)"
    ls -lh DIABDAT.MPQ devilutionx.mpq 2>&1
} >> /mnt/sdcard/cubegm/logs/diablo_start.log 2>&1
# The firmware can export an invalid locale and an unwritable desktop HOME;
# DevilutionX's libc/SDL startup then aborts or appears to hang while creating
# its preference path. Keep all runtime state with the game data instead.
export HOME=/mnt/sdcard/roms/diablo
export LC_ALL=C
export LANG=C
# SDL 1.2 otherwise tries to open /dev/mouse during SDL_Init. The SF3000 has
# no mouse device; controller input is provided through the SDL keyboard/joypad
# path, so disable only SDL's optional mouse backend.
export SDL_NOMOUSE=1
export SDL_MOUSEDEV=/dev/null
export SDL_MOUSEDRV=none
# Standalone binaries do not inherit PicoArch's library path. Use the same
# SDL build as the rest of TreeFrogUI; the firmware SDL opens /dev/mouse.
export LD_LIBRARY_PATH=/mnt/sdcard/cubegm/lib:/lib:/usr/lib
# The SF3000 build must not enter the default Diablo/Hellfire chooser, and
# its MIPS CPU cannot decode the startup cinematic at a useful speed.
{
    echo "=== Diablo runtime $(date 2>/dev/null) ==="
    echo "binary=/mnt/sdcard/cubegm/devilutionx"
    echo "args=--verbose --diablo -n"
} >> /mnt/sdcard/cubegm/logs/diablo_runtime.log 2>&1
exec /mnt/sdcard/cubegm/devilutionx --verbose --diablo -n >> /mnt/sdcard/cubegm/logs/diablo_runtime.log 2>&1
