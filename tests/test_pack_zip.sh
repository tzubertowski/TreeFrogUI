#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT INT TERM
mkdir -p "$TMP/release"
printf 'old\n' > "$TMP/release/install.md"
sleep 1
printf 'new\n' > "$TMP/release/INSTALL.md"
python3 scripts/pack_zip.py "$TMP/out.zip" "$TMP" release

[ "$(7z l -slt "$TMP/out.zip" | grep -c '^Path = release/[Ii][Nn][Ss][Tt][Aa][Ll][Ll]\.md$')" = 1 ]
[ "$(7z e -so "$TMP/out.zip" release/INSTALL.md 2>/dev/null)" = 'new' ]

echo "case-collision ZIP test passed"
