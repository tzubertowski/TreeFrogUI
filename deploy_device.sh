#!/usr/bin/env bash
#
# Guarded in-place TreeFrogUI deployment for supported device cards.
#
# Usage:
#   ./build_release.sh
#   pkexec ./deploy.sh <r36sx|r36hd|sf3000|sf3000hd_nohdmi|sf3500> [payload ...]
#
# With no payload, the complete release plus the selected install_first overlay
# is deployed. Optional development payloads:
#   release, test-games, test-media, perf-test-roms, duke3d-data, undertale-data, openlara-data, vvvvvv, openbor, vvvvvv-data, clean-themes, picoarch, picoarch-hi, frogui, duke3d, butterscotch, picante8, openclaw, dsperate, frogshell, ebook, pcsx4all, pcsx4all-test-game, ps1-bios, pcsx4all-config,
#   tic80, vecx, j2me, j2me-debug, o2em, o2em-test, c64-test, launcher, snesz-comparison,
#   mame2000, mame2000-mslug, mame-test, amstrad-cap32-test
#
# This script never formats a card and never uses rsync --delete.
set -euo pipefail

readonly WORK=/home/tomaszz/sf3000-work
readonly REPO="${TREEFROG_REPO:-$WORK/sf3000_treefrogui}"
readonly OPENBOR="$WORK/OpenBOR-TreeFrogUI"
readonly OPENBOR_GAMES=/home/tomaszz/Roms/openbor
readonly RELEASE="$REPO/release/latest/release"
readonly STAGE="$REPO/sdcard"
readonly OWNER_UID=1000
readonly OWNER_GID=1000

die() {
    echo "deploy-device: $*" >&2
    exit 1
}

usage() {
    cat >&2 <<EOF
usage: $0 <r36sx|r36hd|sf3000|sf3000hd_nohdmi|sf3500> [payload ...]
    payloads: release test-games test-media perf-test-roms duke3d-data undertale-data openlara-data vvvvvv openbor vvvvvv-data clean-themes picoarch picoarch-hi frogui duke3d butterscotch picante8 openclaw dsperate frogshell ebook pcsx4all pcsx4all-test-game ps1-bios pcsx4all-config tic80 vecx j2me j2me-debug o2em o2em-test c64-test launcher snesz-comparison mame2000 mame2000-mslug mame-test amstrad-cap32-test
default:  release
EOF
    exit 2
}

[ "$#" -ge 1 ] || usage

readonly PROFILE="$1"
shift

case "$PROFILE" in
    r36sx)
        readonly EXPECTED_LABEL=R36SX
        readonly EXPECTED_TF_DEVICE=R36SX
        ;;
    r36hd)
        readonly EXPECTED_LABEL=R36HD
        readonly EXPECTED_TF_DEVICE=R36SX
        ;;
    sf3000)
        readonly EXPECTED_LABEL=SF3000
        readonly EXPECTED_TF_DEVICE=SF3000
        ;;
    sf3000hd_nohdmi)
        readonly EXPECTED_LABEL=SF3000HD
        readonly EXPECTED_TF_DEVICE=SF3000
        ;;
    sf3500)
        readonly EXPECTED_LABEL=SF3500
        readonly EXPECTED_TF_DEVICE=SF3500
        ;;
    *) usage ;;
esac

readonly MOUNT="/mnt/treefrog-$PROFILE"
readonly OVERLAY="$RELEASE/install_first/$([ "$PROFILE" = r36hd ] && echo r36sx || echo "$PROFILE")"

if [ "$#" -eq 0 ]; then
    set -- release
fi
readonly -a PAYLOADS=("$@")

for payload in "${PAYLOADS[@]}"; do
    case "$payload" in
        release|test-games|test-media|perf-test-roms|snesz-comparison|duke3d-data|undertale-data|openlara-data|vvvvvv|openbor|vvvvvv-data|clean-themes|picoarch|picoarch-hi|frogui|duke3d|butterscotch|picante8|openclaw|dsperate|frogshell|ebook|pcsx4all|pcsx4all-test-game|ps1-bios|pcsx4all-config|tic80|vecx|j2me|j2me-debug|o2em|o2em-test|c64-test|launcher|mame2000|mame2000-mslug|mame-test|amstrad-cap32-test) ;;
        *) usage ;;
    esac
done

[ "$EUID" -eq 0 ] || die "run through pkexec"

for tool in blkid dirname findmnt fsck.vfat grep lsblk mkdir mktemp mount \
    mountpoint readlink rm rsync sed sha256sum sync umount; do
    command -v "$tool" >/dev/null || die "required command is missing: $tool"
done

validate_release() {
    local path
    for path in \
        "$RELEASE/cubegm" \
        "$RELEASE/frogui" \
        "$RELEASE/roms" \
        "$RELEASE/MD" \
        "$OVERLAY/cubegm/setting.xml" \
        "$OVERLAY/cubegm/cores/libemu_md.so" \
        "$RELEASE/cubegm/cores/openlara_libretro.so" \
        "$RELEASE/cubegm/cores/vvvvvv_libretro.so" \
        "$RELEASE/roms/ports/VVVVVV.sh" \
        "$RELEASE/roms/ports/vvvvvv" \
        "$RELEASE/roms/ports/.res/VVVVVV.png" \
        "$OVERLAY/cubegm/zhijack.sh"; do
        [ -e "$path" ] ||
            die "release is incomplete; missing $path (run ./build_release.sh)"
    done

    grep -q "TF_DEVICE=$EXPECTED_TF_DEVICE" \
        "$OVERLAY/cubegm/zhijack.sh" ||
        die "$PROFILE launcher identity is invalid"
    grep -q 'file="/mnt/sdcard/MD/dummy.md" driver=""' \
        "$OVERLAY/cubegm/setting.xml" ||
        die "$PROFILE autorun overlay is invalid"
}

for payload in "${PAYLOADS[@]}"; do
    [ "$payload" != release ] || validate_release
    if [ "$payload" = snesz-comparison ]; then
        for source in \
            "$REPO/build/snes9x-Z_libretro.so" \
            "$REPO/build/Snes9x-Z.LICENSE" \
            "$REPO/frogui/out/frogui_libretro.so" \
            "/home/tomaszz/Roms/snes/Star Fox (USA) (Rev 2).sfc" \
            "/home/tomaszz/Roms/snes/Donkey Kong Country (USA) (Rev 2).sfc" \
            "/home/tomaszz/Roms/snes/Donkey Kong Country 2 - Diddy's Kong Quest (USA) (En,Fr) (Rev 1).sfc" \
            "/home/tomaszz/Roms/snes/Super Mario World 2 - Yoshi's Island (USA) (Rev 1).sfc" \
            "/home/tomaszz/Roms/snes/F-Zero (USA).sfc" \
            "/home/tomaszz/Roms/snes/Super Mario World (USA).sfc"; do
            [ -s "$source" ] || die "Snes9x-Z comparison input is missing: $source"
        done
    fi
    if [ "$payload" = launcher ]; then
        launcher_src="$OVERLAY/cubegm/zhijack.sh"
        [ -f "$launcher_src" ] || die "profile launcher missing: $launcher_src"
        grep -qx "TF_DEVICE=$EXPECTED_TF_DEVICE" "$launcher_src" ||
            die "$PROFILE launcher identity is invalid"
        ! grep -q 'tf_speaker_open' "$launcher_src" ||
            die "$PROFILE launcher references the standalone speaker helper"
    fi
done

# Resolve only by the selected profile's exact volume label. Both whole-disk
# VFAT images and partitioned replacement cards are supported.
DEV="$(blkid -L "$EXPECTED_LABEL" 2>/dev/null || true)"
[ -n "$DEV" ] || die "card labelled $EXPECTED_LABEL not found"
DEV="$(readlink -f "$DEV")"
case "$DEV" in
    /dev/sd[a-z]|/dev/sd[a-z][0-9]*|/dev/mmcblk[0-9]|/dev/mmcblk[0-9]p[0-9]*) ;;
    *) die "refusing unexpected device path: $DEV" ;;
