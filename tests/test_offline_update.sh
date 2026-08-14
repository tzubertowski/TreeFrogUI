#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
GENERATED_ARCHIVE=${1:-}
BASE_ARCHIVE=${2:-}
CURRENT=release/latest/release

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT INT TERM
SD="$TMP/sd"
PKG="$TMP/package/treefrog-update"
mkdir -p "$SD/frogui" "$SD/cubegm/cores/.pcsx4all" "$SD/roms/gb" \
         "$PKG/payload/frogui" "$PKG/payload/cubegm/cores/.pcsx4all" \
         "$PKG/device/r36sx/cubegm/cores"

printf 'old-settings\n' > "$SD/frogui/settings.txt"
printf 'old-emu-config\n' > "$SD/cubegm/cores/.pcsx4all/pcsx4all.cfg"
printf 'test-0\n' > "$SD/cubegm/version.txt"
printf 'personal-rom\n' > "$SD/roms/gb/personal.gb"
printf 'obsolete\n' > "$SD/cubegm/obsolete.so"

cp hijack/tfupdate.sh "$PKG/payload/cubegm/tfupdate.sh"
printf 'new-settings\n' > "$PKG/payload/frogui/settings.txt"
printf 'new-emu-config\n' > "$PKG/payload/cubegm/cores/.pcsx4all/pcsx4all.cfg"
printf 'new-r36sx-launcher\n' > "$PKG/device/r36sx/cubegm/zhijack.sh"
printf 'new-hijack-core\n' > "$PKG/device/r36sx/cubegm/cores/libemu_md.so"
printf 'cubegm/obsolete.so\n' > "$PKG/delete.txt"
printf 'format=1\nversion=test-1\nbase_version=test-0\ncredit=Offline update idea by devdeve1oper\n' \
    > "$PKG/manifest.txt"
(cd "$PKG" && find . -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > SHA256SUMS)
(cd "$TMP/package" && 7z a -tzip "$SD/update.zip" treefrog-update >/dev/null)
cp "$SD/update.zip" "$TMP/good-update.zip"

set +e
TFUPDATE_ROOT="$SD" sh hijack/tfupdate.sh r36sx
STATUS=$?
set -e
[ "$STATUS" = 10 ] || { echo "expected success status 10, got $STATUS"; exit 1; }
[ ! -e "$SD/update.zip" ] || { echo "successful package was not deleted"; exit 1; }
[ ! -e "$SD/delete.txt" ] || { echo "control deletion list leaked onto SD root"; exit 1; }
grep -qx 'new-settings' "$SD/frogui/settings.txt"
grep -qx 'new-emu-config' "$SD/cubegm/cores/.pcsx4all/pcsx4all.cfg"
grep -qx 'old-settings' "$SD/.treefrog-update/backup-test-1/frogui/settings.txt"
grep -qx 'old-emu-config' \
    "$SD/.treefrog-update/backup-test-1/cubegm/cores/.pcsx4all/pcsx4all.cfg"
grep -qx 'personal-rom' "$SD/roms/gb/personal.gb"
[ ! -e "$SD/cubegm/obsolete.so" ] || { echo "obsolete release file was not deleted"; exit 1; }
grep -qx 'new-r36sx-launcher' "$SD/cubegm/zhijack.sh"
grep -qx 'test-1' "$SD/cubegm/version.txt"

# A valid delta for a different installed base must be retained and rejected.
cp "$TMP/good-update.zip" "$SD/update.zip"
set +e
TFUPDATE_ROOT="$SD" sh hijack/tfupdate.sh r36sx
STATUS=$?
set -e
[ "$STATUS" = 1 ] || { echo "expected base mismatch status 1, got $STATUS"; exit 1; }
[ -f "$SD/update.zip" ] || { echo "wrong-base package was incorrectly deleted"; exit 1; }
grep -qx 'test-1' "$SD/cubegm/version.txt"
rm -f "$SD/update.zip"

# A ZIP that extracts successfully but fails its signed file list must be kept,
# and the installed version must remain untouched.
printf 'tampered-settings\n' > "$PKG/payload/frogui/settings.txt"
rm -f "$SD/update.zip"
(cd "$TMP/package" && 7z a -tzip "$SD/update.zip" treefrog-update >/dev/null)
set +e
TFUPDATE_ROOT="$SD" sh hijack/tfupdate.sh r36sx
STATUS=$?
set -e
[ "$STATUS" = 1 ] || { echo "expected checksum failure status 1, got $STATUS"; exit 1; }
[ -f "$SD/update.zip" ] || { echo "failed package was incorrectly deleted"; exit 1; }
grep -qx 'new-settings' "$SD/frogui/settings.txt"

