#!/bin/sh
# Build both distributable artifacts from release/latest/release/:
#   ./pack_release.sh v1.0.14_a [previous-full-release.zip]
#   release/latest/TreeFrogUI_v1.0.14_a.zip  full clean-card installation
#   release/latest/update.zip                  update payload
set -eu
cd "$(dirname "$0")"
[ -n "${1:-}" ] || {
    echo "usage: $0 <version> [previous-full-release.zip]" >&2
    exit 1
}
RELEASE_ROOT=release
ARTIFACT_DIR="$RELEASE_ROOT/artifact"
LATEST_DIR="$RELEASE_ROOT/latest"
CURRENT="$LATEST_DIR/release"
[ -d "$CURRENT" ] || { echo "ERROR: $CURRENT missing; run ./build_release.sh first"; exit 1; }

VERSION=$1
case "$VERSION" in
    ''|*[!A-Za-z0-9._-]*) echo "ERROR: invalid version: $VERSION" >&2; exit 1 ;;
esac
FULL_OUT="$LATEST_DIR/TreeFrogUI_$VERSION.zip"
UPDATE_OUT="$LATEST_DIR/update.zip"
UPDATE_STAGE=$(mktemp -d)
trap 'rm -rf "$UPDATE_STAGE"' EXIT INT TERM
BUNDLE="$UPDATE_STAGE/treefrog-update"
BASE_STAGE="$UPDATE_STAGE/base"
FORCE_FILE=update-force-include.txt

BASE_ZIP=${2:-}
if [ -z "$BASE_ZIP" ]; then
    BASE_ZIP=$(./select_release_base.sh "$VERSION" "$ARTIFACT_DIR")
fi
[ -f "$BASE_ZIP" ] || {
    echo "ERROR: preceding numeric-line artifact not found in $ARTIFACT_DIR" >&2
    echo "       expected a release older than $VERSION, or pass its ZIP explicitly" >&2
    exit 1
}

pack_zip() {
    output=$1
    parent=$2
    entry=$3
    mkdir -p "$(dirname "$output")"
    rm -f "$output"
    output_abs="$PWD/$output"
    if command -v 7z >/dev/null 2>&1; then
        # Keep packaging reliable on build hosts with constrained memory. The
        # release tree contains many already-compressed assets, so maximum ZIP
        # compression costs a lot of RAM for negligible size savings.
        (cd "$parent" && 7z a -tzip -mx=1 -mfb=64 -mpass=1 "$output_abs" "$entry" >/dev/null)
    elif command -v zip >/dev/null 2>&1; then
        (cd "$parent" && zip -9qr "$output_abs" "$entry")
    else
        python3 - "$output_abs" "$parent" "$entry" <<'PY'
import os, sys, zipfile
output, parent, entry = sys.argv[1:]
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    top = os.path.join(parent, entry)
    for root, dirs, files in os.walk(top):
        for directory in dirs:
            full = os.path.join(root, directory)
            if not os.listdir(full):
                zf.writestr(os.path.relpath(full, parent) + '/', '')
        for filename in files:
            full = os.path.join(root, filename)
            zf.write(full, os.path.relpath(full, parent))
PY
    fi
}

extract_zip() {
    archive=$1
    destination=$2
    mkdir -p "$destination"
    if command -v 7z >/dev/null 2>&1; then
        7z x -y "$archive" "-o$destination" >/dev/null
    elif command -v unzip >/dev/null 2>&1; then
        unzip -q "$archive" -d "$destination"
    else
        echo "ERROR: 7z or unzip is required to read the previous release" >&2
        exit 1
    fi
}

force_include() {
    [ -f "$FORCE_FILE" ] && grep -Fqx "$1" "$FORCE_FILE"
}