esac
[ "$(lsblk -dnro RM "$DEV")" = "1" ] || die "$DEV is not removable"
case "$(lsblk -dnro TYPE "$DEV")" in
    disk|part) ;;
    *) die "$DEV is neither a disk nor a partition" ;;
esac
[ "$(lsblk -dnro FSTYPE "$DEV")" = "vfat" ] || die "$DEV is not VFAT"
[ "$(lsblk -dnro LABEL "$DEV")" = "$EXPECTED_LABEL" ] ||
    die "$DEV label changed"

[ ! -L "$MOUNT" ] || die "refusing symlink mountpoint: $MOUNT"
mkdir -p "$MOUNT"

mounted_here=0
cleanup() {
    if [ "$mounted_here" -eq 1 ] && mountpoint -q "$MOUNT"; then
        sync
        umount "$MOUNT"
        mounted_here=0
        echo "Unmounted $DEV; the $EXPECTED_LABEL card is safe to remove."
    fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# Clear desktop/udisks mounts of this exact validated device.
while IFS= read -r old_mount; do
    [ -z "$old_mount" ] || umount "$old_mount"
done < <(findmnt -rn -S "$DEV" -o TARGET)

check_filesystem() {
    local fsck_rc
    echo "Checking the unmounted $EXPECTED_LABEL FAT filesystem..."
    set +e
    fsck.vfat -a "$DEV"
    fsck_rc=$?
    set -e
    [ "$fsck_rc" -le 1 ] ||
        die "fsck.vfat failed with status $fsck_rc"
}

mount_card() {
    if ! mount -t vfat \
        -o rw,uid="$OWNER_UID",gid="$OWNER_GID",fmask=0022,dmask=0022,flush \
        "$DEV" "$MOUNT"; then
        return 1
    fi
    mounted_here=1
}

repair_and_mount() {
    if mountpoint -q "$MOUNT"; then
        umount "$MOUNT"
        mounted_here=0
    fi
    check_filesystem
    mount_card
}

# Dirty FAT can initially report rw and only flip read-only under a large copy.
# Check it while unmounted before every deployment.
check_filesystem

if ! mount_card; then
    echo "Initial mount failed; repairing the validated $EXPECTED_LABEL card."
    repair_and_mount
fi

mount_opts="$(findmnt -rn -S "$DEV" -o OPTIONS)"
case ",$mount_opts," in
    *,rw,*) ;;
    *)
        echo "Card mounted read-only; repairing the validated $EXPECTED_LABEL card."
        repair_and_mount
        mount_opts="$(findmnt -rn -S "$DEV" -o OPTIONS)"
        case ",$mount_opts," in
            *,rw,*) ;;
            *) die "$DEV remained read-only after fsck" ;;
        esac
        ;;
esac

[ -d "$MOUNT/cubegm" ] ||
    die "not a $EXPECTED_LABEL system card: cubegm/ is missing"

if [ "${PAYLOADS[*]}" = "clean-themes" ]; then
    for retired in Aura Canvas_Pastel Catppuccin Elementerial Iconic PlayStation_X; do
        rm -rf "$MOUNT/frogui/theme-packs/$retired"
    done
    echo "Retired theme packs removed from $EXPECTED_LABEL."
    find "$MOUNT/frogui/theme-packs" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort
    exit 0
fi

# TreeFrogUI must never alter stock boot files. SF3500 boots rkgame directly and
# some already-installed cards omit the unused legacy icube file; protect it
# when present, but only require it on devices whose boot chain uses it.
declare -a STOCK_FILES=(
    cubegm/rkgame
    cubegm/driver.so
)
if [ -f "$MOUNT/cubegm/icube" ]; then
    STOCK_FILES=(cubegm/icube "${STOCK_FILES[@]}")
elif [ "$PROFILE" = r36sx ] &&
    [ -f "$MOUNT/cubegm/zhijack.sh" ] &&
    grep -qx "TF_DEVICE=$EXPECTED_TF_DEVICE" "$MOUNT/cubegm/zhijack.sh" &&
    [ -f "$MOUNT/cubegm/setting.xml" ] &&
    grep -q 'file="/mnt/sdcard/MD/dummy.md" driver=""' "$MOUNT/cubegm/setting.xml" &&
    [ -f "$MOUNT/cubegm/cores/libemu_md.so" ]; then
    echo "r36sx TreeFrogUI identity verified; absent legacy cubegm/icube is unused by this boot path."
elif [ "$PROFILE" = sf3500 ] || [ "$PROFILE" = r36hd ]; then
    echo "$PROFILE legacy cubegm/icube is absent (unused by its boot path)."
else
    die "stock file is missing: cubegm/icube"
fi
readonly -a STOCK_FILES
declare -A stock_hashes=()
for rel in "${STOCK_FILES[@]}"; do
    [ -f "$MOUNT/$rel" ] || die "stock file is missing: $rel"
    hash_line="$(sha256sum "$MOUNT/$rel")"
    stock_hashes["$rel"]="${hash_line%% *}"
done

verify_tree() {
    local src="$1" dst="$2" description="$3" remaining
    remaining="$(rsync -rcni "$src" "$dst" | sed '/^$/d')"
    [ -z "$remaining" ] ||
        die "$description verification found differences: $remaining"
}

deploy_release() {
    local dir name rel hash_line

    echo "Deploying the complete $PROFILE TreeFrogUI release to $DEV..."

    # These were the former visible launcher names and adjacent-art locations.
    for name in \
        "Start Diablo 1.sh" "Start Duke Nukem 3D.sh" "Start Minecraft PE.sh" \
        "Start Captain Claw.sh" "Start Undertale.sh"; do
        rm -f "$MOUNT/roms/ports/$name" "$MOUNT/roms/ports/${name%.sh}.png" \
            "$MOUNT/roms/ports/.res/${name%.sh}.png"
    done

    # Merge only: preserve ROMs, saves, settings, and stock files not present in
    # the release.
    for dir in cubegm frogui roms MD; do
        rsync -rltc "$RELEASE/$dir" "$MOUNT/"
    done

    # install_first itself stays out of the card root. Only this profile's
    # selected overlay is applied.
    for name in README.md theme.md LICENSE.md INSTALL.md picoarch.cfg; do
        [ ! -f "$RELEASE/$name" ] ||
            rsync -tc "$RELEASE/$name" "$MOUNT/"
    done
    [ ! -d "$RELEASE/docs" ] ||
        rsync -rltc "$RELEASE/docs" "$MOUNT/"
    rsync -rltc "$OVERLAY/" "$MOUNT/"

    sync

    for dir in cubegm frogui roms MD; do
        verify_tree "$RELEASE/$dir" "$MOUNT/" "$dir"
    done
    verify_tree "$OVERLAY/" "$MOUNT/" "$PROFILE overlay"

    for name in README.md theme.md LICENSE.md INSTALL.md picoarch.cfg; do
        [ ! -f "$RELEASE/$name" ] ||
            verify_tree "$RELEASE/$name" "$MOUNT/" "$name"
    done
    [ ! -d "$RELEASE/docs" ] ||
        verify_tree "$RELEASE/docs" "$MOUNT/" "docs"

    for rel in \
        cubegm/picoarch \
        cubegm/picoarch_hi \
        cubegm/cores/frogui_libretro.so \
        cubegm/cores/mcpe_libretro.so \
        cubegm/cores/classicube_libretro.so \
        cubegm/cores/j2me_libretro.so \
        cubegm/cores/picante8_libretro.so \
        cubegm/cores/vvvvvv_libretro.so \
        cubegm/cores/libemu_md.so \
        cubegm/zhijack.sh; do
        hash_line="$(sha256sum "$MOUNT/$rel")"
        echo "Verified: $rel  ${hash_line%% *}"
    done

    echo "Complete $PROFILE TreeFrogUI release deployed and verified."
}

