#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK_ROOT=${WORK_ROOT:-$(dirname "$ROOT")}
SOURCE=${FROGGYHWPROBE_ROOT:-$WORK_ROOT/froggyhwprobe}
OUT=${FROGGYHWPROBE_BIN:-$ROOT/build/froggyhwprobe.mipsel}
TOOLCHAIN=${FROGGYHWPROBE_TC:-${SF3500_TC:-}}

[[ -f "$SOURCE/build.sh" ]] || {
  echo "Missing FroggyHWProbe source: $SOURCE" >&2
  exit 1
}
if [[ "${FROGGYHWPROBE_REBUILD:-0}" = 1 ]]; then
  [[ -n "$TOOLCHAIN" ]] || {
    echo "FROGGYHWPROBE_REBUILD=1 requires FROGGYHWPROBE_TC or SF3500_TC" >&2
    exit 1
  }
  (cd "$SOURCE" && SF3500_TC="$TOOLCHAIN" ./build.sh)
fi
[[ -s "$SOURCE/froggyhwprobe.mipsel" ]] || {
  echo "Missing FroggyHWProbe binary: $SOURCE/froggyhwprobe.mipsel" >&2
  exit 1
}
mkdir -p "$(dirname "$OUT")"
cp "$SOURCE/froggyhwprobe.mipsel" "$OUT"
file "$OUT"
