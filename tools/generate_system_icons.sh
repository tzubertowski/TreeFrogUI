#!/bin/sh
# Build TreeFrogUI's System View pack from KyleBing's Cosy console icons.
# Usage: ./tools/generate_system_icons.sh /path/to/retro-game-console-icons
set -eu

SOURCE_ROOT="${1:?pass the retro-game-console-icons directory}"
TRIMUI="$SOURCE_ROOT/series_trimui/300w@1x"
MIYOO="$SOURCE_ROOT/series_miyoo"
OUTPUT="$(dirname "$0")/../assets/system-icons"

if command -v magick >/dev/null 2>&1; then
    IM=magick
elif command -v convert >/dev/null 2>&1; then
    IM=convert
else
    echo "ImageMagick is required" >&2
    exit 1
fi
test -d "$TRIMUI" || {
    echo "Cosy console icons not found: $TRIMUI" >&2
    exit 1
}
mkdir -p "$OUTPUT"
find "$OUTPUT" -maxdepth 1 -type f -name '*.png' -delete

# TreeFrog ROM folder -> Cosy source. Alternate cores for the same platform
# intentionally share art; software-only systems use Cosy's Ports/Video cards.
while read -r folder source; do
    [ -n "$folder" ] || continue
    case "$source" in
        menu/*) input="$MIYOO/menu_main/${source#menu/}.png" ;;
        miyoo/*) input="$MIYOO/132w@1x/${source#miyoo/}@132w.png" ;;
        *) input="$TRIMUI/$source.png" ;;
    esac
    if [ ! -f "$input" ]; then
        echo "missing: $folder <- $source" >&2
        continue
    fi
    "$IM" "$input" -trim +repage -resize '160x130>' -strip "$OUTPUT/$folder.png"
done <<'EOF'
2048 PORTS
32x SEGA32X
a26 ATARI2600
a5200 ATARI5200
a78 ATARI7800
a800 ATARI800
amiga AMIGA
amstrad CPC
amstradb cpc-alt
arduboy ARDUBOY
arduous ARDUBOY
bk PORTS
c64 C64
c64f C64
c64fc C64
c64sc C64
cavestory CAVESTORY
cdg VIDEOS
chip8 PORTS
col COLECO
cps1 CPS1
cps2 CPS2
cps3 CPS3
dblcherrygb GB
fake08 PORTS
favourites menu/ic-favorite-f
fcf CHANNELF
fds FDS
flashback FLASHBACK
gb GB
gba GBA
gbac GBA
gbav GBA
gbb GB
gbgb GB
geolith NEOGEO
gg GG
gme VIDEOS
gong ARCADE
gpgx MD
gw GW
int INTELLIVISION
jnb PORTS
lnx LYNX
lowres-nx LOWRESNX
m2k MAME
menu PORTS
mgba GBA
mp3 VIDEOS
mrboom PORTS
msx MSX
neogeo NEOGEO
nes FC
nesq FC
nest FC
ngpc NGP
nxb PORTS
o2em VIDEOPAC
outrun CANNONBALL
pc8800 PC88
pce PCE
pcesgx PCE
pcfx PCFX
pico286 DOS
pico8 PORTS
pokem POKEMINI
prboom DOOM
ps1 PS
ps1r PS
quake TYRQUAKE
quake2 TYRQUAKE
retro8 PORTS
rockbox VIDEOS
save PORTS
sega MD
segacd SEGACD
snes SFC
snes02 SFC
spec ZXS
thom THOMSON
tic80 TIC
vapor PORTS
vb VB
vec VECTREX
vic20 VIC20
videos VIDEOS
wolf3d miyoo/wolf
wsv WS
wswan WS
x48 TI83
xmil X68000
xrick XRICK
zx81 ZXS
EOF

echo "Generated $(find "$OUTPUT" -maxdepth 1 -type f -name '*.png' | wc -l) Cosy icons in $OUTPUT"
