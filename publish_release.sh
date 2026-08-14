#!/bin/sh
# Build, package and publish both GitHub release assets.
# Usage: ./publish_release.sh <github-tag> [artifact-version] [base-full.zip]
# Example: ./publish_release.sh v1.0.14 v1.0.14_a
set -eu
cd "$(dirname "$0")"

[ -n "${1:-}" ] || {
    echo "usage: $0 <github-tag> [artifact-version] [base-full.zip]" >&2
    exit 1
}
command -v gh >/dev/null 2>&1 || {
    echo "ERROR: GitHub CLI (gh) is required" >&2
    exit 1
}
command -v 7z >/dev/null 2>&1 || {
    echo "ERROR: 7z is required for pre-publish archive tests" >&2
    exit 1
}

TAG=$1
VERSION=${2:-$TAG}
ARTIFACT_DIR=release/artifact
LATEST_DIR=release/latest
FULL="$LATEST_DIR/TreeFrogUI_$VERSION.zip"
UPDATE="$LATEST_DIR/update.zip"
BASE=${3:-}
EXPLICIT_BASE=$BASE

if [ -z "$BASE" ]; then
    BASE=$(./select_release_base.sh "$VERSION" "$ARTIFACT_DIR")
    if [ -z "$BASE" ]; then
        # Bootstrap a missing local cache from the preceding numeric GitHub tag.
        current_line=$(printf '%s\n' "$VERSION" \
            | sed -nE 's/^v([0-9]+)\.([0-9]+)\.([0-9]+)([^0-9].*)?$/\1 \2 \3/p')
        [ -n "$current_line" ] || {
            echo "ERROR: version must begin with vMAJOR.MINOR.RELEASE: $VERSION" >&2
            exit 1
        }
        set -- $current_line
        current_major=$1 current_minor=$2 current_release=$3
        BASE_TAG=$(gh release list --limit 100 --json tagName --jq '.[].tagName' \
            | while IFS= read -r candidate; do
                line=$(printf '%s\n' "$candidate" \
                    | sed -nE 's/^v([0-9]+)\.([0-9]+)\.([0-9]+)([^0-9].*)?$/\1 \2 \3/p')
                [ -n "$line" ] || continue
                set -- $line
                if [ "$1" -eq "$current_major" ] && [ "$2" -eq "$current_minor" ] \
                    && [ "$3" -lt "$current_release" ]; then
                    printf '%s\n' "$candidate"
                fi
              done | sort -V | tail -1)
        [ -n "$BASE_TAG" ] || { echo "ERROR: preceding numeric GitHub release not found" >&2; exit 1; }
        mkdir -p "$ARTIFACT_DIR"
        gh release download "$BASE_TAG" --pattern 'TreeFrogUI_v*.zip' --dir "$ARTIFACT_DIR"
        BASE=$(./select_release_base.sh "$VERSION" "$ARTIFACT_DIR")
    fi
fi

./build_release.sh
if [ -n "$EXPLICIT_BASE" ]; then
    mkdir -p "$ARTIFACT_DIR"
    cached_base="$ARTIFACT_DIR/$(basename "$BASE")"
    if [ ! -e "$cached_base" ] || ! [ "$BASE" -ef "$cached_base" ]; then
        cp "$BASE" "$cached_base"
    fi
    BASE=$cached_base
fi
./pack_release.sh "$VERSION" "$BASE"

# Refuse to mutate GitHub unless both the selection rule and an end-to-end
# simulated SD-card upgrade pass against the exact artifacts being uploaded.
./tests/test_release_base_selection.sh
./tests/test_offline_update.sh "$UPDATE" "$BASE"
7z t "$FULL" >/dev/null
7z t "$UPDATE" >/dev/null

if gh release view "$TAG" >/dev/null 2>&1; then
    gh release upload "$TAG" "$FULL" "$UPDATE" --clobber
else
    gh release create "$TAG" "$FULL" "$UPDATE" \
        --title "TreeFrogUI $TAG" \
        --notes-file release-notes.md
fi

# Retain the successful full build as a future numeric-line comparison artifact.
cp "$FULL" "$ARTIFACT_DIR/"

echo "Published $(basename "$FULL") and $(basename "$UPDATE") to GitHub release $TAG"
