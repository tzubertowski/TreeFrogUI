#!/bin/bash
cd /root/r36k || exit 1
echo "=== all symbols ==="
mipsel-linux-gnu-nm r36k.ko
echo "=== relocs ==="
mipsel-linux-gnu-readelf -rW r36k.ko
echo "=== disasm init.text ==="
mipsel-linux-gnu-objdump -d -j .init.text r36k.ko
echo "=== disasm text ==="
mipsel-linux-gnu-objdump -d -j .text r36k.ko
