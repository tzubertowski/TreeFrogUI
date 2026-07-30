#!/usr/bin/env bash
# Compatibility entry point. New code lives in deploy_device.sh.
set -euo pipefail
exec /home/tomaszz/sf3000-work/sf3000_treefrogui/deploy_device.sh sf3000 "$@"
