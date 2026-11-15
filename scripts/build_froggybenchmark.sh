#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK_ROOT=${WORK_ROOT:-$(dirname "$ROOT")}
SOURCE=${FROGGYBENCHMARK_ROOT:-$WORK_ROOT/froggybenchmark}
OUT=${FROGGYBENCHMARK_BIN:-$ROOT/build/froggybenchmark.mipsel}
TOOLCHAIN=${FROGGYBENCHMARK_TC:-${SF3500_TC:-}}

[[ -f "$SOURCE/build.sh" ]] || {
  echo "Missing FroggyBenchmark source: $SOURCE" >&2
  exit 1
}
if [[ "${FROGGYBENCHMARK_REBUILD:-0}" = 1 ]]; then
  [[ -n "$TOOLCHAIN" ]] || {
    echo "FROGGYBENCHMARK_REBUILD=1 requires FROGGYBENCHMARK_TC or SF3500_TC" >&2
    exit 1
  }
  (cd "$SOURCE" && SF3500_TC="$TOOLCHAIN" ./build.sh)
fi
[[ -s "$SOURCE/froggybenchmark.mipsel" ]] || {
  echo "Missing FroggyBenchmark binary: $SOURCE/froggybenchmark.mipsel" >&2
  exit 1
}
mkdir -p "$(dirname "$OUT")"
cp "$SOURCE/froggybenchmark.mipsel" "$OUT"
file "$OUT"
