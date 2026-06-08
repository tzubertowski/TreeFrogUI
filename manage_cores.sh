#!/bin/bash
# Manage libretro core sources for SF3000 multicore.
# Uses tzubertowski forks where improvements exist, standard libretro repos otherwise.
#
# Usage:
#   ./manage_cores.sh clone    - Clone all core repositories
#   ./manage_cores.sh update   - Update all existing core repositories
#   ./manage_cores.sh          - Show this help message
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create cores directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/cores"

# Change to cores directory
cd "$SCRIPT_DIR/cores"

# Show help message
show_help() {
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  clone    - Clone all core repositories"
    echo "  update   - Update all existing core repositories"
    echo ""
    echo "Examples:"
    echo "  $0 clone   # Clone all cores"
    echo "  $0 update  # Update all existing cores"
    exit 0
}

# Clone a repository
clone_repo() {
    local dir="$1"
    local url="$2"
    if [ -d "$dir/.git" ]; then
        echo "SKIP $dir (already cloned)"
    else
        echo "Cloning $dir..."
        GIT_TERMINAL_PROMPT=0 git clone --depth=1 "$url" "$dir" || (echo "Failed to clone $dir $url" && exit 1)
    fi
}

# Update a repository
update_repo() {
    local dir="$1"
    local url="$2"
    if [ -d "$dir/.git" ]; then
        echo "Updating $dir..."
        cd "$dir"
        git fetch origin
        git reset --hard origin/HEAD
        cd ..
    else
        echo "SKIP $dir (not cloned, use 'clone' command first)"
    fi
}

# Process repositories based on command
process_repos() {
    local action="$1"
    
    # ── tzubertowski forks (improved/MIPS-optimised) ──────────────────────────────
    $action fceumm          https://github.com/tzubertowski/libretro-fceumm
    $action QuickNES_Core   https://github.com/tzubertowski/QuickNES_Core
    $action snes9x2005      https://github.com/tzubertowski/snes9x2005
    $action snes9x2002      https://github.com/tzubertowski/snes9x2002
    $action libretro-gambatte https://github.com/tzubertowski/libretro-gambatte
    $action gpsp            https://github.com/tzubertowski/gpsp_multicore
    $action libretro-frodo  https://github.com/tzubertowski/libretro-frodo
    $action fake-08         https://github.com/tzubertowski/fake-08
    $action libretro-blueMSX https://github.com/tzubertowski/libretro-blueMSX

    # ── standard libretro repos ───────────────────────────────────────────────────
    $action picodrive        https://github.com/libretro/picodrive
    $action mgba             https://github.com/libretro/mgba
    $action Genesis-Plus-GX  https://github.com/libretro/Genesis-Plus-GX
    $action tyrquake         https://github.com/libretro/tyrquake
    $action libretro-prboom  https://github.com/libretro/libretro-prboom
    $action mame2000         https://github.com/libretro/mame2000-libretro
    $action stella2014       https://github.com/libretro/stella2014-libretro
    $action prosystem        https://github.com/libretro/prosystem-libretro
    $action nestopia         https://github.com/libretro/nestopia
    $action libretro-tgbdual https://github.com/libretro/tgbdual-libretro
    $action Gearboy          https://github.com/drhelius/Gearboy
    $action PokeMini         https://github.com/libretro/PokeMini
    $action vba-next         https://github.com/libretro/vba-next
    $action cannonball       https://github.com/libretro/cannonball
    $action ecwolf           https://github.com/libretro/ecwolf
    $action libretro-pocketcdg https://github.com/libretro/libretro-pocketcdg
    $action RACE             https://github.com/libretro/RACE
    $action libretro-beetle-pce-fast https://github.com/libretro/beetle-pce-fast-libretro
    $action libretro-beetle-wswan    https://github.com/libretro/beetle-wswan-libretro
    $action libretro-beetle-lynx     https://github.com/libretro/beetle-lynx-libretro
    $action libretro-beetle-vb       https://github.com/libretro/beetle-vb-libretro
    $action libretro-beetle-supergrafx https://github.com/libretro/beetle-supergrafx-libretro
    $action libretro-beetle-pcfx     https://github.com/libretro/beetle-pcfx-libretro
    $action libretro-handy   https://github.com/libretro/libretro-handy
    $action a5200            https://github.com/libretro/a5200
    $action libretro-81      https://github.com/libretro/81-libretro
    $action libretro-fuse    https://github.com/libretro/fuse-libretro
    $action libretro-vecx    https://github.com/libretro/libretro-vecx
    $action potator          https://github.com/libretro/potator
    $action theodore         https://github.com/Zlika/theodore
    $action Gearcoleco       https://github.com/drhelius/Gearcoleco
    $action Gearsystem       https://github.com/drhelius/Gearsystem
    $action FreeChaF         https://github.com/libretro/FreeChaF
    $action FreeIntv         https://github.com/libretro/FreeIntv
    $action libretro-gme     https://github.com/libretro/libretro-gme
    $action libretro-cap32   https://github.com/libretro/libretro-cap32
    $action libretro-crocods https://github.com/libretro/libretro-crocods
    $action arduous          https://github.com/libretro/arduous
    $action libretro-vice    https://github.com/libretro/vice-libretro
    $action libretro-gw      https://github.com/libretro/gw-libretro
    $action libretro-xrick   https://github.com/libretro/xrick-libretro
    $action REminiscence     https://github.com/libretro/REminiscence
    $action libretro-prboom  https://github.com/libretro/libretro-prboom
    $action libretro-o2em    https://github.com/libretro/libretro-o2em
    $action libretro-nxengine https://github.com/libretro/nxengine-libretro
    $action libretro-jumpnbump https://github.com/libretro/jumpnbump-libretro
    $action lowres-nx        https://github.com/timoinutilis/lowres-nx
    $action retro8           https://github.com/libretro/retro8
    $action gong             https://github.com/libretro/gong
    $action jaxe             https://github.com/kurtjd/jaxe
    $action libretro-quasi88 https://github.com/libretro/quasi88-libretro
    $action libretro-doublecherryGB https://github.com/TimOelrichs/doublecherryGB-libretro
    $action libretro-geolith https://github.com/libretro/geolith-libretro
    $action libretro-xmil    https://github.com/libretro/xmil-libretro
    $action vaporspec        https://github.com/minkcv/vm
    $action libretro-atari800 https://github.com/libretro/libretro-atari800

    # ── angree SF2000 ports (Amiga/Atari ST) ────────────────────────────────────
    $action sf2000-uae-amiga-emulator          https://github.com/angree/sf2000-uae-amiga-emulator
    $action sf2000-atarist-emulator            https://github.com/angree/sf2000-atarist-emulator
}

# Main script logic
case "${1:-}" in
    clone)
        echo "Cloning all cores..."
        process_repos clone_repo
        echo ""
        echo "All cores cloned."
        ;;
    update)
        echo "Updating all cores..."
        process_repos update_repo
        echo ""
        echo "All cores updated."
        ;;
    *)
        show_help
        ;;
esac
