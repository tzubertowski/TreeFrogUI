#!/bin/sh
# Test-only launch wrapper in the owned VM. No SD or console access.
exec qemu-mipsel -cpu 74Kf /work/r36-legacy-keys-v3 "$@"