deploy_one() {
    local name="$1" src dst src_hash dst_hash hash_line launcher_hash
    case "$name" in
        picoarch)
            src="$WORK/picoarch/picoarch"
            dst="$MOUNT/cubegm/picoarch"
            ;;
        picoarch-hi)
            src="$WORK/picoarch/picoarch_hi"
            dst="$MOUNT/cubegm/picoarch_hi"
            ;;
        frogui)
            src="$REPO/frogui/out/frogui_libretro.so"
            dst="$MOUNT/cubegm/cores/frogui_libretro.so"
            ;;
        duke3d)
            src="$WORK/FroggyDuke/build/sf3000/duke3d_libretro.so"
            dst="$MOUNT/cubegm/cores/duke3d_libretro.so"
            ;;
        butterscotch)
            src="$WORK/FroggyTale/build/sf3000/butterscotch_libretro.so"
            dst="$MOUNT/cubegm/cores/butterscotch_libretro.so"
            ;;
        picante8)
            src="$REPO/release/latest/release/cubegm/cores/picante8_libretro.so"
            dst="$MOUNT/cubegm/cores/picante8_libretro.so"
            ;;
        vvvvvv-data)
            src="/home/tomaszz/.local/share/Steam/steamapps/common/vvvvvv/data.zip"
            dst="$MOUNT/roms/ports/vvvvvv/data.zip"
            ;;
        openclaw)
            src="$WORK/FroggyClaw/openclaw_libretro.so"
            dst="$MOUNT/cubegm/cores/openclaw_libretro.so"
            ;;
        frogshell)
            src="$STAGE/cubegm/frogshell"
            dst="$MOUNT/cubegm/frogshell"
            ;;
        ebook)
            src="$WORK/ebook/ebook"
            dst="$MOUNT/cubegm/ebook"
            ;;
        pcsx4all)
            src="$STAGE/cubegm/pcsx4all"
            dst="$MOUNT/cubegm/pcsx4all"
            ;;
        pcsx4all-config)
            src="$STAGE/cubegm/cores/.pcsx4all/pcsx4all.cfg"
            dst="$MOUNT/cubegm/cores/.pcsx4all/pcsx4all.cfg"
            ;;
        tic80)
            src="$STAGE/cubegm/cores/tic80_libretro.so"
            dst="$MOUNT/cubegm/cores/tic80_libretro.so"
            ;;
        vecx)
            src="$STAGE/cubegm/cores/vecx_libretro.so"
            dst="$MOUNT/cubegm/cores/vecx_libretro.so"
            ;;
        j2me|j2me-debug)
            src="$REPO/build/j2me_libretro.so"
            dst="$MOUNT/cubegm/cores/j2me_libretro.so"
            ;;
        o2em)
            src="$STAGE/cubegm/cores/o2em_libretro.so"
            dst="$MOUNT/cubegm/cores/o2em_libretro.so"
            ;;
        launcher)
            src="$OVERLAY/cubegm/zhijack.sh"
            dst="$MOUNT/cubegm/zhijack.sh"
            ;;
        mame2000)
            src="$STAGE/cubegm/cores/mame2000_libretro.so"
            dst="$MOUNT/cubegm/cores/mame2000_libretro.so"
            ;;
        *) usage ;;
    esac

    [ -f "$src" ] || die "source missing: $src"
    mkdir -p "$(dirname "$dst")"

    hash_line="$(sha256sum "$src")"
    src_hash="${hash_line%% *}"
    if [ -f "$dst" ]; then
        hash_line="$(sha256sum "$dst")"
        dst_hash="${hash_line%% *}"
        if [ "$src_hash" = "$dst_hash" ]; then
            echo "$name already current: $src_hash"
        fi
    fi

    rsync -tc "$src" "$dst"
    if [ "$name" = launcher ]; then
        rm -f "$MOUNT/cubegm/tf_speaker_open"
        [ ! -e "$MOUNT/cubegm/tf_speaker_open" ] ||
            die "obsolete speaker helper remains on card"
    fi
    if [ "$name" = frogui ]; then
        mkdir -p "$MOUNT/frogui/lang"
        rsync -rltc "$REPO/frogui/lang/" "$MOUNT/frogui/lang/"
        # Captain Claw is named openclaw everywhere. Remove files from the
        # retired claw alias so an older install cannot select stale artwork.
        rm -f "$MOUNT/frogui/claw.png" \
              "$MOUNT/frogui/theme-packs/Art_Book_NextUI/claw.png" \
              "$MOUNT/frogui/theme-packs/Art_Book_Next/claw.png" \
              "$MOUNT/frogui/theme-packs/Nao_Black/claw.png"
        rsync -tc "$REPO/assets/j2me/java-games-artbook-nextui.png" "$MOUNT/frogui/j2me.png"
        rsync -tc "$REPO/assets/j2me/java-games-artbook-nextui.png" "$MOUNT/frogui/theme-packs/Art_Book_NextUI/j2me.png"
        rsync -tc "$REPO/assets/j2me/java-games-artbook-next.png" "$MOUNT/frogui/theme-packs/Art_Book_Next/j2me.png"
        rsync -tc "$REPO/assets/j2me/java-games-nao-black.png" "$MOUNT/frogui/theme-packs/Nao_Black/j2me.png"
        for system in classicube; do
            rsync -tc "$REPO/assets/minecraft/minecraft-artbook-nextui.jpg" "$MOUNT/frogui/$system.jpg"
            rsync -tc "$REPO/assets/minecraft/minecraft-artbook-nextui.jpg" "$MOUNT/frogui/theme-packs/Art_Book_NextUI/$system.jpg"
            rsync -tc "$REPO/assets/minecraft/minecraft-artbook-next.jpg" "$MOUNT/frogui/theme-packs/Art_Book_Next/$system.jpg"
            rsync -tc "$REPO/assets/minecraft/minecraft-nao-black.jpg" "$MOUNT/frogui/theme-packs/Nao_Black/$system.jpg"
        done
    fi
    if [ "$name" = duke3d ]; then
        local marker_src="$REPO/assets/duke3d/Start Duke Nukem 3D.duke3d"
        local marker_dst="$MOUNT/roms/ports/duke3d/Start Duke Nukem 3D.duke3d"
        local launcher_src="$REPO/assets/ports/duke3d/run.sh"
        [ -f "$marker_src" ] || die "source missing: $marker_src"
        mkdir -p "$(dirname "$marker_dst")"
        rsync -tc "$marker_src" "$marker_dst"
        rsync -tc "$launcher_src" "$MOUNT/roms/ports/Duke Nukem 3D.sh"
        mkdir -p "$MOUNT/roms/ports/.res"
        rsync -tc "$REPO/assets/ports/duke3d/boxart.png" "$MOUNT/roms/ports/.res/Duke Nukem 3D.png"
        rm -f "$MOUNT/roms/ports/Start Duke Nukem 3D.sh" \
            "$MOUNT/roms/ports/Start Duke Nukem 3D.png" \
            "$MOUNT/roms/ports/.res/Start Duke Nukem 3D.png"
        echo "duke3d launcher deployed"
    fi
    if [ "$name" = butterscotch ]; then
        local marker_src="$REPO/assets/undertale/Start Undertale.butterscotch"
        local marker_dst="$MOUNT/roms/ports/undertale/Start Undertale.butterscotch"
        local launcher_src="$REPO/assets/ports/undertale/run.sh"
        [ -f "$marker_src" ] || die "source missing: $marker_src"
        mkdir -p "$(dirname "$marker_dst")"
        rsync -tc "$marker_src" "$marker_dst"
        rsync -tc "$launcher_src" "$MOUNT/roms/ports/Undertale.sh"
        mkdir -p "$MOUNT/roms/ports/.res"
        rsync -tc "$REPO/assets/ports/undertale/boxart.png" "$MOUNT/roms/ports/.res/Undertale.png"
        rm -f "$MOUNT/roms/ports/Start Undertale.sh" \
            "$MOUNT/roms/ports/Start Undertale.png" \
            "$MOUNT/roms/ports/.res/Start Undertale.png"
        echo "Undertale launcher marker deployed; game data was not copied"
    fi
    sync
    hash_line="$(sha256sum "$dst")"
    dst_hash="${hash_line%% *}"
    [ "$src_hash" = "$dst_hash" ] || die "$name verification failed"
    echo "$name deployed: $dst_hash"

    if [ "$name" = j2me-debug ]; then
        : > "$MOUNT/log.txt"
        echo "J2ME RMS diagnostics enabled."
    fi

    if [ "$name" = j2me ] || [ "$name" = j2me-debug ]; then
        local classes_src="$REPO/assets/j2me/classes.zip"
        local classes_dst="$MOUNT/cubegm/bios/classes.zip"
        [ -f "$classes_src" ] || die "source missing: $classes_src"
        mkdir -p "$(dirname "$classes_dst")"
        rsync -tc "$classes_src" "$classes_dst"
        hash_line="$(sha256sum "$classes_src")"
        src_hash="${hash_line%% *}"
        hash_line="$(sha256sum "$classes_dst")"
        dst_hash="${hash_line%% *}"
        [ "$src_hash" = "$dst_hash" ] || die "classes.zip verification failed"
        echo "j2me classes deployed: $dst_hash"
    fi
}

