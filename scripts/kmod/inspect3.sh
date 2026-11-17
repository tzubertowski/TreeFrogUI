#!/bin/bash
cd /root/linux-4.4.186 || exit 1
echo "=== -EL / endian in arch/mips/Makefile ==="
grep -n "EL\|EB\|ENDIAN\|endian" arch/mips/Makefile | head -20
echo "=== relevant KBUILD flags ==="
grep -n "mno-abicalls\|mabicalls\|no-pic\|explicit-relocs\|64bit\|32bit" arch/mips/Makefile | head -20
echo "=== ccflags of built module ==="
cd /root/r36k
mipsel-linux-gnu-readelf -h r36k.ko | grep -E "Data|Machine|Flags"
