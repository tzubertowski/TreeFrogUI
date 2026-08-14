#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT INT TERM
touch "$TMP/TreeFrogUI_v1.0.11_l.zip" \
      "$TMP/TreeFrogUI_v1.0.12.zip" \
      "$TMP/TreeFrogUI_v1.0.12_c.zip" \
      "$TMP/TreeFrogUI_v1.0.13_a.zip"

[ "$(./select_release_base.sh v1.0.13_b "$TMP")" = "$TMP/TreeFrogUI_v1.0.12_c.zip" ]
[ "$(./select_release_base.sh v1.0.13_z "$TMP")" = "$TMP/TreeFrogUI_v1.0.12_c.zip" ]
[ "$(./select_release_base.sh v1.0.14_a "$TMP")" = "$TMP/TreeFrogUI_v1.0.13_a.zip" ]

echo "release base selection tests passed"
