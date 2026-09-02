# USB-host storage (`ROM Source: OTG`)

The stock root filesystem owns hotplug handling, so external USB storage cannot
be enabled by copying files to the SD card alone.  The implementation lives in
[`rootfs-overlay/etc/mdev/mount-helper.sh`](../../rootfs-overlay/etc/mdev/mount-helper.sh).
Install that file into the firmware rootfs at the same path.

When a USB disk is attached, mdev mounts it once at `/media/hdd`. If the drive
contains `/roms`, FrogUI shows **ROM Source: SD / OTG** in Settings; selecting
OTG makes the Games tab browse `/media/hdd/roms` as a separate library. The
option is not shown without a mounted compatible drive. On removal the drive is
lazily unmounted and the internal SD remains untouched.

This is USB-host mode (console reads an external drive), distinct from MTP
device mode (a PC reads the console SD).  It requires the stock kernel's
USB-storage and filesystem modules and an image rebuild to install the rootfs
overlay.
