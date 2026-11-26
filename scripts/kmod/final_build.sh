#!/bin/bash
set -e
cd /root/r36k || exit 1
make clean >/dev/null 2>&1
make >/dev/null 2>&1
echo "=== undefined symbols ==="
mipsel-linux-gnu-nm -u r36k.ko
printf 'description=kernel mem reader\0license=GPL\0depends=\0vermagic=4.4.186-release preempt MIPS32_R2 32BIT \0' > modinfo.bin
mipsel-linux-gnu-objcopy --update-section .modinfo=modinfo.bin r36k.ko r36k.final.ko
echo "=== final modinfo ==="
mipsel-linux-gnu-readelf -p .modinfo r36k.final.ko
echo "=== elf header ==="
mipsel-linux-gnu-readelf -h r36k.final.ko | grep -E "Data|Machine|Type"
echo "=== size ==="
ls -l r36k.final.ko