deploy_vvvvvv() {
    local src dst source_hash card_hash pair
    [ -x "$MOUNT/cubegm/port_check.sh" ] && [ -x "$MOUNT/cubegm/picoarch" ] ||
        die "TreeFrogUI port support is missing; deploy the full release first"
    local -a files=(
        "$WORK/VVVVVV-OpenDingux/build/sf3000/vvvvvv_libretro.so:cubegm/cores/vvvvvv_libretro.so"
        "$REPO/assets/ports/vvvvvv/run.sh:roms/ports/VVVVVV.sh"
        "$REPO/assets/ports/vvvvvv/boxart.png:roms/ports/.res/VVVVVV.png"
        "$REPO/assets/ports/vvvvvv/install.png:frogui/port-help/vvvvvv.png"
        "$WORK/VVVVVV-OpenDingux/LICENSE.md:frogui/licenses/VVVVVV.LICENSE"
    )
    mkdir -p "$MOUNT/roms/ports/vvvvvv"
    for pair in "${files[@]}"; do
        src="${pair%%:*}"
        dst="$MOUNT/${pair#*:}"
        [ -s "$src" ] || die "VVVVVV source missing: $src"
        mkdir -p "$(dirname "$dst")"
        rsync -tc "$src" "$dst"
        [ "$dst" != "$MOUNT/roms/ports/VVVVVV.sh" ] || chmod 755 "$dst"
    done
    sync
    for pair in "${files[@]}"; do
        src="${pair%%:*}"
        dst="$MOUNT/${pair#*:}"
        source_hash="$(sha256sum "$src")"; source_hash="${source_hash%% *}"
        card_hash="$(sha256sum "$dst")"; card_hash="${card_hash%% *}"
        [ "$source_hash" = "$card_hash" ] || die "VVVVVV verification failed: ${pair#*:}"
        echo "Verified VVVVVV: ${pair#*:}  $card_hash"
    done
    echo "VVVVVV port deployed; existing data.zip and saves preserved."
}

deploy_openbor() {
    local pair src dst source_hash card_hash old_pak_hash new_pak_hash game_count=0
    [ -x "$MOUNT/cubegm/port_check.sh" ] && [ -x "$MOUNT/cubegm/picoarch" ] ||
        die "TreeFrogUI port support is missing; deploy the full release first"
    local -a files=(
        "$OPENBOR/build/sf3000/openbor_libretro.so:cubegm/cores/openbor_libretro.so"
        "$REPO/frogui/out/frogui_libretro.so:cubegm/cores/frogui_libretro.so"
        "$REPO/docs/cores/openbor.md:docs/cores/openbor.md"
        "$OPENBOR/LICENSE:frogui/licenses/OpenBOR.LICENSE"
    )
    mkdir -p "$MOUNT/roms/openbor"
    for pair in "${files[@]}"; do
        src="${pair%%:*}"
        dst="$MOUNT/${pair#*:}"
        [ -s "$src" ] || die "OpenBOR source missing: $src"
        mkdir -p "$(dirname "$dst")"
        rsync -tc "$src" "$dst"
    done
    mkdir -p "$MOUNT/frogui/lang/builtin"
    rsync -rltc "$REPO/frogui/lang/builtin/" "$MOUNT/frogui/lang/builtin/"
    # Preserve PAKs already copied to the former port folder while keeping the
    # originals in place in case the user wants to roll back.
    if [ -d "$MOUNT/roms/ports/openbor" ]; then
        while IFS= read -r -d '' src; do
            dst="$MOUNT/roms/openbor/${src##*/}"
            if [ -e "$dst" ]; then
                old_pak_hash="$(sha256sum "$src")"; old_pak_hash="${old_pak_hash%% *}"
                new_pak_hash="$(sha256sum "$dst")"; new_pak_hash="${new_pak_hash%% *}"
                [ "$old_pak_hash" = "$new_pak_hash" ] || {
                    echo "Kept conflicting PAK in roms/ports/openbor: ${src##*/}" >&2
                    continue
                }
            else
                rsync -tc "$src" "$dst"
                old_pak_hash="$(sha256sum "$src")"; old_pak_hash="${old_pak_hash%% *}"
                new_pak_hash="$(sha256sum "$dst")"; new_pak_hash="${new_pak_hash%% *}"
                [ "$old_pak_hash" = "$new_pak_hash" ] || die "OpenBOR PAK migration failed: ${src##*/}"
            fi
            rm -f "$src"
            echo "Moved OpenBOR PAK to roms/openbor/: ${src##*/}"
        done < <(find "$MOUNT/roms/ports/openbor" -maxdepth 1 -type f -iname '*.pak' -print0)
        rmdir "$MOUNT/roms/ports/openbor" 2>/dev/null || true
    fi
    [ -d "$OPENBOR_GAMES" ] || die "OpenBOR game folder is missing: $OPENBOR_GAMES"
    while IFS= read -r -d '' src; do
        dst="$MOUNT/roms/openbor/${src##*/}"
        if [ -e "$dst" ]; then
            old_pak_hash="$(sha256sum "$src")"; old_pak_hash="${old_pak_hash%% *}"
            new_pak_hash="$(sha256sum "$dst")"; new_pak_hash="${new_pak_hash%% *}"
            [ "$old_pak_hash" = "$new_pak_hash" ] || die "refusing to overwrite a different PAK: ${src##*/}"
        else
            rsync -tc "$src" "$dst"
            old_pak_hash="$(sha256sum "$src")"; old_pak_hash="${old_pak_hash%% *}"
            new_pak_hash="$(sha256sum "$dst")"; new_pak_hash="${new_pak_hash%% *}"
            [ "$old_pak_hash" = "$new_pak_hash" ] || die "OpenBOR game copy failed: ${src##*/}"
        fi
        echo "Verified OpenBOR game: roms/openbor/${src##*/}  $new_pak_hash"
        game_count=$((game_count + 1))
    done < <(find "$OPENBOR_GAMES" -maxdepth 1 -type f -iname '*.pak' -print0)
    [ "$game_count" -gt 0 ] || die "no OpenBOR PAK games found in $OPENBOR_GAMES"
    rm -f "$MOUNT/roms/ports/OpenBOR.sh" "$MOUNT/roms/ports/.res/OpenBOR.png"
    rm -f "$MOUNT/frogui/port-help/openbor.png"
    sync
    for pair in "${files[@]}"; do
        src="${pair%%:*}"
        dst="$MOUNT/${pair#*:}"
        source_hash="$(sha256sum "$src")"; source_hash="${source_hash%% *}"
        card_hash="$(sha256sum "$dst")"; card_hash="${card_hash%% *}"
        [ "$source_hash" = "$card_hash" ] || die "OpenBOR verification failed: ${pair#*:}"
        echo "Verified OpenBOR: ${pair#*:}  $card_hash"
    done
    verify_tree "$REPO/frogui/lang/builtin/" "$MOUNT/frogui/lang/builtin/" "OpenBOR translations"
    echo "OpenBOR core deployed under Games/OpenBOR; existing game PAKs and saves were preserved."
}

