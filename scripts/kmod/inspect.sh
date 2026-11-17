#!/bin/bash
cd /root/r36k || exit 1
echo "=== undef symbols ==="
mipsel-linux-gnu-readelf -sW r36k.ko | grep -c UND
mipsel-linux-gnu-readelf -sW r36k.ko | grep UND | awk '{print $8}' | sort -u
echo "=== reloc symbol names ==="
mipsel-linux-gnu-readelf -rW r36k.ko | awk 'NR>3 {print $5}' | grep -v '^$' | sort -u
