#!/bin/bash
set -o pipefail
cd /root/r36k || exit 1
make clean >/dev/null 2>&1
make V=1 > /root/r36k/build.log 2>&1
echo "exit=$?"
grep -E "mipsel-linux-gnu-gcc" /root/r36k/build.log | head -3
echo "--- modpost tail ---"
grep -E "WARNING|ERROR|undefined" /root/r36k/build.log | head -20
echo "--- final elf ---"
mipsel-linux-gnu-readelf -h r36k.ko | grep -E "Data|Machine"
