#!/bin/bash
# Build the customized FreeDOS boot floppy for pico286 from the stock FreeDOS 1.4
# "Floppy Edition" x86BOOT.img. Removes the language menu, auto-runs the launched
# game (RUN.BAT / first .EXE/.COM on C: then B:), and loads the CTMOUSE driver
# so INT33 mouse games work.
#
# Usage:  ./make_freedos.sh <stock_x86BOOT.img> [out.img]
#         (download FreeDOS 1.4 Floppy Edition: https://www.freedos.org/download/
#          and pass 144m/x86BOOT.img)
#
# Output goes to cubegm/bios/x86BOOT.img by default.
set -e
SRC="$1"; OUT="${2:-sdcard/cubegm/bios/x86BOOT.img}"
[ -f "$SRC" ] || { echo "usage: $0 <stock_x86BOOT.img> [out.img]"; exit 1; }
command -v mcopy >/dev/null || { echo "need mtools"; exit 1; }
export MTOOLS_SKIP_CHECK=1
T=$(mktemp -d)

cat > "$T/FDCONFIG.SYS" <<'EOF'
LASTDRIVE=Z
BUFFERS=20
FILES=40
SHELL=\FREEDOS\BIN\COMMAND.COM \FREEDOS\BIN /E:2048 /P=\FDAUTO.BAT
EOF

cat > "$T/FDAUTO.BAT" <<'EOF'
@echo off
SET DOSDIR=A:\FREEDOS
SET PATH=A:\FREEDOS\BIN
A:\CTMOUSE.EXE /S >nul
if exist C:\*.* goto usec
if exist B:\*.* goto useb
echo No game disk found - drop a game in roms/pico286 and relaunch.
goto theend
:usec
C:
goto run
:useb
B:
:run
cd \
if exist RUN.BAT goto rbat
if exist AUTORUN.BAT goto abat
for %%E in (*.EXE) do %%E
for %%E in (*.COM) do %%E
goto theend
:rbat
call RUN.BAT
goto theend
:abat
call AUTORUN.BAT
:theend
EOF

# CTMOUSE: use BIN/CTMOUSE.EXE from the FreeDOS ctmouse package if not cached.
CTM="$T/CTMOUSE.EXE"
if [ -f ctmouse/CTMOUSE.EXE ]; then cp ctmouse/CTMOUSE.EXE "$CTM"
else
  echo "fetching CTMOUSE..."
  curl -fsSL -o "$T/ctmouse.zip" "https://www.ibiblio.org/pub/micro/pc-stuff/freedos/files/repositories/1.3/base/ctmouse.zip"
  unzip -o -j "$T/ctmouse.zip" BIN/CTMOUSE.EXE -d "$T" >/dev/null
fi

mkdir -p "$(dirname "$OUT")"
cp "$SRC" "$OUT"
mdel -i "$OUT" ::FDCONFIG.SYS ::FDAUTO.BAT ::SETUP.BAT 2>/dev/null || true
mcopy -i "$OUT" "$T/FDCONFIG.SYS" ::FDCONFIG.SYS
mcopy -i "$OUT" "$T/FDAUTO.BAT"   ::FDAUTO.BAT
mcopy -i "$OUT" "$CTM"            ::CTMOUSE.EXE
rm -rf "$T"
echo "Wrote $OUT (FreeDOS auto-boot + CTMOUSE)."
