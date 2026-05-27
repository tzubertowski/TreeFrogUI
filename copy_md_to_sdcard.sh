#!/bin/sh
# Copy all *.md files (and LICENSE) from this project into the sdcard
# staging dir.  Run from /home/tomaszz/sf3000-work/sf3000_treefrogui.
set -e
cd "$(dirname "$0")"
DEST="sdcard/docs"
mkdir -p "$DEST"
# Skip sdcard itself + cores/ submodules' nested .md (noisy) + build artifacts
find . -type f -name "*.md" \
    -not -path "./sdcard/*" \
    -not -path "./cores/*" \
    -not -path "./build/*" \
    -exec cp --parents {} "$DEST/" \;
# Drop LICENSE at sdcard root for visibility
cp LICENSE.md sdcard/LICENSE.md
echo "Copied $(find "$DEST" -name '*.md' | wc -l) markdown files → $DEST"
echo "Copied LICENSE.md → sdcard/"
