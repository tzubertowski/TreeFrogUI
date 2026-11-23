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
backed-up card and follow [`docs/dev/usb-mode-safety.md`](../../docs/dev/usb-mode-safety.md).

## Lazy MTP responder (`tfmtp`)

`usb_mtp.sh` / `usb_mode.sh mtp` prefer `cubegm/tfmtp` and fall back to the
stock `mtp-server` when it is absent (`TF_USB_MTP_RESPONDER` still overrides
both).

Why: the stock `mtp-server` walks the whole SD card before it reads its first
command (~200 objects/s; 167 s for a 34k-object card). Windows cancels
`OpenSession` after ~30 s ("driver start failed", HRESULT 0x802A0006) and does
not retry until the cable is replugged, so the device never appears in
Explorer. `tfmtp` assigns object handles only when the host lists a folder, so
it answers immediately.

- Source: `tfmtp.c` (single file, MIT). It talks to the same Android `f_mtp`
  gadget (`/dev/mtp_usb`, `MTP_SEND_FILE_WITH_HEADER`) as `mtp-server`.
- Build: `zig cc -target mipsel-linux-musleabi -mcpu=mips32 -static -Os -s -o tfmtp tfmtp.c`
  (static, no dependency on the card's libraries).
- Self-test on a host: `zig cc -DTFMTP_TEST -o tfmtp_test tfmtp.c && ./tfmtp_test`.
- `usb_mode.sh` now binds the UDC (and switches the MUSB role) only after the
  responder blocks in `mtp_read`. Switching to `peripheral` before a gadget is
  bound makes Windows report "device descriptor request failed". With the stock
  responder the screen shows the indexing progress, and B cancels it.
- With an empty `log.txt` in the SD root, every MTP operation and a 2 s
  process/USB trace are appended to `log.txt`.
- Full diagnosis, measurements and a standalone installer:
  https://github.com/kotekompotek/treefrogui-mtp-server
