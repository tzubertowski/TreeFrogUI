# External USB storage (follow-up)

Potential next feature: use the console as a USB host so a flash drive or
external card can provide ROMs to FrogUI.

## Feasibility notes

- First verify MUSB host mode, VBUS power, and hotplug enumeration with a
  powered OTG hub and a small FAT32 flash drive.
- Confirm the stock 4.4.186 kernel has USB mass-storage, SCSI disk, and the
  desired filesystem drivers (`usb-storage`, `scsi_mod`, `sd_mod`, FAT32).
  If not, obtain compatible MIPS modules or rebuild the kernel.
- Software flow: switch peripheral → host, enumerate `/dev/sdX`, mount safely,
  add the mount path as a FrogUI ROM root, and unmount on exit/unplug.
- Keep the internal SD mounted; external storage is an additional ROM source.
- Prefer read-only mounting initially and require a powered hub for drives
  that exceed the console USB-C power budget.

## Rough effort

Host probe/mount helper: 0.5 day. Safe hotplug lifecycle: 0.5–1 day.
FrogUI browser integration: 1–2 days. Drive/filesystem testing: about 1 day.

## Current status

Not implemented. MTP peripheral mode is complete; external-host support awaits
hardware and kernel-driver verification.
