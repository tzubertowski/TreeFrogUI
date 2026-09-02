# USB mode safety contract

`USB mode` exports the SD-card filesystem as a USB mass-storage device.  The
console and the computer must never have that filesystem mounted at the same
time: neither FAT nor exFAT has coordination for two independent writers.

## Runtime contract

The source helper is `apps/usb_mode/usb_mode.sh`; releases install it as
`cubegm/usb_mode.sh`. It has a blocking `run` command plus
a read-only `status` command.  `run` owns the complete transition and does not
return until the host has disconnected and the local filesystem has been
restored.  There is deliberately no asynchronous `stop` operation: unbinding a
LUN while the computer is still writing can corrupt the card.

For device-independent tests, these locations are configurable.  Production
launches must use their built-in defaults and must not inherit these variables
from user content:

- `TF_USB_SYS_ROOT`: fake or real sysfs root
- `TF_USB_PROC_MOUNTS`: fake or real mount table
- `TF_USB_MOUNTPOINT`: local SD mount point
- `TF_USB_BLOCK_DEVICE`: whole device or partition exported as the LUN
- `TF_USB_CONFIG_ROOT`: fake or real ConfigFS USB-gadget root
- `TF_USB_MODULE_DIR`: device kernel-module directory
- `TF_USB_LOG`: diagnostic log path

Command mocks may be injected by prepending a directory to `PATH`.  The helper
must not invoke a shell assembled from any of the values above.

## Required ordering

Before changing local storage state, `run` must verify all of the following:

1. Exactly one configured backing block device exists and resolves to an
   explicitly supported SD device or partition.  Empty paths, symlinks outside
   `/dev`, root filesystems, and ambiguous discovery are fatal.
2. The mount point is backed by that device.  A different source mounted there
   is fatal.
3. The USB device controller and mass-storage gadget prerequisites exist.
4. No other gadget is bound.  USB host mode is not active.

The successful transition order is strict:

1. `sync`
2. normal `umount` of the SD mount (never `-f` or `-l`)
3. reread the mount table and fail unless the SD is absent
4. configure the mass-storage LUN
5. bind the gadget to the UDC

The recovery order is the inverse:

1. observe a real host disconnect before honoring UI exit or TERM/INT
2. unbind the gadget and verify that the UDC file is empty
3. remove the LUN/gadget configuration
4. run a read-only filesystem check if the platform supplies one
5. normally remount the exact block device at the exact original mount point
6. verify the mount table before reporting success

Every error before binding rolls back immediately.  Every error after binding
keeps the gadget alive until disconnect; it must not trade possible host data
loss for a quick return to the menu.  Failure to remount is a visible fatal
state and must not relaunch FrogUI, whose normal operation writes settings and
saves to the card.

## Host-side acceptance matrix

Tests run against temporary fake sysfs/ConfigFS trees and `PATH` command spies;
they must never require root or touch `/dev`.

| Case | Expected result |
|---|---|
| missing or non-whitelisted backing device | refuse; no `sync`, unmount, or gadget writes |
| mount source differs from backing device | refuse without mutation |
| missing UDC or mass-storage support | refuse before unmount |
| another gadget already bound | refuse without changing it |
| normal path | `sync -> umount -> verify -> configure -> bind` |
| unmount command fails | refuse; filesystem remains locally mounted |
| mount table still contains SD after unmount | refuse; never configure or bind |
| ConfigFS write fails after unmount | remove partial gadget and remount SD |
| bind fails | remove partial gadget and remount SD |
| TERM/INT while host is connected | record exit request, remain bound |
| host disconnect | unbind, clean gadget, remount, then return success |
| remount fails | nonzero result and persistent recovery message/log; do not relaunch UI |
| `status` | makes no writes and distinguishes local, exported, transitioning, and recovery-failed states |

Physical validation should start with a disposable, backed-up card.  While a
large file is copied from the PC, request exit on the console and confirm the
USB disk remains present until the host safely ejects it.  Then verify the
console remounts the card, run a filesystem check on the PC, compare a checksum,
and repeat once with the cable unplugged without ejecting.  The last case is an
unavoidable unsafe-host-removal scenario, but recovery must remain bounded and
must never create simultaneous mounts.
