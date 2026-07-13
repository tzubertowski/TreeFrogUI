#!/bin/bash
# Clone all libretro core sources for SF3000 multicore.
# Uses tzubertowski forks where improvements exist, standard libretro repos otherwise.
set -e
cd "$(dirname "$0")/cores"

clone() {
    local dir="$1"
    local url="$2"
    local branch="${3:-}"
    if [ -d "$dir/.git" ]; then
        echo "SKIP $dir (already cloned)"
    else
        echo "Cloning $dir..."
        if [ -n "$branch" ]; then
            git clone --depth=1 --branch "$branch" "$url" "$dir"
        else
            git clone --depth=1 "$url" "$dir"
        fi
    fi
}

# ── tzubertowski forks (improved/MIPS-optimised) ──────────────────────────────
clone fceumm          https://github.com/tzubertowski/libretro-fceumm
clone QuickNES_Core   https://github.com/libretro/QuickNES_Core
clone snes9x2005      https://github.com/tzubertowski/snes9x2005
clone snes9x2002      https://github.com/tzubertowski/snes9x2002
clone snes9x2010      https://github.com/libretro/snes9x2010
clone libretro-gambatte https://github.com/tzubertowski/libretro-gambatte
clone gpsp            https://github.com/tzubertowski/gpsp_multicore
clone gpsp_upstream   https://github.com/libretro/gpsp
clone libretro-frodo  https://github.com/tzubertowski/libretro-frodo
clone fake-08         https://github.com/tzubertowski/fake-08         sf3000
clone libretro-blueMSX https://github.com/tzubertowski/libretro-blueMSX
clone Ardens          https://github.com/tiberiusbrown/Ardens          # Arduboy (fast custom AVR core)

# ── standard libretro repos ───────────────────────────────────────────────────
clone picodrive        https://github.com/libretro/picodrive
clone mgba             https://github.com/libretro/mgba
clone Genesis-Plus-GX  https://github.com/libretro/Genesis-Plus-GX
clone tyrquake         https://github.com/libretro/tyrquake
clone libretro-prboom  https://github.com/libretro/libretro-prboom
clone mame2000         https://github.com/libretro/mame2000-libretro
clone fbalpha2012_cps1   https://github.com/libretro/fbalpha2012_cps1
clone fbalpha2012_cps2   https://github.com/libretro/fbalpha2012_cps2
clone fbalpha2012_cps3   https://github.com/libretro/fbalpha2012_cps3
clone fbalpha2012_neogeo https://github.com/libretro/fbalpha2012_neogeo
clone mame2003-plus-libretro https://github.com/libretro/mame2003-plus-libretro
clone FBNeo            https://github.com/libretro/FBNeo
clone stella2014       https://github.com/libretro/stella2014-libretro
clone prosystem        https://github.com/libretro/prosystem-libretro
clone nestopia         https://github.com/libretro/nestopia
clone libretro-tgbdual https://github.com/libretro/tgbdual-libretro
clone Gearboy          https://github.com/drhelius/Gearboy
clone PokeMini         https://github.com/libretro/PokeMini
clone vba-next         https://github.com/libretro/vba-next
clone cannonball       https://github.com/libretro/cannonball
clone ecwolf           https://github.com/libretro/ecwolf
clone libretro-pocketcdg https://github.com/libretro/libretro-pocketcdg
clone RACE             https://github.com/libretro/RACE
clone libretro-beetle-pce-fast https://github.com/libretro/beetle-pce-fast-libretro
clone libretro-beetle-wswan    https://github.com/libretro/beetle-wswan-libretro
clone libretro-beetle-lynx     https://github.com/libretro/beetle-lynx-libretro
clone libretro-beetle-vb       https://github.com/libretro/beetle-vb-libretro
clone libretro-beetle-supergrafx https://github.com/libretro/beetle-supergrafx-libretro
clone libretro-beetle-pcfx     https://github.com/libretro/beetle-pcfx-libretro
clone libretro-handy   https://github.com/libretro/libretro-handy
clone a5200            https://github.com/libretro/a5200
clone libretro-81      https://github.com/libretro/81-libretro
clone libretro-fuse    https://github.com/libretro/fuse-libretro
clone libretro-vecx    https://github.com/libretro/libretro-vecx
clone potator          https://github.com/libretro/potator
clone theodore         https://github.com/Zlika/theodore
clone Gearcoleco       https://github.com/drhelius/Gearcoleco
clone Gearsystem       https://github.com/drhelius/Gearsystem
clone FreeChaF         https://github.com/libretro/FreeChaF
clone FreeIntv         https://github.com/libretro/FreeIntv
clone libretro-gme     https://github.com/libretro/libretro-gme
clone libretro-cap32   https://github.com/libretro/libretro-cap32
clone libretro-crocods https://github.com/libretro/crocods-core
clone arduous          https://github.com/libretro/arduous
clone libretro-vice    https://github.com/libretro/vice-libretro
clone libretro-gw      https://github.com/libretro/gw-libretro
clone libretro-xrick   https://github.com/libretro/xrick-libretro
clone REminiscence     https://github.com/libretro/REminiscence
clone libretro-prboom  https://github.com/libretro/libretro-prboom
clone libretro-o2em    https://github.com/libretro/o2em-libretro
clone libretro-nxengine https://github.com/libretro/nxengine-libretro
clone libretro-jumpnbump https://github.com/libretro/jumpnbump-libretro
clone lowres-nx        https://github.com/timoinutilis/lowres-nx
clone retro8           https://github.com/libretro/retro8
clone gong             https://github.com/libretro/gong
clone jaxe             https://github.com/libretro/jaxe
clone libretro-quasi88 https://github.com/libretro/quasi88-libretro
clone libretro-doublecherryGB https://github.com/DoubleCherry/doublecherryGB-libretro
clone libretro-geolith https://github.com/libretro/geolith-libretro
clone libretro-xmil    https://github.com/libretro/xmil-libretro
clone vaporspec        https://github.com/libretro/vaporspec
clone libretro-atari800 https://github.com/libretro/libretro-atari800

# ── pico-286 standalone DOS/PC emulator (8086-286) ──────────────────────────
clone pico-286         https://github.com/xrip/pico-286

# ── TIC-80 fantasy console (CMake build; submodules fetched in build_all.sh) ─
clone TIC-80           https://github.com/nesbox/TIC-80

# ── angree SF2000 ports (Amiga/Atari ST) ────────────────────────────────────
clone sf2000-uae-amiga-emulator          https://github.com/angree/sf2000-uae-amiga-emulator
clone sf2000-atarist-emulator            https://github.com/angree/sf2000-atarist-emulator

echo ""
echo "All cores cloned."
