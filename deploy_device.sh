#!/usr/bin/env bash
#
# Guarded in-place TreeFrogUI deployment for supported device cards.
#
# Usage:
#   ./build_release.sh
#   pkexec ./deploy.sh <r36sx|sf3000|sf3500> [payload ...]
#
# With no payload, the complete release plus the selected install_first overlay
# is deployed. Optional development payloads:
#   release, clean-themes, picoarch, picoarch-hi, frogui, ebook, pcsx4all, pcsx4all-config,
#   tic80, vecx, o2em, o2em-test, c64-test,
#   mame2000, mame2000-mslug, mame-test, amstrad-cap32-test
#
# This script never formats a card and never uses rsync --delete.
set -euo pipefail

readonly WORK=/home/tomaszz/sf3000-work
readonly REPO="$WORK/sf3000_treefrogui"
readonly RELEASE="$REPO/release"
readonly STAGE="$REPO/sdcard"
readonly OWNER_UID=1000
readonly OWNER_GID=1000

die() {
    echo "deploy-device: $*" >&2
    exit 1
}

usage() {
    cat >&2 <<EOF
usage: $0 <r36sx|sf3000|sf3500> [payload ...]
payloads: release clean-themes picoarch picoarch-hi frogui ebook pcsx4all pcsx4all-config tic80 vecx o2em o2em-test c64-test mame2000 mame2000-mslug mame-test amstrad-cap32-test
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
        readonly CLEAR_FORCE_SW=0
        ;;
    sf3000)
        readonly EXPECTED_LABEL=SF3000
        readonly EXPECTED_TF_DEVICE=SF3000
        readonly CLEAR_FORCE_SW=1
        ;;
    sf3500)
        readonly EXPECTED_LABEL=SF3500
        readonly EXPECTED_TF_DEVICE=SF3500
        readonly CLEAR_FORCE_SW=1
        ;;
    *) usage ;;
esac

readonly MOUNT="/mnt/treefrog-$PROFILE"
readonly OVERLAY="$RELEASE/install_first/$PROFILE"

if [ "$#" -eq 0 ]; then
    set -- release
fi
readonly -a PAYLOADS=("$@")

for payload in "${PAYLOADS[@]}"; do
    case "$payload" in
        release|clean-themes|picoarch|picoarch-hi|frogui|ebook|pcsx4all|pcsx4all-config|tic80|vecx|o2em|o2em-test|c64-test|mame2000|mame2000-mslug|mame-test|amstrad-cap32-test) ;;
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
    for retired in Aura Catppuccin Elementerial Iconic PlayStation_X; do
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
if [ "$PROFILE" != sf3500 ] || [ -f "$MOUNT/cubegm/icube" ]; then
    STOCK_FILES=(cubegm/icube "${STOCK_FILES[@]}")
else
    echo "SF3500 legacy cubegm/icube is absent (unused by its direct rkgame boot)."
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

    # SF-class devices use the hardware presentation watchdog. A marker from an
    # older failed test must not pin a newly fixed build to software rendering.
    if [ "$CLEAR_FORCE_SW" -eq 1 ] &&
        [ -e "$MOUNT/cubegm/force_sw.flag" ]; then
        rm -f -- "$MOUNT/cubegm/force_sw.flag"
        echo "Removed stale cubegm/force_sw.flag."
    fi

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
        cubegm/cores/libemu_md.so \
        cubegm/zhijack.sh; do
        hash_line="$(sha256sum "$MOUNT/$rel")"
        echo "Verified: $rel  ${hash_line%% *}"
    done

    echo "Complete $PROFILE TreeFrogUI release deployed and verified."
}

deploy_one() {
    local name="$1" src dst src_hash dst_hash hash_line
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
            src="$WORK/FrogUI/frogui_libretro.so"
            dst="$MOUNT/cubegm/cores/frogui_libretro.so"
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
        o2em)
            src="$STAGE/cubegm/cores/o2em_libretro.so"
            dst="$MOUNT/cubegm/cores/o2em_libretro.so"
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
            return
        fi
    fi

    rsync -tc "$src" "$dst"
    sync
    hash_line="$(sha256sum "$dst")"
    dst_hash="${hash_line%% *}"
    [ "$src_hash" = "$dst_hash" ] || die "$name verification failed"
    echo "$name deployed: $dst_hash"
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

for payload in "${PAYLOADS[@]}"; do
    case "$payload" in
        release) deploy_release ;;
        mame2000-mslug) deploy_mame2000_mslug ;;
        mame-test) deploy_mame_test ;;
        amstrad-cap32-test) deploy_amstrad_cap32_test ;;
        o2em-test) deploy_o2em_test ;;
        c64-test) deploy_c64_test ;;
        *) deploy_one "$payload" ;;
    esac
done

for rel in "${STOCK_FILES[@]}"; do
    hash_line="$(sha256sum "$MOUNT/$rel")"
    deployed_hash="${hash_line%% *}"
    [ "$deployed_hash" = "${stock_hashes[$rel]}" ] ||
        die "protected stock file changed: $rel"
    echo "Stock preserved: $rel  $deployed_hash"
done