deploy_dsperate() {
    local src="$WORK/dsperate/build/sf3000-package" dst="$MOUNT/cubegm/dsperate" hash_line
    [ -f "$src/dsperate" ] || die "DSperate SF3000 package is missing: $src/dsperate"
    mkdir -p "$dst"
    rsync -rltc "$src/" "$dst/"
    sync
    verify_tree "$src/" "$dst/" "DSperate package"
    hash_line="$(sha256sum "$dst/dsperate")"
    echo "dsperate deployed: ${hash_line%% *}"
}

deploy_pcsx4all_test_game() {
    local src="/home/tomaszz/Roms/ps1/Harvest Moon - Back to Nature (USA)"
    local dst="$MOUNT/roms/ps1/Harvest Moon - Back to Nature (USA)"
    [ -s "$src/Harvest Moon - Back to Nature (USA).cue" ] &&
        [ -s "$src/Harvest Moon - Back to Nature (USA).bin" ] ||
        die "Harvest Moon PS1 test game is missing from $src"
    mkdir -p "$dst"
    rsync -rltc "$src/" "$dst/"
    sync
    verify_tree "$src/" "$dst/" "PCSX4ALL test game"
    echo "Verified PS1 test game: roms/ps1/Harvest Moon - Back to Nature (USA)"
}

deploy_ps1_bios() {
    local src="/home/tomaszz/Roms/BIOS/scph5501.bin"
    local dst="$MOUNT/cubegm/bios/scph5501.bin" hash_line src_hash dst_hash
    [ -s "$src" ] && [ "$(wc -c < "$src")" -eq 524288 ] ||
        die "valid PS1 BIOS is missing from $src"
    mkdir -p "$(dirname "$dst")"
    if [ -e "$dst" ]; then
        hash_line="$(sha256sum "$src")"; src_hash="${hash_line%% *}"
        hash_line="$(sha256sum "$dst")"; dst_hash="${hash_line%% *}"
        [ "$src_hash" = "$dst_hash" ] ||
            die "refusing to replace a different BIOS at $dst"
    else
        rsync -tc "$src" "$dst"
    fi
    sync
    hash_line="$(sha256sum "$src")"; src_hash="${hash_line%% *}"
    hash_line="$(sha256sum "$dst")"; dst_hash="${hash_line%% *}"
    [ "$src_hash" = "$dst_hash" ] || die "PS1 BIOS verification failed"
    echo "Verified PS1 BIOS: cubegm/bios/scph5501.bin  $dst_hash"
}

deploy_mame2000_mslug() {
    local game_src bios_src game_dst bios_dst
    local game_hash bios_hash hash_line
    readonly game_hash=7ec7824bc018f7aaed7bf9b5964bc468c3ebd70962328426f4d0ca165a2a28bb
    readonly bios_hash=25c7e3892f1d7f9f82d5bdc08bc61b3ad23862d8f60fd1f68041cd76a81f892a

    game_src="$WORK/../Roms/ARCADE/mslug.zip"
    bios_src="$WORK/SF3000_Pro_sdcard/emus/mame/neogeo.zip"
    game_dst="$MOUNT/roms/m2k/mslug.zip"
    bios_dst="$MOUNT/roms/m2k/neogeo.zip"

    [ -f "$game_src" ] || die "Metal Slug ROM is missing: $game_src"
    [ -f "$bios_src" ] || die "MAME 2000 Neo Geo BIOS is missing: $bios_src"
    [ -f "$MOUNT/cubegm/cores/mame2000_libretro.so" ] ||
        die "MAME 2000 core is missing from the card"
    hash_line="$(sha256sum "$game_src")"
    [ "${hash_line%% *}" = "$game_hash" ] ||
        die "Metal Slug ROM no longer matches the verified MAME 0.37b5 set"
    hash_line="$(sha256sum "$bios_src")"
    [ "${hash_line%% *}" = "$bios_hash" ] ||
        die "Neo Geo BIOS no longer matches the verified MAME 0.37b5 set"

    mkdir -p "$MOUNT/roms/m2k"
    rsync -tc "$game_src" "$game_dst"
    rsync -tc "$bios_src" "$bios_dst"
    sync

    hash_line="$(sha256sum "$game_dst")"
    [ "${hash_line%% *}" = "$game_hash" ] ||
        die "m2k/mslug.zip verification failed"
    hash_line="$(sha256sum "$bios_dst")"
    [ "${hash_line%% *}" = "$bios_hash" ] ||
        die "m2k/neogeo.zip verification failed"
    echo "MAME 2000 Metal Slug and Neo Geo BIOS deployed and verified."
}

deploy_mame_test() {
    local rom_src bios_src core_overrides override_tmp game bios dir
    local src_hash dst_hash hash_line copied=0
    local -a games=(
        pacman.zip
        galaga.zip
        frogger.zip
        1942.zip
        dkong3.zip
        sf2.zip
        ffightu.zip
        outrunb.zip
        mk.zip
        nbajam.zip
    )
    local -a bios_files=(
        bios.gg
        bios_E.sms
        bios_J.sms
        bios_MD.bin
        bios_U.sms
        disksys.rom
        gb_bios.bin
        gba_bios.bin
        gbc_bios.bin
        neogeo.zip
        scph5501.bin
    )

    rom_src="$WORK/../Roms/ARCADE/tiny-best-set-go-arcade-update-onion/Roms/ARCADE"
    bios_src="$WORK/../Roms/BIOS"
    [ -d "$rom_src" ] || die "MAME test ROM source is missing: $rom_src"
    [ -d "$bios_src" ] || die "BIOS source is missing: $bios_src"
    [ -f "$MOUNT/cubegm/cores/mame2000_libretro.so" ] ||
        die "MAME 2000 core is missing from the card"
    [ -f "$MOUNT/cubegm/cores/mame2003_plus_libretro.so" ] ||
        die "MAME 2003 Plus core is missing from the card"

    echo "Installing the controlled MAME 2000 / MAME 2003 Plus test set..."
    mkdir -p "$MOUNT/roms/m2k" "$MOUNT/roms/m3p" "$MOUNT/cubegm/bios"

    # The source package declares itself as MAME 2003 Plus. Duplicate the same
    # small batch so m2k shows version-mismatch behavior while m3p is the
    # matching-core control.
    for game in "${games[@]}"; do
        [ -f "$rom_src/$game" ] || die "test ROM is missing: $game"
        for dir in m2k m3p; do
            rsync -tc "$rom_src/$game" "$MOUNT/roms/$dir/$game"
            hash_line="$(sha256sum "$rom_src/$game")"
            src_hash="${hash_line%% *}"
            hash_line="$(sha256sum "$MOUNT/roms/$dir/$game")"
            dst_hash="${hash_line%% *}"
            [ "$src_hash" = "$dst_hash" ] ||
                die "$dir/$game verification failed"
            copied=$((copied + 1))
        done
    done

    # Install the user's general firmware files. MAME machine BIOS zips belong
    # beside their ROMs; keep neogeo.zip there as well as in the system folder.
    for bios in "${bios_files[@]}"; do
        [ -f "$bios_src/$bios" ] || die "BIOS file is missing: $bios"
        rsync -tc "$bios_src/$bios" "$MOUNT/cubegm/bios/$bios"
        hash_line="$(sha256sum "$bios_src/$bios")"
        src_hash="${hash_line%% *}"
        hash_line="$(sha256sum "$MOUNT/cubegm/bios/$bios")"
        dst_hash="${hash_line%% *}"
        [ "$src_hash" = "$dst_hash" ] ||
            die "BIOS verification failed: $bios"
    done
    rsync -tc "$bios_src/neogeo.zip" "$MOUNT/roms/m2k/neogeo.zip"
    rsync -tc "$bios_src/neogeo.zip" "$MOUNT/roms/m3p/neogeo.zip"

    if [ -f "$bios_src/mame2003-plus/hiscore.dat" ]; then
        rsync -tc "$bios_src/mame2003-plus/hiscore.dat" \
            "$MOUNT/cubegm/bios/hiscore.dat"
    fi

    # Give the control folder the same artwork as m2k.
    if [ -f "$MOUNT/frogui/m2k.jpg" ]; then
        rsync -tc "$MOUNT/frogui/m2k.jpg" "$MOUNT/frogui/m3p.jpg"
    fi

    # Preserve every existing override except this test folder's exact entry.
    core_overrides="$MOUNT/frogui/core_overrides.txt"
    override_tmp="$(mktemp /tmp/treefrog-core-overrides.XXXXXX)"
    if [ -f "$core_overrides" ]; then
        grep -vF '/mnt/sdcard/roms/m3p|' "$core_overrides" \
            > "$override_tmp" || true
    fi
    printf '%s\n' \
        '/mnt/sdcard/roms/m3p|/mnt/sdcard/cubegm/cores/mame2003_plus_libretro.so' \
        >> "$override_tmp"
    rsync -tc "$override_tmp" "$core_overrides"
    rm -f -- "$override_tmp"

    sync
    grep -qF \
        '/mnt/sdcard/roms/m3p|/mnt/sdcard/cubegm/cores/mame2003_plus_libretro.so' \
        "$core_overrides" || die "MAME 2003 Plus folder override was not saved"

    echo "MAME test ready: $copied verified ROM copies across m2k and m3p."
}

