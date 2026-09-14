#!/bin/sh
# Print the newest full archive from the preceding numeric release line.
# Suffixes do not advance the line: v1.0.13_b still selects v1.0.12_*.
set -eu

VERSION=${1:-}
ARTIFACT_DIR=${2:-release/artifact}
[ -n "$VERSION" ] || { echo "usage: $0 <version> [artifact-dir]" >&2; exit 1; }

current_line=$(printf '%s\n' "$VERSION" \
    | sed -nE 's/^v([0-9]+)\.([0-9]+)\.([0-9]+)([^0-9].*)?$/\1 \2 \3/p')
[ -n "$current_line" ] || {
    echo "ERROR: version must begin with vMAJOR.MINOR.RELEASE: $VERSION" >&2
    exit 1
}
set -- $current_line
current_major=$1 current_minor=$2 current_release=$3

# A suffix build should diff from the stable release of the same numeric
# version when one exists; otherwise fall back to the preceding numeric line.
STABLE="$ARTIFACT_DIR/TreeFrogUI_v$current_major.$current_minor.$current_release.zip"
if [ -f "$STABLE" ]; then
    printf '%s\n' "$STABLE"
    exit 0
fi

# Prefer the newest stable archive in an older numeric line over its suffix
# (prerelease) rebuilds.
OLDER_STABLE=$(find "$ARTIFACT_DIR" -maxdepth 1 -type f -name 'TreeFrogUI_v*.zip' -print 2>/dev/null \
    | sed -nE 's#(.*TreeFrogUI_v[0-9]+\.[0-9]+\.[0-9]+)\.zip$#\1#p' \
    | while IFS= read -r candidate; do
        candidate_line=$(printf '%s\n' "${candidate##*/TreeFrogUI_}" \
            | sed -nE 's/^v([0-9]+)\.([0-9]+)\.([0-9]+)$/\1 \2 \3/p')
        [ -n "$candidate_line" ] || continue
        set -- $candidate_line
        if [ "$1" -eq "$current_major" ] && [ "$2" -eq "$current_minor" ] \
            && [ "$3" -lt "$current_release" ]; then
            printf '%s.zip\n' "$candidate"
        fi
      done | sort -V | tail -1)
if [ -n "$OLDER_STABLE" ]; then
    printf '%s\n' "$OLDER_STABLE"
    exit 0
fi

find "$ARTIFACT_DIR" -maxdepth 1 -type f -name 'TreeFrogUI_v*.zip' -print 2>/dev/null \
    | while IFS= read -r candidate; do
        candidate_version=${candidate##*/TreeFrogUI_}
        candidate_version=${candidate_version%.zip}
        candidate_line=$(printf '%s\n' "$candidate_version" \
            | sed -nE 's/^v([0-9]+)\.([0-9]+)\.([0-9]+)([^0-9].*)?$/\1 \2 \3/p')
        [ -n "$candidate_line" ] || continue
        set -- $candidate_line
        if [ "$1" -eq "$current_major" ] && [ "$2" -eq "$current_minor" ] \
            && [ "$3" -lt "$current_release" ]; then
            printf '%s\n' "$candidate"
        fi
      done | sort -V | tail -1
