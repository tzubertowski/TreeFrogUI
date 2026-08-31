# USB mode runtime

`usb_mode.sh` safely hands the SD filesystem from the console to a PC through
the Linux USB mass-storage gadget, then restores local access after the PC has
ejected the disk and the cable has been unplugged.

The included `usb_f_mass_storage.ko` was built from pristine upstream Linux
4.4.186 (`linux-4.4.186.tar.xz` from kernel.org) with the repository's existing
MIPS toolchain and the ABI settings recovered by the LGPT R36SX OTG port:

```text
ARCH=mips
CROSS_COMPILE=mips-mti-linux-gnu-
rt305x_defconfig
CONFIG_LOCALVERSION="-release"
CONFIG_PREEMPT=y
CONFIG_DEBUG_PREEMPT=n
CONFIG_SMP=n
CONFIG_MODVERSIONS=n
CONFIG_MODULE_UNLOAD=n
CONFIG_USB_GADGET=y
CONFIG_USB_LIBCOMPOSITE=m
CONFIG_USB_CONFIGFS=m
CONFIG_USB_CONFIGFS_MASS_STORAGE=y
CONFIG_USB_F_MASS_STORAGE=m
```

Artifact identity:

```text
file: ELF 32-bit LSB relocatable, MIPS, MIPS32 rel2
vermagic: 4.4.186-release preempt MIPS32_R2 32BIT
sha256: 8a4e7279818c7071d8e8d57a5ee160f7ac1d3b27a7da10292f4ee81d4739c997
```

Static and ABI checks do not equal a physical pass. Test first on a disposable,
backed-up card and follow `docs/usb-mode-safety.md`.