deploy_amstrad_cap32_test() {
    local game core_overrides override_tmp
    game="/mnt/sdcard/roms/amstrad/Caves of Doom (1985)(Mastertronic).dsk"
    core_overrides="$MOUNT/frogui/core_overrides.txt"

    [ -f "$MOUNT/roms/amstrad/Caves of Doom (1985)(Mastertronic).dsk" ] ||
        die "Amstrad test disk is missing"
    [ -f "$MOUNT/cubegm/cores/cap32_libretro.so" ] ||
        die "Cap32 core is missing from the card"

    override_tmp="$(mktemp /tmp/treefrog-core-overrides.XXXXXX)"
    if [ -f "$core_overrides" ]; then
        grep -vF "$game|" "$core_overrides" > "$override_tmp" || true
    fi
    printf '%s|%s\n' "$game" \
        "/mnt/sdcard/cubegm/cores/cap32_libretro.so" >> "$override_tmp"
    rsync -tc "$override_tmp" "$core_overrides"
    rm -f -- "$override_tmp"

    # zhijack enables verbose logging when this marker exists.
    : > "$MOUNT/log.txt"
    sync
    grep -qF "$game|/mnt/sdcard/cubegm/cores/cap32_libretro.so" \
        "$core_overrides" || die "Cap32 test override was not saved"
    echo "Amstrad test ready: Caves of Doom will launch through Cap32."
}

deploy_o2em_test() {
    local src_dir bios_src game_src bios_dst game_dst hash_line
    readonly src_dir="$WORK/o2em-test"
    readonly bios_src="$src_dir/o2rom.bin"
    readonly game_src="$src_dir/Atlantis.bin"
    readonly bios_dst="$MOUNT/cubegm/bios/o2rom.bin"
    readonly game_dst="$MOUNT/roms/o2em/Atlantis.bin"

    [ -f "$MOUNT/cubegm/cores/o2em_libretro.so" ] ||
        die "O2EM core is missing from the card"
    [ -f "$bios_src" ] || die "O2EM test BIOS is missing: $bios_src"
    [ -f "$game_src" ] || die "O2EM test game is missing: $game_src"

    hash_line="$(sha256sum "$bios_src")"
    [ "${hash_line%% *}" = cb0c5d9ed64f7c1d8870333451832638885b9aa3d7013f0c05fd2a20a5e5bfef ] ||
        die "O2EM BIOS checksum is wrong"
    hash_line="$(sha256sum "$game_src")"
    [ "${hash_line%% *}" = 79a265135c6805311ce9a325f168b5ace770a5f52d71f91d305465ede2722fd3 ] ||
        die "Atlantis test ROM checksum is wrong"

    mkdir -p "$(dirname "$bios_dst")" "$(dirname "$game_dst")"
    rsync -tc "$bios_src" "$bios_dst"
    rsync -tc "$game_src" "$game_dst"
    sync

    verify_tree "$bios_src" "$bios_dst" "O2EM BIOS"
    verify_tree "$game_src" "$game_dst" "Atlantis test ROM"
    echo "O2EM test ready: Atlantis.bin with verified o2rom.bin."
}

deploy_c64_test() {
    local core_src core_dst game_src game_dst config_src config_dst hash_line
    readonly core_src="$STAGE/cubegm/cores/vice_x64_libretro.so"
    readonly core_dst="$MOUNT/cubegm/cores/vice_x64_libretro.so"
    readonly game_src="$WORK/c64-test/Bruce Lee.d64"
    readonly game_dst="$MOUNT/roms/c64/Bruce Lee.d64"
    readonly config_src="$REPO/test-configs/c64/Bruce Lee.cfg"
    readonly config_dst="$MOUNT/picoarch/c64/Bruce Lee.cfg"

    [ -f "$core_src" ] || die "VICE x64 core is missing: $core_src"
    [ -f "$game_src" ] || die "C64 test disk is missing: $game_src"
    [ -f "$config_src" ] || die "C64 test config is missing: $config_src"
    hash_line="$(sha256sum "$game_src")"
    [ "${hash_line%% *}" = d883005ab7bba6f0e3bb5f3e397181a576a09862fe1f1f0d1cc989adfade1de7 ] ||
        die "Bruce Lee test disk checksum is wrong"

    mkdir -p "$(dirname "$core_dst")" "$(dirname "$game_dst")" "$(dirname "$config_dst")"
    rsync -tc "$core_src" "$core_dst"
    rsync -tc "$game_src" "$game_dst"
    rsync -tc "$config_src" "$config_dst"
    : > "$MOUNT/log.txt"
    sync

    verify_tree "$core_src" "$core_dst" "VICE x64 core"
    verify_tree "$game_src" "$game_dst" "Bruce Lee test disk"
    verify_tree "$config_src" "$config_dst" "Bruce Lee warp-autostart config"
    echo "C64 test ready: Bruce Lee.d64 through VICE x64 with warp autostart."
}

