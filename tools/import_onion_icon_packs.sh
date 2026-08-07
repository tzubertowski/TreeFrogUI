#!/bin/sh
# Import the official Onion catalog's standalone icon packs for TreeFrogUI.
# Usage: ./tools/import_onion_icon_packs.sh /path/to/OnionUI-Themes
set -eu

ROOT="${1:?pass an OnionUI/Themes checkout}"
OUTPUT="$(dirname "$0")/../assets/icon-packs"
test -d "$ROOT/icons" || { echo "Onion icons directory not found" >&2; exit 1; }
if command -v magick >/dev/null 2>&1; then IM=magick; else IM=convert; fi
mkdir -p "$OUTPUT"

while IFS='|' read -r target source; do
    [ -n "$target" ] || continue
    case "$source" in
        themes/*) src="$ROOT/$source" ;;
        *) src="$ROOT/icons/$source" ;;
    esac
    test -d "$src" || { echo "missing pack: $source" >&2; continue; }
    out="$OUTPUT/$target"
    rm -rf "$out"
    mkdir -p "$out"

    while read -r folder candidates; do
        [ -n "$folder" ] || continue
        input=""
        oldifs=$IFS; IFS=','
        for candidate in $candidates; do
            input=$(find "$src" -maxdepth 1 -type f -iname "$candidate.png" -print -quit)
            [ -z "$input" ] || break
        done
        IFS=$oldifs
        [ -n "$input" ] || continue
        case "$target" in
            Dot-art*|Hakchi*|Pixel*)
                "$IM" "$input" -trim +repage -filter point -resize '160x130>' -strip "$out/$folder.png" ;;
            *)
                "$IM" "$input" -trim +repage -filter Lanczos -resize '160x130>' -strip "$out/$folder.png" ;;
        esac
    done <<'MAP'
2048 ports
32x 32X
a26 atari
a5200 5200
a78 7800
a800 atari800,atari
amiga amiga
amstrad cpc
amstradb cpc
arduboy arduboy,ports
arduous arduboy,ports
bk ports
c64 c64
c64f c64
c64fc c64
c64sc c64
cavestory cavestory,ports
cdg ffplay,ports
chip8 ports
col col
cps1 cps1,arcade
cps2 cps2,arcade
cps3 cps3,arcade
dblcherrygb gb
fake08 ports
fcf fairchild
fds fds,fc
flashback flashback,ports
gb gb,gbc
gba gba
gbac gba
gbav gba
gbb gb,gbc
gbgb gb,gbc
geolith neogeo,arcade
gg gg
gme ffplay,ports
gong arcade,mame
gpgx md
gw gw
int itv
jnb ports
lnx lynx
lowres-nx lowresnx,ports
m2k mame,arcade
menu ports
mgba gba
mp3 ffplay,ports
mrboom ports
msx msx
neogeo neogeo,arcade
nes fc
nesq fc
nest fc
ngpc ngpc,ngp
nxb ports
o2em ody
outrun cannonball,ports,arcade
pc8800 pc88,dos,ports
pce pce
pcesgx sgfx,pce
pcfx pcfx,pce
pico286 dos,ports
pico8 ports
pokem poke
prboom doom,ports
ps1 ps
ps1r ps
quake quake,ports
quake2 quake,ports
retro8 ports
rockbox ffplay,ports
save ports
sega md
segacd segacd,md
snes sfc
snes02 sfc
spec zxs
thom thomson,ports
tic80 tic,ports
vapor ports
vb vb
vec vectrex
vic20 vic20,c64
videos videos,ffplay,ports
wolf3d wolf,ports
wsv ws,wsc
wswan ws,wsc
x48 ti83,ports
xmil x68000,ports
xrick xrick,ports
zx81 zxs
MAP

    upstream=$(find "$src" -maxdepth 1 -type f -iname 'readme*' -print -quit)
    [ -z "$upstream" ] || cp "$upstream" "$out/UPSTREAM_README.txt"
    echo "$(find "$out" -maxdepth 1 -type f -name '*.png' | wc -l) icons: $target"
done <<'PACKS'
Arcticons_by_joelchrono|Arcticons by joelchrono
Cosy_by_KyleBing|Cosy by KyleBing
CyberOnion_by_Aemiii91|themes/CyberOnion (2-pack) by Aemiii91/CyberOnion by Aemiii91/icons
Dot-art_by_Yoshi-kun|Dot-art by Yoshi-kun
Hakchi_Pixel_Art_by_faustbear|Hakchi Pixel Art by faustbear
NSO_by_Cheetashock|NSO by Cheetashock
Onion_PS_Text_Icons_by_hanessh4|Onion PS Text Icons by hanessh4
Pixel_by_Jeltron|Pixel by Jeltron
Silhouette_Black_by_Dreambrace|Silhouette Black by Dreambrace
Silhouette_White_by_Dreambrace|Silhouette White by Dreambrace
PACKS
