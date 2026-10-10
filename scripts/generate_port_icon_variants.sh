#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MASTER="$ROOT/assets/system-icons"
PACKS="$ROOT/assets/icon-packs"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

systems='j2me openclaw classicube mcpe diablo nds'

label_for()
{
    case "$1" in
        j2me) echo 'JAVA GAMES' ;;
        openclaw) echo 'CAPTAIN CLAW' ;;
        classicube) echo 'CLASSICUBE' ;;
        mcpe) echo 'MINECRAFT PE' ;;
        diablo) echo 'DIABLO' ;;
        nds) echo 'NINTENDO DS' ;;
    esac
}

for name in $systems; do
    src="$MASTER/$name.png"
    [ -f "$src" ] || { echo "Missing master icon: $src" >&2; exit 1; }

    # Arcticons: thin white monochrome line art.
    convert "$src" -channel A -threshold 8% +channel -colorspace gray \
        -fill none -stroke white -strokewidth 2 -resize '220x88>' \
        "$PACKS/Arcticons_by_joelchrono/$name.png"

    # Cosy: soft grey hardware-like shading while retaining small color cues.
    convert "$src" -resize '220x88>' -modulate 90,55,100 \
        -channel RGB -level 8%,92% +channel \
        "$PACKS/Cosy_by_KyleBing/$name.png"

    # CyberOnion: near-black body with a hot-magenta neon edge.
    convert "$src" -resize '220x88>' "$TMP/base.png"
    convert "$TMP/base.png" -alpha extract -edge 1 -threshold 18% "$TMP/edge.png"
    convert "$TMP/base.png" -fill '#080013' -colorize 92 \
        "$TMP/edge.png" -alpha off -compose CopyOpacity -composite \
        -fill '#ff006e' -colorize 70 \
        "$PACKS/CyberOnion_by_Aemiii91/$name.png"

    # Dot-art: deliberately chunky, compact isometric-era pixel treatment.
    convert "$src" -resize '60x48>' -dither None -colors 16 \
        -filter point -resize '120x96>' \
        "$PACKS/Dot-art_by_Yoshi-kun/$name.png"

    # Hakchi: restrained grey pixel art with the pack's red accent.
    convert "$src" -resize '60x48>' -colorspace gray -dither None -colors 8 \
        -fill '#b31b2c' -colorize 12 -filter point -resize '120x96>' \
        "$PACKS/Hakchi_Pixel_Art_by_faustbear/$name.png"

    # NSO: red square card, compact emblem, white system label.
    convert -size 130x130 xc:'#e60012' \
        \( "$src" -resize '100x78>' \) -gravity north -geometry +0+6 -composite \
        -gravity south -fill white -stroke none -font DejaVu-Sans-Bold -pointsize 12 \
        -annotate +0+8 "$(label_for "$name")" \
        "$PACKS/NSO_by_Cheetashock/$name.png"

    # Onion PS text set: flat white mark on transparency.
    convert "$src" -resize '118x96>' -channel A -threshold 8% +channel \
        -fill white -colorize 100 \
        "$PACKS/Onion_PS_Text_Icons_by_hanessh4/$name.png"

    # Jeltron Pixel: low-color outlined pixel icon.
    convert "$src" -resize '64x48>' -dither None -colors 7 \
        -filter point -resize '128x96>' \
        "$PACKS/Pixel_by_Jeltron/$name.png"

    # Dreambrace silhouettes: identical geometry in pack-specific polarity.
    convert "$src" -resize '220x88>' -channel A -threshold 8% +channel \
        -fill black -colorize 100 \
        "$PACKS/Silhouette_Black_by_Dreambrace/$name.png"
    convert "$src" -resize '220x88>' -channel A -threshold 8% +channel \
        -fill white -colorize 100 \
        "$PACKS/Silhouette_White_by_Dreambrace/$name.png"
done

echo "Generated 6 icons for all 10 shipped icon packs."