migrate_j2me_saves() {
    local legacy="$MOUNT/picoarch/j2me" target="$MOUNT/saves/j2me"
    local game migrated=0

    [ -d "$legacy" ] || return 0
    mkdir -p "$target"
    for game in "$legacy"/*; do
        [ -d "$game" ] || continue
        mkdir -p "$target/$(basename "$game")"
        rsync -rltc "$game/" "$target/$(basename "$game")/"
        verify_tree "$game/" "$target/$(basename "$game")/" \
            "J2ME save migration for $(basename "$game")"
        migrated=$((migrated + 1))
    done
    [ "$migrated" -eq 0 ] || echo "Migrated and verified $migrated J2ME save directories."
}

deploy_test_games() {
    local src dst hash_line src_hash dst_hash

    copy_game() {
        src="$1"
        dst="$MOUNT/$2"
        [ -f "$src" ] || die "test game source is missing: $src"
        mkdir -p "$(dirname "$dst")"
        rsync -a --partial --append-verify "$src" "$dst"
        hash_line="$(sha256sum "$src")"
        src_hash="${hash_line%% *}"
        hash_line="$(sha256sum "$dst")"
        dst_hash="${hash_line%% *}"
        [ "$src_hash" = "$dst_hash" ] || die "test game verification failed: $dst"
        echo "Verified test game: $2  $dst_hash"
    }

    copy_game /home/tomaszz/Pobrane/mattercrash.p8 roms/pico8/mattercrash.p8
    copy_game /home/tomaszz/Pobrane/carnival_0.2.2.p8 roms/pico8/carnival_0.2.2.p8
    copy_game '/home/tomaszz/Pobrane/1986 - Pokemon Emerald (U)(TrashMan).gba' 'roms/gba/Pokemon Emerald.gba'
    copy_game /home/tomaszz/Pobrane/Diamond-Rush_J2ME_EN_v10-DIAMOND-Dopod-S1.jar 'roms/j2me/Diamond Rush.jar'
    copy_game /home/tomaszz/Pobrane/Asphalt-Nitro_J2ME_EN_v114.jar 'roms/j2me/Asphalt Nitro.jar'
    copy_game '/home/tomaszz/Pobrane/Doom-RPG_J2ME_EN_v1998/Doom RPG (2009)(JAMDAT Mobile Inc.)(v1.9.98).jar' 'roms/j2me/Doom RPG.jar'
    copy_game /home/tomaszz/Pobrane/Asphalt_Urban_GT2.jar 'roms/j2me/Asphalt Urban GT 2.jar'
    copy_game '/home/tomaszz/Pobrane/Tomb Raider (E) [SLES-00024]/Tomb Raider [PAL-E] (E) [SLES-00024].cue' 'roms/ps1/Tomb Raider.cue'
    copy_game '/home/tomaszz/Pobrane/Tomb Raider (E) [SLES-00024]/Tomb Raider [PAL-E] (E) [SLES-00024].bin' 'roms/ps1/Tomb Raider.bin'
    copy_game /home/tomaszz/Pobrane/DIABDAT.MPQ roms/ports/diablo/DIABDAT.MPQ
    sync
}

deploy_test_media() {
    local src dst hash_line src_hash dst_hash

    copy_file() {
        src="$1"
        dst="$MOUNT/$2"
        [ -f "$src" ] || die "test media source is missing: $src"
        mkdir -p "$(dirname "$dst")"
        rsync -tc "$src" "$dst"
        hash_line="$(sha256sum "$src")"; src_hash="${hash_line%% *}"
        hash_line="$(sha256sum "$dst")"; dst_hash="${hash_line%% *}"
        [ "$src_hash" = "$dst_hash" ] || die "test media verification failed: $dst"
        echo "Verified test media: ${dst#"$MOUNT/"}  $dst_hash"
    }

    copy_file '/home/tomaszz/Pobrane/Dance with the Dead - Hex [Official Video].mp3' 'roms/mp3/Dance with the Dead - Hex [Official Video].mp3'
    copy_file '/home/tomaszz/Pobrane/Dance with the Dead - Hex [Official Video].mp3' 'roms/rockbox/Dance with the Dead - Hex [Official Video].mp3'
    copy_file '/home/tomaszz/Roms/gb/video themes/Wario Land - Super Mario Land 3 (World).mp4' 'roms/videos/Wario Land - Super Mario Land 3 (World).mp4'
    copy_file '/home/tomaszz/Roms/ps1/Crash Bandicoot (USA)/Crash Bandicoot (USA).cue' 'roms/ps1/Crash Bandicoot (USA)/Crash Bandicoot (USA).cue'
    copy_file '/home/tomaszz/Roms/ps1/Crash Bandicoot (USA)/Crash Bandicoot (USA).bin' 'roms/ps1/Crash Bandicoot (USA)/Crash Bandicoot (USA).bin'
    copy_file '/home/tomaszz/Roms/snes/Super Metroid (Japan, USA) (En,Ja).sfc' 'roms/snes/Super Metroid.sfc'
    copy_file '/home/tomaszz/Roms/gb/roms/Dr. Mario (World) (Rev A).gb' 'roms/gb/Dr. Mario (World) (Rev A).gb'
    sync
}

deploy_perf_test_roms() {
    local src dst hash_line src_hash dst_hash

    copy_rom() {
        src="$1"
        dst="$MOUNT/$2"
        [ -f "$src" ] || die "performance test ROM is missing: $src"
        mkdir -p "$(dirname "$dst")"
        rsync -tc "$src" "$dst"
        hash_line="$(sha256sum "$src")"; src_hash="${hash_line%% *}"
        hash_line="$(sha256sum "$dst")"; dst_hash="${hash_line%% *}"
        [ "$src_hash" = "$dst_hash" ] || die "performance test ROM verification failed: $dst"
        echo "Verified performance test ROM: ${dst#"$MOUNT/"}  $dst_hash"
    }

    copy_rom '/home/tomaszz/Pobrane/Castlevania - Dawn of Sorrow (USA).nds' 'roms/nds/Castlevania - Dawn of Sorrow.nds'
    copy_rom '/home/tomaszz/Pobrane/Picross DS (USA) (En,Fr,Es).nds' 'roms/nds/Picross DS.nds'
    copy_rom '/home/tomaszz/Roms/gb/roms/Super Mario Land 2 - 6 Golden Coins (USA, Europe) (Rev B).gb' 'roms/gb/Super Mario Land 2.gb'
    copy_rom '/home/tomaszz/Roms/Nintendo Game Boy Color/roms/Pokemon - Crystal Version (USA, Europe) (Rev A).gbc' 'roms/gbc/Pokemon Crystal.gbc'
    copy_rom '/home/tomaszz/Roms/gba/Metroid Fusion (USA).gba' 'roms/gba/Metroid Fusion.gba'
    copy_rom '/home/tomaszz/Roms/nes/Metroid (USA).nes' 'roms/nes/Metroid.nes'
    copy_rom '/home/tomaszz/Roms/snes/Super Metroid (Japan, USA) (En,Ja).sfc' 'roms/snes/Super Metroid.sfc'
    copy_rom '/home/tomaszz/Roms/sega/Sonic The Hedgehog 2 (World) (Rev B).md' 'roms/sega/Sonic 2.md'
    copy_rom '/home/tomaszz/Roms/pico8/[Platform]/Celeste (v1.0).p8.png' 'roms/pico8/Celeste (v1.0).p8.png'
    copy_rom '/home/tomaszz/Roms/pico8/[Platform]/Celeste (v1.0).p8.png' 'roms/fake08/Celeste (v1.0).p8.png'
    copy_rom '/home/tomaszz/Roms/pico8/[Platform]/Celeste (v1.0).p8.png' 'roms/retro8/Celeste (v1.0).p8.png'
    sync
}

deploy_snesz_comparison() {
    local src rel dst hash_line src_hash dst_hash system item name
    local -a games=(
        "Star Fox.sfc|/home/tomaszz/Roms/snes/Star Fox (USA) (Rev 2).sfc"
        "Donkey Kong Country.sfc|/home/tomaszz/Roms/snes/Donkey Kong Country (USA) (Rev 2).sfc"
        "Donkey Kong Country 2.sfc|/home/tomaszz/Roms/snes/Donkey Kong Country 2 - Diddy's Kong Quest (USA) (En,Fr) (Rev 1).sfc"
        "Yoshi's Island.sfc|/home/tomaszz/Roms/snes/Super Mario World 2 - Yoshi's Island (USA) (Rev 1).sfc"
        "F-Zero.sfc|/home/tomaszz/Roms/snes/F-Zero (USA).sfc"
        "Super Mario World.sfc|/home/tomaszz/Roms/snes/Super Mario World (USA).sfc"
    )

    install_file() {
        src="$1"
        rel="$2"
        dst="$MOUNT/$rel"
        mkdir -p "$(dirname "$dst")"
        if [[ "$rel" == roms/* && -e "$dst" ]]; then
            hash_line="$(sha256sum "$src")"; src_hash="${hash_line%% *}"
            hash_line="$(sha256sum "$dst")"; dst_hash="${hash_line%% *}"
            [ "$src_hash" = "$dst_hash" ] || die "refusing to replace a different ROM: $rel"
        else
            rsync -tc "$src" "$dst"
        fi
        hash_line="$(sha256sum "$src")"; src_hash="${hash_line%% *}"
        hash_line="$(sha256sum "$dst")"; dst_hash="${hash_line%% *}"
        [ "$src_hash" = "$dst_hash" ] || die "Snes9x-Z comparison verification failed: $rel"
        echo "Verified Snes9x-Z comparison file: $rel  $dst_hash"
    }

    install_file "$REPO/build/snes9x-Z_libretro.so" cubegm/cores/snes9x-Z_libretro.so
    install_file "$REPO/build/Snes9x-Z.LICENSE" frogui/licenses/Snes9x-Z.LICENSE
    install_file "$REPO/frogui/out/frogui_libretro.so" cubegm/cores/frogui_libretro.so
    for item in "${games[@]}"; do
        name="${item%%|*}"
        src="${item#*|}"
        for system in snes snesz; do
            install_file "$src" "roms/$system/Snes9x-Z Compare - $name"
        done
    done
    sync
}

deploy_duke3d_data() {
    local src_dir=/home/tomaszz/Pobrane/DUKE3D/DUKE3D
    local file src dst hash_line src_hash dst_hash

    [ -d "$src_dir" ] || die "Duke 3D data directory is missing: $src_dir"
    mkdir -p "$MOUNT/roms/ports/duke3d"
    for file in DUKE3D.GRP DUKE.RTS; do
        src="$src_dir/$file"
        dst="$MOUNT/roms/ports/duke3d/$file"
        [ -f "$src" ] || die "Duke 3D data file is missing: $src"
        rsync -tc "$src" "$dst"
        hash_line="$(sha256sum "$src")"
        src_hash="${hash_line%% *}"
        hash_line="$(sha256sum "$dst")"
        dst_hash="${hash_line%% *}"
        [ "$src_hash" = "$dst_hash" ] || die "Duke 3D verification failed: $file"
        echo "Verified Duke 3D data: roms/ports/duke3d/$file  $dst_hash"
    done
    sync
}

deploy_undertale_data() {
    local src_dir="$WORK/FroggyTale/build/undertale-package"
    local name src dst hash_line src_hash dst_hash
    [ -d "$src_dir" ] || die "Undertale package is missing: $src_dir"
    mkdir -p "$MOUNT/roms/ports/undertale/.data"
    for name in game.unx ATLAS.BIN ATLAS.RGBA4444; do
        src="$src_dir/$name"
        dst="$MOUNT/roms/ports/undertale/.data/$name"
        [ -f "$src" ] || die "Undertale file is missing: $src"
        rsync -tc "$src" "$dst"
        hash_line="$(sha256sum "$src")"
        src_hash="${hash_line%% *}"
        hash_line="$(sha256sum "$dst")"
        dst_hash="${hash_line%% *}"
        [ "$src_hash" = "$dst_hash" ] || die "Undertale verification failed: $name"
        echo "Verified Undertale data: roms/ports/undertale/.data/$name  $dst_hash"
        local old_dst="$MOUNT/roms/ports/undertale/$name"
        if [ -f "$old_dst" ] && [ "$(sha256sum "$old_dst" | cut -d' ' -f1)" = "$src_hash" ]; then
            rm -- "$old_dst"
        fi
    done
    local audio_count=0
    for src in "$src_dir"/*.ogg; do
        [ -f "$src" ] || continue
        name="${src##*/}"
        dst="$MOUNT/roms/ports/undertale/.data/$name"
        rsync -tc "$src" "$dst"
        hash_line="$(sha256sum "$src")"
        src_hash="${hash_line%% *}"
        hash_line="$(sha256sum "$dst")"
        dst_hash="${hash_line%% *}"
        [ "$src_hash" = "$dst_hash" ] || die "Undertale audio verification failed: $name"
        audio_count=$((audio_count + 1))
        local old_dst="$MOUNT/roms/ports/undertale/$name"
        if [ -f "$old_dst" ] && [ "$(sha256sum "$old_dst" | cut -d' ' -f1)" = "$src_hash" ]; then
            rm -- "$old_dst"
        fi
    done
    [ "$audio_count" -gt 0 ] || die "Undertale OGG audio files are missing from $src_dir"
    echo "Verified Undertale audio: $audio_count OGG tracks"
    sync
}