protected_delete() {
    case "$1" in
        roms/*|PS/*|GB/*|GBA/*|GBC/*|FC/*|MD/*|SFC/*|cubegm/bios/*|\
        cubegm/saves/*|screenshots/*|saves/*|bios/*|frogui/settings.txt|\
        frogui/keymap.txt|picoarch.cfg|cubegm/.pcsx4all/*|\
        cubegm/cores/.pcsx4all/*)
            return 0 ;;
    esac
    return 1
}

# Stamp the full installation so future deltas can enforce their exact base.
printf '%s\n' "$VERSION" > "$CURRENT/cubegm/version.txt"
pack_zip "$FULL_OUT" "$LATEST_DIR" release

mkdir -p "$BUNDLE/payload" "$BUNDLE/device"
extract_zip "$BASE_ZIP" "$BASE_STAGE"
[ -d "$BASE_STAGE/release" ] || {
    echo "ERROR: $BASE_ZIP does not contain a release/ tree" >&2
    exit 1
}
BASE_VERSION=$(cat "$BASE_STAGE/release/cubegm/version.txt" 2>/dev/null || true)
[ -n "$BASE_VERSION" ] || BASE_VERSION=unknown

MANIFEST_BASE_VERSION=$BASE_VERSION
MANIFEST_BASE_MAJOR=
if [ "${TREEFROG_CUMULATIVE_UPDATE:-0}" = 1 ]; then
    MANIFEST_BASE_MAJOR=$(printf '%s\n' "$BASE_VERSION" \
        | sed -nE 's/^v([0-9]+)\..*$/\1/p')
    [ -n "$MANIFEST_BASE_MAJOR" ] || {
        echo "ERROR: cumulative update base has no valid major version: $BASE_VERSION" >&2
        exit 1
    }
    # Older 1.x updaters understand base_version=unknown and will accept this
    # package. Newer updaters also enforce base_major below.
    MANIFEST_BASE_VERSION=unknown
fi

# Recreate the universal directory skeleton, then copy only files whose bytes
# changed (plus explicitly forced migration/config files).
find "$CURRENT" -path "$CURRENT/install_first" -prune -o -type d -print \
    | while IFS= read -r directory; do
        relative=${directory#"$CURRENT"}
        mkdir -p "$BUNDLE/payload$relative"
      done

find "$CURRENT" -path "$CURRENT/install_first" -prune -o -type f -print \
    | while IFS= read -r current; do
        relative=${current#"$CURRENT"/}
        previous="$BASE_STAGE/release/$relative"
        if force_include "$relative" || [ ! -f "$previous" ] || ! cmp -s "$current" "$previous"; then
            mkdir -p "$BUNDLE/payload/$(dirname "$relative")"
            cp -a "$current" "$BUNDLE/payload/$relative"
        fi
      done

# Checksummed deletion list for obsolete release-owned files. Personal data and
# mutable configs are protected even if a future release stops shipping them.
: > "$BUNDLE/delete.txt"
find "$BASE_STAGE/release" -path "$BASE_STAGE/release/install_first" -prune -o -type f -print \
    | while IFS= read -r previous; do
        relative=${previous#"$BASE_STAGE/release"/}
        if [ ! -f "$CURRENT/$relative" ] && ! protected_delete "$relative"; then
            printf '%s\n' "$relative" >> "$BUNDLE/delete.txt"
        fi
      done

# Device overlays are also differential, but only the three TreeFrogUI-owned
# boot files are eligible. Stock setting.xml is never part of an update.
for device_dir in "$CURRENT"/install_first/*; do
    [ -d "$device_dir" ] || continue
    device=$(basename "$device_dir")
    destination="$BUNDLE/device/$device"
    mkdir -p "$destination"
    : > "$destination/delete.txt"
    for relative in cubegm/zhijack.sh cubegm/cores/libemu_md.so cubegm/xgame-logo.bmp; do
        current="$device_dir/$relative"
        previous="$BASE_STAGE/release/install_first/$device/$relative"
        if [ -f "$current" ] && { [ ! -f "$previous" ] || ! cmp -s "$current" "$previous"; }; then
            mkdir -p "$destination/$(dirname "$relative")"
            cp -a "$current" "$destination/$relative"
        elif [ ! -f "$current" ] && [ -f "$previous" ]; then
            printf '%s\n' "$relative" >> "$destination/delete.txt"
        fi
    done
done

cat > "$BUNDLE/manifest.txt" <<EOF
format=1
version=$VERSION
base_version=$MANIFEST_BASE_VERSION
${MANIFEST_BASE_MAJOR:+base_major=$MANIFEST_BASE_MAJOR
}base_archive=$(basename "$BASE_ZIP")
credit=Offline update idea by devdeve1oper
EOF

(cd "$BUNDLE" && find . -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > SHA256SUMS)

find "$BUNDLE" -type l -print | grep . && {
    echo "ERROR: symlink in update bundle (FAT32 unsafe)"; exit 1;
}
find "$BUNDLE/device" -name setting.xml -print | grep . && {
    echo "ERROR: update bundle must not replace stock setting.xml"; exit 1;
}
[ -f "$BUNDLE/payload/frogui/settings.txt" ] \
    || { echo "ERROR: forced FrogUI settings missing from update"; exit 1; }
[ -f "$BUNDLE/payload/cubegm/cores/.pcsx4all/pcsx4all.cfg" ] \
    || { echo "ERROR: forced emulator config missing from update"; exit 1; }

pack_zip "$UPDATE_OUT" "$UPDATE_STAGE" treefrog-update

echo "Built latest release against numeric-line artifact $BASE_ZIP ($BASE_VERSION):"
ls -lh "$FULL_OUT" "$UPDATE_OUT"
printf 'Delta files: '
find "$BUNDLE/payload" "$BUNDLE/device" -type f | wc -l
