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

## Background MTP service (`tfusbd`, opt-in)

With `cubegm/tfusbd.on` on the SD card, `zhijack.sh` starts `tfusbd` at boot.
MTP is then served in the background on the OTG port while FrogUI and games
keep running, and the port still works as a USB host (mouse, pad, flash drive):

- `tfusbd` alternates host (2 s) and peripheral with the MTP gadget bound
  (2 s) until something answers. A PC is detected from the MUSB FRAME (SOF)
  counter: on this board VBUS always reads valid (the console powers the port)
  and the UDC state stays `configured` after an unplug, so neither works.
- `tfmtp` runs at nice 19 (SCHED_IDLE starved it under 100 % game load and
  Windows dropped the device), so a game keeps ~98 % of the CPU (24 MB during a GBA game: 1.7 MB/s to the console, 7.6 MB/s to the
  PC, no visible stutter).
- A session started from the USB (MTP) menu item is ended the way the B button
  does it (exit flag + SIGTERM): SIGKILLing `usb_mode.sh` left the display
  black until reboot. While `tfusbd` runs, `usb_mtp.sh` returns to the menu.
- `tfusbd.sh start|stop|status`; log in `/tmp/tfusbd.log`. Idle CPU is 0 %.
- Measured on the GB350: the DC port is charge-only, so MTP works on the OTG
  port only.

Optional remote control: with `cubegm/tfmtp.remote` present, `tfmtp` also
accepts vendor operations 0x9A00-0x9A04 (run a shell command, read its output,
write its stdin, signal it). `pc/r36.py` uses them from Windows through the
stock MTP driver (WPD MTP extension commands): shell, files, `tfkey` button
presses, screenshots (`pc/fbshot.py`), reboot. **Any PC the console is plugged
into gets root while that file exists**, so nothing creates it by default.

### Recording (opt-in, GB350)

With `cubegm/tfshim.on`, `zhijack.sh` exports
`PICOARCH_DRIVER=/mnt/sdcard/cubegm/tfshim_gb350.so`. That layer has exactly the
exports of `driver_gb350.so` (generated trampolines, `capture/gen/`, symbol names
only), forwards every call, and copies frames and audio into `/dev/shm/tfcap`
while `tfrec` runs. `pc/r36rec.py` (needs remote control and ffmpeg) turns the
stream into an H.264/AAC MP4. Measured on Moonwalker (Mega Drive): 320x240 at
30 fps, 3 of 398 frames lost, audio lossless, no stutter noticed. Sources and
offline tests: `capture/` (`build.sh`). Details: docs/dev/mtp-background.md, section 12.

### PC screen on the console, console as a gamepad (needs remote control)

`pc/r36stream.py` (Windows) streams the PC desktop or one window to the
console and turns the console into a virtual Xbox 360 controller (ViGEmBus +
`pip install vgamepad`). On the console `tfview` (sources in `stream/`) runs as
a FrogUI standalone app, so it is started from the menu like any other app.

- Video: lossless RGB565 deltas (`capture/tfcodec.c`) while the picture is
  mostly still, 320x240 JPEG (stb_image) while much of it moves. Frames are
  pixel-doubled to 640x480 on the console, because a size change makes the
  display driver reprogram its scaler and flash black.
- Latency: the PC sends a frame only after `tfview` reports the previous one
  shown, so nothing queues up. Send-to-shown is ~3-20 ms; capture adds up to
  one frame.
- Buttons: D-pad, A/B/X/Y, L1/R1 -> LB/RB, **L2/R2 (joy_key bits 8/9) -> LT/RT**,
  FN (bit 16) -> L3, START/SELECT. SELECT+R1 cycles the pad mode (D-pad as left
  stick, A/B/X/Y as right stick), with an on-screen banner. Hold SELECT+START
  for 1.5 s to leave.
- Measured on the GB350: its "analog" sticks are 8-way digital switches wired
  in parallel to the D-pad (left) and A/B/X/Y (right). `cubevol` reads them
  bit by bit from a shift register, and the SoC ADC shows no stick signal.

Details and measurements: [docs/dev/mtp-background.md](../../docs/dev/mtp-background.md).
