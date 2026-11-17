#!/bin/bash
set -euo pipefail
ROOT=/mnt/d/r36s-
REV=da5f1a22ef2ff5c46aa3f750fa10825813970b09
SRC=${SRC:-/root/linux-hichip-$REV}
LAB=$ROOT/scripts/kernel_lab
OUT=${OUT:-$ROOT/payload/kernel_lab}
WORK=/root/r36-kernel-lab
PROFILE=${LAB_PROFILE:-ports}
mkdir -p "$WORK" "$OUT"
test -f "$SRC/arch/mips/hichip/Kconfig"
python3 "$LAB/integrate_ports.py" "$SRC"
# WSL1 can hang when GCC vfork-execs cc1 directly; env breaks that exec chain.
MAKE_ARGS=(ARCH=mips CROSS_COMPILE=mipsel-linux-gnu- "CC=mipsel-linux-gnu-gcc -wrapper /usr/bin/env" "HOSTCC=gcc -wrapper /usr/bin/env" "LD=env mipsel-linux-gnu-ld" "HOSTLD=env ld")
case "$PROFILE" in boot|driver|ports|input|memory) ;; *) echo "unknown LAB_PROFILE=$PROFILE" >&2; exit 2 ;; esac
INIT=$LAB/r36-init.c
EXTRA=()
if [ "$PROFILE" = ports ] || [ "$PROFILE" = input ]; then INIT=$LAB/r36-init-console.c; fi
if [ "$PROFILE" = boot ] || [ "$PROFILE" = driver ]; then INIT=$LAB/r36-init-minimal.c; fi
if [ "$PROFILE" = driver ]; then EXTRA=(-DR36_TEST_DRIVER=1); fi
mipsel-linux-gnu-gcc -wrapper /usr/bin/env -static -Os -Wall -Wextra -Werror "${EXTRA[@]}" "$INIT" -o "$WORK/init"
printf 'dir /dev 0755 0 0\ndir /proc 0755 0 0\ndir /sys 0755 0 0\ndir /sd 0755 0 0\nfile /init %s/init 0755 0 0\nnod /dev/console 0600 0 0 c 5 1\n' "$WORK" > "$WORK/initramfs.list"
cp "$LAB/r36-lab.dts" "$SRC/arch/mips/boot/dts/hichip/r36-lab.dts"
if [ "$PROFILE" != memory ]; then
    cp "$LAB/r36-lab.dts" "$SRC/arch/mips/boot/dts/hichip/r36-base.dts"
    cp "$LAB/r36-ports.dts" "$SRC/arch/mips/boot/dts/hichip/r36-lab.dts"
    cp "$LAB/r36-ports.dts" "$SRC/arch/mips/boot/dts/hichip/r36-ports.dts"
    if [ "$PROFILE" = input ]; then
        cp "$LAB/r36-input.dts" "$SRC/arch/mips/boot/dts/hichip/r36-lab.dts"
    fi
    if [ "$PROFILE" = boot ] || [ "$PROFILE" = driver ]; then
        cp "$LAB/r36-boot.dts" "$SRC/arch/mips/boot/dts/hichip/r36-lab.dts"
    fi
fi
make -C "$SRC" "${MAKE_ARGS[@]}" sf3000_defconfig
"$SRC/scripts/config" --file "$SRC/.config" \
    --set-str LOCALVERSION -r36lab --disable LOCALVERSION_AUTO \
    --enable BLK_DEV_INITRD --set-str INITRAMFS_SOURCE "$WORK/initramfs.list" \
    --enable MODULES --enable MODULE_UNLOAD --disable MODVERSIONS \
    --disable NET --disable USB --disable USB_GADGET --disable INPUT \
    --disable GPIO_HC16XX --disable PINCTRL_HC16XX \
    --disable PWM --disable BACKLIGHT_CLASS_DEVICE --disable REGULATOR \
    --disable EXT4_FS --disable SQUASHFS --disable PROFILING \
    --enable DEVTMPFS --enable DEVTMPFS_MOUNT --enable MMC_BLOCK \
    --enable SERIAL_8250 --enable SERIAL_8250_CONSOLE --enable SERIAL_OF_PLATFORM \
    --enable IKCONFIG --enable IKCONFIG_PROC --enable PROC_PAGE_MONITOR --disable HC16XX_TIMER
if [ "$PROFILE" = ports ] || [ "$PROFILE" = input ]; then
    "$SRC/scripts/config" --file "$SRC/.config" \
        --enable USB --enable USB_GADGET --enable USB_MUSB_HDRC --enable USB_MUSB_HC16XX \
        --disable USB_MUSB_DUAL_ROLE --disable USB_MUSB_HOST --enable USB_MUSB_GADGET \
        --enable MUSB_PIO_ONLY --enable USB_CONFIGFS --enable USB_CONFIGFS_ACM \
        --enable IIO --enable PRINTK_TIME
fi
if [ "$PROFILE" = boot ] || [ "$PROFILE" = driver ]; then
    "$SRC/scripts/config" --file "$SRC/.config" \
        --disable MIPS_RAW_APPENDED_DTB --disable MIPS_ZBOOT_APPENDED_DTB --enable MIPS_NO_APPENDED_DTB
fi
if [ "$PROFILE" = input ]; then
    "$SRC/scripts/config" --file "$SRC/.config" \
        --enable GPIO_HC16XX --enable PINCTRL_HC16XX --enable INPUT --enable INPUT_EVDEV \
        --enable KEYBOARD_GPIO --enable KEYBOARD_GPIO_SERIALIZER
fi
make -C "$SRC" "${MAKE_ARGS[@]}" olddefconfig
make -C "$SRC" -j8 "${MAKE_ARGS[@]}" vmlinux vmlinuz.bin hichip/r36-lab.dtb
# The examples only import built-in kernel symbols; avoid rebuilding unrelated
# in-tree modules solely to obtain their export table.
cp "$SRC/vmlinux.symvers" "$SRC/Module.symvers"
make -C "$SRC" "${MAKE_ARGS[@]}" M="$LAB/hello_driver" modules
mipsel-linux-gnu-objcopy -O binary "$SRC/vmlinux" "$OUT/vmlinux.bin"
cp "$SRC/vmlinux" "$OUT/vmlinux.elf"
cp "$SRC/arch/mips/boot/vmlinuz.bin" "$OUT/vmlinuz.bin"
cp "$SRC/arch/mips/boot/dts/hichip/r36-lab.dtb" "$OUT/r36-lab.dtb"
cp "$SRC/.config" "$OUT/kernel.config"
cp "$SRC/System.map" "$OUT/System.map"
cp "$WORK/init" "$OUT/init.elf"
cp "$SRC/usr/initramfs_inc_data" "$OUT/initramfs.cpio.gz"
cp "$LAB/hello_driver/r36hello.ko" "$LAB/hello_driver/r36memcheck.ko" "$OUT/"
python3 "$LAB/package_kernel.py" "$OUT" "$REV" "$PROFILE" "$SRC"