if [ -n "$GENERATED_ARCHIVE" ]; then
    ARCHIVE_VERSION=$(7z e -so "$GENERATED_ARCHIVE" treefrog-update/manifest.txt 2>/dev/null \
        | sed -n 's/^version=//p')
    [ -n "$ARCHIVE_VERSION" ] || { echo "generated update version missing"; exit 1; }
    REAL_SD="$TMP/real-sd"
    mkdir -p "$REAL_SD/frogui" "$REAL_SD/cubegm/cores/.pcsx4all" "$REAL_SD/roms/gb"
    printf 'pre-release-settings\n' > "$REAL_SD/frogui/settings.txt"
    printf 'pre-release-emu-config\n' > "$REAL_SD/cubegm/cores/.pcsx4all/pcsx4all.cfg"
    printf 'keep-me\n' > "$REAL_SD/roms/gb/personal.gb"
    cp "$GENERATED_ARCHIVE" "$REAL_SD/update.zip"
    set +e
    TFUPDATE_ROOT="$REAL_SD" sh hijack/tfupdate.sh sf3000
    STATUS=$?
    set -e
    [ "$STATUS" = 10 ] || { echo "generated update returned $STATUS"; exit 1; }
    [ ! -e "$REAL_SD/update.zip" ] || { echo "generated update was not deleted"; exit 1; }
    cmp "$CURRENT/frogui/settings.txt" "$REAL_SD/frogui/settings.txt"
    cmp "$CURRENT/cubegm/cores/.pcsx4all/pcsx4all.cfg" \
        "$REAL_SD/cubegm/cores/.pcsx4all/pcsx4all.cfg"
    cmp "$CURRENT/install_first/sf3000/cubegm/zhijack.sh" "$REAL_SD/cubegm/zhijack.sh"
    grep -qx 'pre-release-settings' \
        "$REAL_SD/.treefrog-update/backup-$ARCHIVE_VERSION/frogui/settings.txt"
    grep -qx 'keep-me' "$REAL_SD/roms/gb/personal.gb"
    grep -qx "$ARCHIVE_VERSION" "$REAL_SD/cubegm/version.txt"
fi

if [ -n "$GENERATED_ARCHIVE" ] && [ -n "$BASE_ARCHIVE" ]; then
    BASE_EXTRACT="$TMP/base-extract"
    BASE_SD="$TMP/base-sd"
    mkdir -p "$BASE_EXTRACT" "$BASE_SD"
    7z x -y "$BASE_ARCHIVE" "-o$BASE_EXTRACT" >/dev/null
    [ -d "$BASE_EXTRACT/release" ] || { echo "base release tree missing"; exit 1; }
    cp -a "$BASE_EXTRACT/release/." "$BASE_SD/"
    rm -rf "$BASE_SD/install_first"
    cp -a "$BASE_EXTRACT/release/install_first/sf3000/." "$BASE_SD/"
    mkdir -p "$BASE_SD/roms/gb"
    printf 'survives-delta\n' > "$BASE_SD/roms/gb/personal.gb"
    cp "$GENERATED_ARCHIVE" "$BASE_SD/update.zip"
    set +e
    TFUPDATE_ROOT="$BASE_SD" sh hijack/tfupdate.sh sf3000
    STATUS=$?
    set -e
    [ "$STATUS" = 10 ] || { echo "base-to-current delta returned $STATUS"; exit 1; }

    find "$CURRENT" -path "$CURRENT/install_first" -prune -o -type f -print \
        | while IFS= read -r current; do
            relative=${current#"$CURRENT"/}
            cmp "$current" "$BASE_SD/$relative" || {
                echo "delta mismatch: $relative" >&2
                exit 1
            }
          done
    for relative in cubegm/zhijack.sh cubegm/cores/libemu_md.so cubegm/xgame-logo.bmp; do
        cmp "$CURRENT/install_first/sf3000/$relative" "$BASE_SD/$relative"
    done
    grep -qx 'survives-delta' "$BASE_SD/roms/gb/personal.gb"
fi

echo "offline updater tests passed"
