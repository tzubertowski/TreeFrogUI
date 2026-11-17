#!/bin/bash
echo "=== dsc.ko this_module section ==="
mipsel-linux-gnu-readelf -SW /root/dsc.ko 2>/dev/null | grep -E "this_module|Name" || \
mipsel-linux-gnu-readelf -SW "/mnt/d/r36s-/analysis/rootfs_card2/lib/modules/4.4.186-release/extra/dsc.ko" | grep -E "this_module|Name"
echo "=== our module ==="
mipsel-linux-gnu-readelf -SW /root/r36k/r36k.final.ko | grep -E "this_module|Name"
