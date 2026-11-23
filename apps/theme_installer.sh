#!/bin/sh
# Import a MuOS theme archive into FrogUI's dynamic renderer scheme directory.
set -eu

SD=/mnt/sdcard
SCHEMES="$SD/frogui/schemes"
STATUS="$SD/frogui/theme-install-status.txt"
ARCHIVE=${1:-}

fail() {
    printf 'ERROR: %s\n' "$1" > "$STATUS"
    exit 1
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
if ! unzip -l "$ARCHIVE" 2>&1 | awk '
    tolower($0) ~ /removing leading/ { unsafe = 1 }
    /(^|[[:space:]])Name$/ { header = 1; next }
    header && /^ *-+([[:space:]]+-+)*[[:space:]]*$/ {
        separators++
        if (separators == 2) footer = 1
        next
    }
    header && !footer {
        if ($1 !~ /^[0-9]+$/ || NF < 4) exit 1
        path = $4
        for (i = 5; i <= NF; i++) path = path " " $i
        if (path ~ /^\// || path ~ /^[A-Za-z]:/ || path ~ /\\/ ||
            path ~ /(^|\/)\.\.(\/|$)/) exit 1
        total += $1
        if (total > 67108864) exit 1
        files++
    }
    END { if (unsafe || !header || separators < 2 || !footer || files == 0) exit 1 }
'; then
    fail 'Invalid or unsafe theme archive'
fi

work="$SD/frogui/.theme-import-$$"
mkdir -p "$SCHEMES"
mkdir "$work" || fail 'Could not create import folder'
trap 'rm -rf "$work"' EXIT HUP INT TERM
if ! unzip -o "$ARCHIVE" -d "$work" >/dev/null 2>&1; then
    fail 'Could not extract theme archive'
fi

# MuOS archives may contain one wrapper directory around the theme payload.
profile="$work/640x480/scheme/default.ini"
if [ ! -f "$profile" ]; then
    set -- "$work"/*/640x480/scheme/default.ini
    [ -f "$1" ] || fail 'Theme has no 640x480/scheme/default.ini profile'
    profile=$1
fi
payload=${profile%/scheme/default.ini}
payload=${payload%/640x480}

target=$name
suffix=2
while [ -e "$SCHEMES/$target.ini" ] || [ -e "$SCHEMES/$target" ]; do
    target="${name}_$suffix"
    suffix=$((suffix + 1))
done

mkdir "$work/install"
cp -R "$payload/640x480" "$work/install/640x480" || fail 'Could not stage theme files'
if [ -f "$payload/640x480/image/wall/muxlaunch/explore.png" ] ||
   [ -f "$payload/640x480/image/static/muxlaunch/explore.png" ]; then
    printf '[frogui]\nhome_layout=switch\n\n' > "$work/install.ini"
elif [ -f "$payload/640x480/image/grid/muxlaunch/explore.png" ]; then
    printf '[frogui]\nhome_layout=catos\n\n' > "$work/install.ini"
else
    : > "$work/install.ini"
fi
cat "$profile" >> "$work/install.ini" || fail 'Could not stage theme profile'
mv "$work/install" "$SCHEMES/$target" || fail 'Could not install theme files'
if ! mv "$work/install.ini" "$SCHEMES/$target.ini"; then
    rm -rf "$SCHEMES/$target"
    fail 'Could not install theme profile'
fi
sync
printf 'SUCCESS: %s\n' "$target" > "$STATUS"
exit 0