deploy_openlara_data() {
    local src_dir="$REPO/build/openlara-game-data" src name dst hash_line src_hash dst_hash count=0 error_slug
    [ -f "$src_dir/LEVEL1.PHD" ] || die "OpenLara game data is missing: $src_dir/LEVEL1.PHD"
    mkdir -p "$MOUNT/roms/ports/openlara"
    for src in "$src_dir"/*.PHD; do
        [ -f "$src" ] || continue
        name="${src##*/}"
        dst="$MOUNT/roms/ports/openlara/$name"
        rsync -tc "$src" "$dst"
        hash_line="$(sha256sum "$src")"
        src_hash="${hash_line%% *}"
        hash_line="$(sha256sum "$dst")"
        dst_hash="${hash_line%% *}"
        [ "$src_hash" = "$dst_hash" ] || die "OpenLara data verification failed: $name"
        echo "Verified OpenLara data: roms/ports/openlara/$name  $dst_hash"
        count=$((count + 1))
    done
    [ "$count" -gt 0 ] || die "no OpenLara PHD files found in $src_dir"
    if [ -f "$MOUNT/cubegm/port_error.txt" ] &&
        IFS= read -r error_slug < "$MOUNT/cubegm/port_error.txt" &&
        [ "$error_slug" = openlara ]; then
        rm -f "$MOUNT/cubegm/port_error.txt"
    fi
    sync
}

for payload in "${PAYLOADS[@]}"; do
    case "$payload" in
        release) deploy_release ;;
        vvvvvv) deploy_vvvvvv ;;
        openbor) deploy_openbor ;;
        test-games) deploy_test_games ;;
        test-media) deploy_test_media ;;
        perf-test-roms) deploy_perf_test_roms ;;
        snesz-comparison) deploy_snesz_comparison ;;
        duke3d-data) deploy_duke3d_data ;;
        undertale-data) deploy_undertale_data ;;
        openlara-data) deploy_openlara_data ;;
        mame2000-mslug) deploy_mame2000_mslug ;;
        mame-test) deploy_mame_test ;;
        amstrad-cap32-test) deploy_amstrad_cap32_test ;;
        o2em-test) deploy_o2em_test ;;
        c64-test) deploy_c64_test ;;
        dsperate) deploy_dsperate ;;
        pcsx4all-test-game) deploy_pcsx4all_test_game ;;
        ps1-bios) deploy_ps1_bios ;;
        *) deploy_one "$payload" ;;
    esac
done

case "${PAYLOADS[*]}" in
    vvvvvv|openbor|snesz-comparison) ;;
    *) migrate_j2me_saves ;;
esac

for rel in "${STOCK_FILES[@]}"; do
    hash_line="$(sha256sum "$MOUNT/$rel")"
    deployed_hash="${hash_line%% *}"
    [ "$deployed_hash" = "${stock_hashes[$rel]}" ] ||
        die "protected stock file changed: $rel"
    echo "Stock preserved: $rel  $deployed_hash"
done
