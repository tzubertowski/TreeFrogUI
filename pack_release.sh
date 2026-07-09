#!/bin/sh
# Pack release/ into a versioned zip: ./pack_release.sh v1.0.4_b
# Uses zip(1) when present; otherwise Python (which must explicitly add empty
# directories — the roms/ skeleton is mostly empty placeholder folders and a
# naive file-walk zipper silently drops them all).
set -e
cd "$(dirname "$0")"
[ -n "$1" ] || { echo "usage: $0 <version>  (e.g. v1.0.4_b)"; exit 1; }
OUT="TreeFrogUI_$1.zip"

if command -v zip >/dev/null 2>&1; then
    rm -f "$OUT"
    zip -qr "$OUT" release
else
    python3 - "$OUT" <<'EOF'
import zipfile, os, sys
with zipfile.ZipFile(sys.argv[1], 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk('release'):
        for d in dirs:
            full = os.path.join(root, d)
            if not os.listdir(full):
                zf.writestr(zipfile.ZipInfo(full + '/'), '')
        for f in files:
            full = os.path.join(root, f)
            zf.write(full, full)
EOF
fi
ls -la "$OUT"
