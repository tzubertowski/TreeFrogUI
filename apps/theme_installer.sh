#!/bin/sh
# Import a MuOS theme archive into FrogUI's dynamic renderer scheme directory.
set -eu

SD=${FROGUI_SD_ROOT:-/mnt/sdcard}
SCHEMES="$SD/frogui/schemes"
STATUS="$SD/frogui/theme-install-status.txt"
ARCHIVE=${1:-}

fail() {
    printf 'ERROR: %s\n' "$1" > "$STATUS.tmp.$$"
    mv "$STATUS.tmp.$$" "$STATUS"
    exit 1
}

progress() {
    printf 'PROGRESS: %s: %s\n' "$1" "$2" > "$STATUS.tmp.$$"
    mv "$STATUS.tmp.$$" "$STATUS"
}

extension=$(printf '%s' "${ARCHIVE##*.}" | tr '[:upper:]' '[:lower:]')
[ "$extension" = muxthm ] || fail 'Choose a .muxthm archive'
[ -f "$ARCHIVE" ] || fail 'Theme archive not found'
command -v unzip >/dev/null 2>&1 || fail 'unzip is unavailable'

base=${ARCHIVE##*/}
name=$(printf '%s' "${base%.*}" | sed -e 's/[^A-Za-z0-9_-]/_/g' -e 's/__*/_/g' -e 's/^_//' -e 's/_$//')
[ -n "$name" ] || fail 'Theme filename has no usable characters'
[ "${#name}" -le 40 ] || fail 'Theme filename is too long'

# Validate every archive member before extraction: reject absolute paths,
# traversal, malformed listing rows, and archives larger than 64 MiB unpacked.
mkdir -p "$SD/frogui"
listing="$SD/frogui/.theme-list-$$"
work=
trap 'if [ -n "$work" ]; then rm -rf "$work"; fi; rm -f "$listing" "$STATUS.tmp.$$"' EXIT HUP INT TERM
progress 4 'Checking theme archive'
if ! unzip -l "$ARCHIVE" > "$listing" 2>&1; then
    fail 'Invalid or unsafe theme archive'
fi
if ! total_files=$(awk '
    tolower($0) ~ /removing leading/ { unsafe = 1 }
    /(^|[[:space:]])Name$/ { header = 1; next }
    header && /^ *-+([[:space:]]+-+)*[[:space:]]*$/ {
        separators++
        if (separators == 2) footer = 1
        next
    }
    header && !footer {
        if ($1 !~ /^[0-9]+$/ || NF < 4) { invalid = 1; next }
        path = $4
        for (i = 5; i <= NF; i++) path = path " " $i
        if (path ~ /^\// || path ~ /^[A-Za-z]:/ || path ~ /\\/ ||
            path ~ /(^|\/)\.\.(\/|$)/) { invalid = 1; next }
        total += $1
        if (total > 67108864) invalid = 1
        entries++
        if (path !~ /\/$/) files++
    }
    END {
        if (unsafe || invalid || !header || separators < 2 || !footer || entries == 0)
            exit 1
        print files + 0
    }
' "$listing"); then
    fail 'Invalid or unsafe theme archive'
fi
[ "$total_files" -gt 0 ] || fail 'Theme archive contains no files'
rm -f "$listing"

work="$SD/frogui/.theme-import-$$"
mkdir -p "$SCHEMES"
mkdir "$work" || fail 'Could not create import folder'
progress 8 'Preparing theme files'
: > "$work/unzip.log"
(
    if unzip -o "$ARCHIVE" -d "$work" > "$work/unzip.log" 2>&1; then
        unzip_status=0
    else
        unzip_status=$?
    fi
    printf '%s\n' "$unzip_status" > "$work/unzip.exit"
) &
unzip_monitor=$!
while [ ! -f "$work/unzip.exit" ]; do
    extracted=$(awk '/(inflating:|extracting:)/ {count++} END {print count + 0}' "$work/unzip.log")
    percent=$((8 + extracted * 72 / total_files))
    [ "$percent" -le 80 ] || percent=80
    progress "$percent" 'Extracting theme files'
    sleep 0.2
done
wait "$unzip_monitor" || true
if [ "$(cat "$work/unzip.exit")" != 0 ]; then
    fail 'Could not extract theme archive'
fi

# MuOS archives may wrap their resolution folders in one directory.
payload=$work
if [ ! -d "$payload/640x480" ]; then
    for candidate in "$work"/*; do
        [ -d "$candidate/640x480" ] || continue
        payload=$candidate
        break
    done
fi
[ -d "$payload/640x480" ] || fail 'Theme has no 640x480 assets'

# MinUIfied provides 640x480 screen overrides but omits that size's base INI.
profile="$payload/640x480/scheme/default.ini"
if [ ! -f "$profile" ]; then
    profile="$payload/720x480/scheme/default.ini"
fi
if [ ! -f "$profile" ]; then
    for candidate in "$payload"/*/scheme/default.ini; do
        [ -f "$candidate" ] || continue
        profile=$candidate
        break
    done
fi
[ -f "$profile" ] || fail 'Theme has no default scheme profile'
progress 86 'Preparing theme profile'

target=$name
suffix=2
while [ -e "$SCHEMES/$target.ini" ] || [ -e "$SCHEMES/$target" ]; do
    target="${name}_$suffix"
    suffix=$((suffix + 1))
done

mkdir "$work/install"
cp -R "$payload/640x480" "$work/install/640x480" || fail 'Could not stage theme files'
# Keep optional, panel-sized artwork while retaining the 640x480 scheme.
if [ -d "$payload/854x480/image" ]; then
    mkdir "$work/install/854x480"
    cp -R "$payload/854x480/image" "$work/install/854x480/image" || fail 'Could not stage wide theme artwork'
fi
if [ -f "$payload/640x480/image/wall/muxlaunch/explore.png" ] ||
   [ -f "$payload/640x480/image/static/muxlaunch/explore.png" ]; then
    printf '[frogui]\nhome_layout=switch\n\n' > "$work/install.ini"
elif [ -f "$payload/640x480/image/grid/muxlaunch/explore.png" ]; then
    printf '[frogui]\nhome_layout=catos\n\n' > "$work/install.ini"
else
    : > "$work/install.ini"
fi
cat "$profile" >> "$work/install.ini" || fail 'Could not stage theme profile'
progress 94 'Installing theme files'
mv "$work/install" "$SCHEMES/$target" || fail 'Could not install theme files'
if ! mv "$work/install.ini" "$SCHEMES/$target.ini"; then
    rm -rf "$SCHEMES/$target"
    fail 'Could not install theme profile'
fi
sync
progress 100 'Theme installed'
printf 'SUCCESS: %s\n' "$target" > "$STATUS"
exit 0
