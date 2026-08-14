#!/bin/sh
# TreeFrogUI offline updater. This file is copied to /tmp by zhijack.sh before
# execution, so the installed copy can safely replace itself during an update.

SDROOT=${TFUPDATE_ROOT:-/mnt/sdcard}
PACKAGE="$SDROOT/update.zip"
WORK_DIR="$SDROOT/.treefrog-update"
STAGE="$WORK_DIR/staging"
LOG="$SDROOT/update.log"
DEVICE=${1:-}

case "$DEVICE" in
    r36sx|r36hd|sf3000|sf3500|sf3000hd|sf3100|gb350) ;;
    *) exit 0 ;;
esac

[ -f "$PACKAGE" ] || exit 0

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null) $*" >> "$LOG"
}

fail() {
    log "ERROR: $*"
    rm -rf "$STAGE"
    sync
    exit 1
}

extract_package() {
    if command -v unzip >/dev/null 2>&1; then
        unzip -o "$PACKAGE" -d "$STAGE"
    elif [ -x /bin/busybox ]; then
        /bin/busybox unzip -o "$PACKAGE" -d "$STAGE"
    else
        return 127
    fi
}

install_tree() {
    SOURCE=$1
    [ -d "$SOURCE" ] || return 0

    find "$SOURCE" -type d > "$STAGE/directories.list" || return 1
    while IFS= read -r DIR; do
        REL=${DIR#"$SOURCE"/}
        [ "$DIR" = "$SOURCE" ] && continue
        mkdir -p "$SDROOT/$REL" || return 1
    done < "$STAGE/directories.list"

    find "$SOURCE" -type f > "$STAGE/files.list" || return 1
    while IFS= read -r SRC; do
        REL=${SRC#"$SOURCE"/}
        [ "$REL" = delete.txt ] && continue
        DST="$SDROOT/$REL"
        TMP="$DST.tfu-new.$$"
        mkdir -p "$(dirname "$DST")" || return 1
        rm -f "$TMP"
        cp "$SRC" "$TMP" || return 1
        mv -f "$TMP" "$DST" || return 1
    done < "$STAGE/files.list"
}

mkdir -p "$WORK_DIR" || exit 1
rm -rf "$STAGE"
mkdir -p "$STAGE" || fail "cannot create staging directory"
log "Applying $(basename "$PACKAGE") for $DEVICE"

extract_package >> "$LOG" 2>&1 \
    || fail "archive extraction failed; package kept for retry"

BUNDLE="$STAGE/treefrog-update"
[ -f "$BUNDLE/manifest.txt" ] || fail "manifest.txt missing"
[ -f "$BUNDLE/SHA256SUMS" ] || fail "SHA256SUMS missing"
[ "$(sed -n 's/^format=//p' "$BUNDLE/manifest.txt")" = 1 ] \
    || fail "unsupported update format"
[ -d "$BUNDLE/payload" ] || fail "universal payload missing"
[ -d "$BUNDLE/device/$DEVICE" ] || fail "payload does not support $DEVICE"

(cd "$BUNDLE" && sha256sum -c SHA256SUMS) >> "$LOG" 2>&1 \
    || fail "checksum verification failed; package kept for retry"

VERSION=$(sed -n 's/^version=//p' "$BUNDLE/manifest.txt")
BASE_VERSION=$(sed -n 's/^base_version=//p' "$BUNDLE/manifest.txt")
case "$VERSION" in
    ''|*[!A-Za-z0-9._-]*) fail "invalid update version" ;;
esac
case "$BASE_VERSION" in
    *[!A-Za-z0-9._-]*) fail "invalid base version" ;;
esac
if [ -n "$BASE_VERSION" ] && [ "$BASE_VERSION" != unknown ]; then
    INSTALLED_VERSION=$(cat "$SDROOT/cubegm/version.txt" 2>/dev/null)
    [ "$INSTALLED_VERSION" = "$BASE_VERSION" ] \
        || fail "requires $BASE_VERSION, installed version is ${INSTALLED_VERSION:-unknown}"
fi

# Configs are intentionally authoritative: releases may add options, migrate
# formats, or fix incompatible defaults. Keep one pre-update copy for recovery
# without preserving stale values over the new release.
BACKUP="$WORK_DIR/backup-$VERSION"
for REL in \
    frogui/settings.txt \
    frogui/keymap.txt \
    picoarch.cfg \
    cubegm/.pcsx4all/pcsx4all.cfg \
    cubegm/cores/.pcsx4all/pcsx4all.cfg
do
    if [ -f "$BUNDLE/payload/$REL" ] && \
       [ -f "$SDROOT/$REL" ] && [ ! -f "$BACKUP/$REL" ]; then
        mkdir -p "$BACKUP/$(dirname "$REL")" || fail "cannot create config backup"
        cp "$SDROOT/$REL" "$BACKUP/$REL" || fail "cannot back up $REL"
    fi
done

# ROMs, BIOS, saves, histories and media are never deleted. Release configs are
# authoritative and replace installed configs after the backup above. Device
# files are applied last so the launcher is the final boot-critical change.
install_tree "$BUNDLE/payload" || fail "installing universal payload failed"
install_tree "$BUNDLE/device/$DEVICE" || fail "installing device payload failed"

delete_list() {
    LIST=$1
    [ -f "$LIST" ] || return 0
    while IFS= read -r REL; do
        [ -n "$REL" ] || continue
        case "$REL" in
            /*|../*|*/../*|*/..|roms/*|PS/*|GB/*|GBA/*|GBC/*|FC/*|MD/*|SFC/*|\
            cubegm/bios/*|cubegm/saves/*|cubegm/Update/*|.treefrog-update/*|\
            screenshots/*|saves/*|bios/*|update.zip|update.log)
                return 1 ;;
        esac
        rm -f "$SDROOT/$REL" || return 1
    done < "$LIST"
}

delete_list "$BUNDLE/delete.txt" || fail "unsafe or failed common deletion"
delete_list "$BUNDLE/device/$DEVICE/delete.txt" || fail "unsafe or failed device deletion"

echo "$VERSION" > "$SDROOT/cubegm/version.txt.tfu-new.$$" \
    || fail "cannot write installed-version marker"
mv -f "$SDROOT/cubegm/version.txt.tfu-new.$$" \
      "$SDROOT/cubegm/version.txt" \
    || fail "cannot install version marker"
sync

# Deletion is the commit point: failed/interrupted updates retain the package
# and converge by applying it again on the next successful boot.
rm -f "$PACKAGE" || fail "update installed but package deletion failed"
rm -rf "$STAGE"
sync
log "SUCCESS: TreeFrogUI $VERSION installed; package removed"
exit 10
