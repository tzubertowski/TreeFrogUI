# Background MTP service (tfusbd) and remote control

> Enabling: create `cubegm/tfusbd.on` (background MTP) and, optionally, `cubegm/tfmtp.remote` (remote shell) and `cubegm/tfshim.on` (recording layer, GB350). All are off by default. Code: `apps/usb_mode/tfusbd.c`, `tfusbd.sh`, `tfkey.c`, `tfmtp.c` (ops 0x9A00-0x9A04), `pc/`.

MTP now starts by itself when the console is plugged into a PC and runs in the background while the menu and games keep working. The OTG port still works with mice and flash drives, and the PC can control the console over the same MTP connection. The first part (why the stock MTP failed and how `tfmtp` works) is in [mtp.md](mtp.md) and [apps/usb_mode/README.md](../../apps/usb_mode/README.md); the full write-up is at https://github.com/kotekompotek/treefrogui-mtp-server/blob/main/docs/TECHNICAL.md.

Everything below was verified on one console: an R36S clone on a HiChip HC16xx, TreeFrogUI v1.8.0_u (GB350 profile), Windows 10 22H2. The numbers come from that console's logs.

---

## 1. Goal and constraints

Goals:

1. MTP starts by itself as soon as the console is connected to a PC, without the USB (MTP) menu item.
2. Meanwhile the menu and games run as usual; MTP works in the background.
3. The OTG port is not stuck in device mode: a mouse, pad or flash drive on an OTG adapter must keep working.
4. Full control from the PC: Linux commands, files, buttons, screenshots, reboot. The link comes back by itself after a reboot.
5. MTP on both USB ports, if possible.

Found right away in the kernel dumps (`/proc/kallsyms`, TreeFrog's module build config):

- **The kernel has no TCP/IP** (no `tcp_v4_rcv`, no `inet_init`). USB networking (RNDIS/ECM), ssh and adb are impossible without a new kernel, so the control channel has to run over MTP itself.
- **No `uinput` and no `/dev/input`.** Buttons do not go through evdev. The stock `cubevol` daemon polls GPIOs and puts the state into SysV shared memory `ftok("/tmp/joy_key",'a')`; the menu and emulators read it from there.
- The kernel accepts modules through plain `insmod`, which is how TreeFrog already loads `usb_f_mtp.ko`.

## 2. Control channel: custom MTP operations

MTP reserves a range of operation codes for vendor extensions. Windows can send arbitrary MTP operations to a device through WPD (Windows Portable Devices): the MTP driver has an "MTP extension" command category (`WPD_COMMAND_MTP_EXT_EXECUTE_COMMAND_WITH_DATA_TO_READ` and `..._TO_WRITE`, `READ_DATA`/`WRITE_DATA`, `END_DATA_TRANSFER`). No extra driver or libusb is needed: the stock Windows driver is used, and Explorer can stay open at the same time.

**Checked before touching the console.** Through WPD (Python + `comtypes`, wrappers generated from `PortableDeviceApi.dll`), the old `tfmtp` received a plain `GetDevicePropValue(0xD402)` and answered "R36S". The mechanism works.

**`tfmtp` 1.1/1.2: operations 0x9A00–0x9A04.**

| Code | Operation | Data | Response |
|---|---|---|---|
| 0x9A00 | TF_Info | → PC: version string | — |
| 0x9A01 | TF_Exec(flags) | PC →: command for `/bin/sh -c` | job id |
| 0x9A02 | TF_Read(job, max, wait_ms) | → PC: stdout+stderr | state, exit code, bytes still buffered |
| 0x9A03 | TF_Write(job, flags) | PC →: stdin data | bytes accepted |
| 0x9A04 | TF_Signal(job, sig) | — | sig 0 = forget the job |

Design:
- a job is `fork` + `setsid` + `/bin/sh -c`; stdout and stderr share one non-blocking pipe;
- output is buffered in 512 KB per job (up to 8 jobs). When the buffer is full, `tfmtp` stops reading the pipe and the process simply blocks. Memory never grows, and streaming programs (e.g. a recorder) get natural back-pressure;
- `TF_Read` waits for data for at most 2 s, so Explorer's MTP session never stalls;
- the operations exist only when the card has `cubegm/tfmtp.remote`. Without it the console behaves exactly like v1.0 and does not even announce these codes in `DeviceInfo`;
- children get SIGPIPE back to default (otherwise `cat | head` misbehaves) and all extra descriptors closed, including `/dev/mtp_usb`.

**Updating without a card reader.** On Linux a running executable can be deleted; the process keeps using the unlinked inode. So the new build went over MTP: delete `cubegm/tfmtp`, upload the new one, compare SHA-256, re-enter USB mode once.

PC client: [`apps/usb_mode/pc/r36.py`](../../apps/usb_mode/pc/r36.py). The very first `id; uname -a` returned `uid=0(root)`.

Trap: in `sh -c 'cat > f && ... &'` the backgrounded list gets stdin from `/dev/null`, so `cat` reads nothing. Background only the last command.

## 3. Which port can be a USB device

The SoC has two MUSB controllers: `musb-hdrc.0.auto` (0x18844000) and `musb-hdrc.1.auto` (0x18850000). The device tree says `dr_mode = "host"` for both, with no ID or VBUS-sense lines.

**DC port.** Experiment (script logging every 0.25 s): the PC cable was moved from OTG to DC, the second controller was switched to device mode and the MTP gadget was bound to it.

```
 19.83 adc5=104 ...                 <- DC charging detected
 22.34 PHASE4 musb1 -> peripheral, bind gadget to musb-hdrc.1.auto
 ... 30 s: u1=not_attached, the PC never reset the bus
 52.27 RESULT DC_NO_DATA
```

**The DC port only charges; it has no data lines.** MTP on it is impossible at board level.

**The OTG port** (musb0) is the only one with data. The same connector must be a host (mouse, flash drive) and a device (PC). TreeFrog also uses musb0 for both `usb_host.sh` (flash drive) and MTP.

## 4. Telling that a PC is connected

The usual signals do not work on this board:

| Signal | What the experiment showed |
|---|---|
| VBUS (`DEVCTL` VBUS bits, sysfs `vbus`) | always "on": the console itself powers the OTG port |
| UDC state | stays `configured` after the cable is pulled (watched for 300 s) |
| `/dev/check_adc5` (charge sensor) | sees DC charging only; a PC on the OTG port reads 0, although the battery does charge |
| `POWER`/suspend | bit never changes |

**What works: the MUSB FRAME register (offset 0x0C).** It holds the frame number the host broadcasts in an SOF packet every millisecond. It counts while a PC is talking and stands still otherwise:

```
frame0=0x0259  frame0=0x02CD  frame0=0x0312  ...   (PC connected, 3 ms apart)
musb0=idle                                         (cable pulled)
```

Read it twice 3 ms apart via `mmap` of `/dev/mem` (for debugging: `devmem 0x1884400C 16`).

## 5. The tfusbd service: switching host/device

A freshly bound gadget starts in `not attached`; any other state right after binding means a host has reset us. This gives a state machine:

```
IDLE:  2 s HOST        — anything enumerated in /sys/bus/usb/devices/1-* ?  → DEV
       2 s PERIPHERAL  — FRAME counting or UDC left "not attached" ?        → PC
PC:    check FRAME once a second; 3 misses in a row → PC gone → IDLE
DEV:   wait until the device disappears → IDLE
```

Service log on the console:

```
 57.74 PC gone (udc=configured)
 61.60 USB device attached: COMPANY  USB Device  (idVendor=09da class=03)   <- mouse
 65.05 USB device removed
 73.96 PC detected (udc=configured)
```

- `tfmtp` runs all the time; while the gadget is unbound, its reads fail and it waits.
- The gadget is always re-bound before device mode. Device mode without a bound gadget makes Windows report "Unknown USB device (device descriptor request failed)" (see the `usb_mode.sh` comments).
- The first version was a shell script calling `devmem` several times a second. The C version ([`apps/usb_mode/tfusbd.c`](../../apps/usb_mode/tfusbd.c)) reads the register through `mmap` and uses 0% CPU when idle (measured over 10 s during a GBA game).

## 6. Staying out of the games' way

`tfmtp` runs with the **`SCHED_IDLE`** scheduling policy, so it only gets CPU time the game does not want. musl has no `sched_setscheduler` (it deliberately returns an error), so the call is made directly with `syscall(SYS_sched_setscheduler, ...)`. Remote jobs (buttons and the rest) are put back into the normal class by `tfmtp`; otherwise key presses would lag in a busy game.

Measured: 24 MB each way while a game was running.

| | Contra (NES), normal priority | Ace Air Combat (GBA), `SCHED_IDLE` |
|---|---|---|
| PC → console | 2.1 MB/s | 1.7 MB/s |
| console → PC | 7.3 MB/s | 7.6 MB/s |
| visible stutter | one per transfer | none noticed |
| SHA-256 | match | match |

## 7. Taking over a menu session, and the black screen

If the service starts while the USB (MTP) menu item is open, it takes the session over. The first version killed `usb_mode.sh` with SIGKILL so its teardown would not run. Result: the menu started and drew frames into memory (an `fb0` snapshot showed the menu), **but the panel stayed black even after restarting the menu**, until a reboot. The hypothesis "stock `cubevol` blanks the screen while USB is connected" was tested by releasing USB for a minute: the screen stayed black, so it was wrong.

Fix: end the session the way the B button does. The service creates `/tmp/treefrog_mtp_exit`, sends `SIGTERM` to the responder and waits for `usb_mode.sh` to remove the gadget itself. The menu comes back normally.

While the service runs, the USB (MTP) menu item is not needed; the patched `usb_mtp.sh` then returns to the menu immediately.

## 8. Autostart and reboot

At boot TreeFrog runs `cubegm/zhijack.sh`, generated from [`hijack/zhijack.tpl.sh`](../../hijack/zhijack.tpl.sh). Two lines there, before the menu loop and after `cubevol` is started, start the service:

```sh
[ -f /mnt/sdcard/cubegm/tfusbd.on ] && [ -x /mnt/sdcard/cubegm/tfusbd.sh ] && \
    /mnt/sdcard/cubegm/tfusbd.sh start >/dev/null 2>&1
```

`tfusbd.sh start` copies the binary to `/tmp` and runs it from there, so the card is never kept busy. On/off switch: the file `cubegm/tfusbd.on`.

Reboot from the PC: `python r36.py reboot` runs `sync; reboot`. 27 s later the console was back: the service started 9 s into boot and found the PC at 17 s.

## 9. Buttons

The button state is a 32-bit word in shared memory, bits from `frogui/keymap.txt`: UP=4, DOWN=6, LEFT=7, RIGHT=5, A=13, B=14, X=12, Y=15, L1=10, R1=11, START=3, SELECT=0.

Experiment `tfkey probe`: set the unused bit 31 and time how long until `cubevol` overwrites it.

```
marker cleared in 20/20 tries: min 4.97 ms avg 19.53 ms max 47.22 ms
```

`cubevol` rewrites the word every ~20–50 ms, so [`tfkey`](../../apps/usb_mode/tfkey.c) re-asserts the held bits every 0.2 ms and leaves 60 ms between presses in a sequence so the game sees the release. Check: `r36.py key press START` paused Contra, a second press resumed it, no extra presses.

## 10. Screenshots

`fb0` is RGB565, 640×(480×23 pages); the visible page is in `/sys/class/graphics/fb0/pan`. `fb1` is `cubevol`'s ARGB overlay (battery, volume). [`apps/usb_mode/pc/fbshot.py`](../../apps/usb_mode/pc/fbshot.py) reads the visible `fb0` page and `fb1` through `dd`, alpha-blends them and writes a PNG with no third-party libraries. Works in the menu and in games (checked with NES and GBA). In the menu's USB (MTP) mode the visible page holds garbage, because the menu is closed there.

## 11. Security

`cubegm/tfmtp.remote` gives **root access to any PC** the console is plugged into. Remote control is therefore off by default: nothing creates that file. Create it by hand only on consoles you plug into PCs you trust.

## 12. Recording video and sound (tfshim + tfrec)

**Where the frames and sound come from.** Games do not output picture and sound themselves: picoarch loads a driver library (`driver_gb350.so` on the GB350) and calls its `video_driver_disp_frame` and `sound_driver_playframe`. A replacement library in front of the driver sees every frame and every audio chunk at the moment it is output, at the game's native resolution, without reading the screen back.

What the picoarch sources (TreeFrogUI_picoarch, `plat_sdl.c`, `hwdisp.c`) say:
- picoarch does **not** take the driver path from `TF_DRIVER` in `/tmp/tfdevice.env`; it is hard-coded per `TF_DEVICE` and overridden by the `PICOARCH_DRIVER` environment variable. Only the image and video viewers read `TF_DRIVER`;
- `int video_driver_disp_frame(void *src, int w, int h, int pitch_bytes)`: an RGB565 frame;
- `int sound_driver_init(void *dev, int rate, int channels)` is called with `(NULL, 48000, 2)`;
- `int sound_driver_playframe(const void *buf, int n)`: `n` is a count of s16 stereo frames (usually 480 = 10 ms). A negative return makes picoarch re-initialise audio;
- besides functions, picoarch also `dlsym`s the driver's `g_render` variable.

**The layer, `tfshim_gb350.so`** ([`capture/tfshim.c`](../../apps/usb_mode/capture/tfshim.c)):
- exports exactly the real driver's symbol set: 117 functions and 7 variables. The list comes from the driver's `.dynsym` via [`capture/gen_tramp.py`](../../apps/usb_mode/capture/gen_tramp.py); only names are read;
- 114 functions are 8-instruction MIPS trampolines that jump into the real function with argument registers, stack and return address untouched;
- only `video_driver_disp_frame`, `sound_driver_playframe` and `sound_driver_init` (for rate and channels) are intercepted;
- at load the layer points the driver's variables in its own symbol table at the real ones, so `dlsym(…, "g_render")` returns the real driver's address;
- while nothing records, an intercepted call costs 18 instructions, and every 16th call checks whether the capture file `/dev/shm/tfcap` has appeared;
- if the real driver fails to load, the layer logs an error and does not crash the game.

Enabling: with `cubegm/tfshim.on` and `TF_DEVICE=GB350`, the lines in `zhijack.sh` do `export PICOARCH_DRIVER=/mnt/sdcard/cubegm/tfshim_gb350.so`. Nothing on disk is replaced; the real `driver_gb350.so` stays where it is.

**Recording.** [`tfrec`](../../apps/usb_mode/capture/tfrec.c) creates a shared segment `/dev/shm/tfcap` in RAM (2.3 MB: 3 frame slots up to 640×480 and a 2.7 s audio ring). The layer notices it and starts copying frames (capped at the requested fps) and audio there, never blocking: a late `tfrec` just skips overwritten frames. `tfrec` compresses frames losslessly (delta to the previous frame + RLE) and writes a stream to stdout. Remote control carries it to the PC, where [`pc/r36rec.py`](../../apps/usb_mode/pc/r36rec.py) lines it up by timestamps and feeds ffmpeg: H.264 + AAC in an MP4.

Build traps (Zig 0.17):
- a 64-bit division in the layer pulled in an import of a non-existent compiler-rt symbol, which would have made `dlopen` fail on the console. The layer has no 64-bit division, and a check rejects any import without a glibc version;
- the linker wired `DT_INIT`/`DT_FINI` to the exported `_init`/`_fini` trampolines, which would have run them at load. [`capture/postlink.py`](../../apps/usb_mode/capture/postlink.py) removes those entries.

Before the console, the layer passed PC checks: its export set equals the driver's, every trampoline jumps to its own function, and in a MIPS emulator (Unicorn) registers and stack are preserved and frames and audio reach the segment bit-exact.

**Measured on the console** (Moonwalker, Mega Drive, 20 s requested):

| | |
|---|---|
| recorded | 16.9 s: the first ~3 s went into starting `tfrec` and attaching the layer |
| video | 320×240 (the game's native resolution), 30 fps, 398 frames received, 3 lost |
| audio | 48 kHz stereo, nothing lost, in sync with the picture |
| USB stream | ~0.6 MB/s; the MP4 is 0.85 MB |
| game | no stutter noticed (checked by the console's owner) |

The FrogUI menu outputs full 640×480 frames, and the low-priority `tfrec` keeps only part of them (8 of 126 while scrolling fast). A still menu outputs no new frames, so there is nothing to record.

## 13. Not done / not tested

- MTP on the DC port is impossible (no data lines).
- Tested on one console (GB350) and with Windows 10 only. Plain MTP should work with Linux and macOS (libmtp), but remote control is implemented for Windows (WPD) only.
- A flash drive on OTG with the service running was not tested, only a mouse. The service keeps the port in host mode while a device is attached, but working together with TreeFrog's `usb_host.sh` should be checked separately.
- When the PC sleeps, the frame counter stops and the service returns to IDLE after ~3 s. After the PC wakes up, the console reconnects in the next device-mode window, i.e. within 4 s.
- Recording only covers games that run through picoarch (libretro cores); standalone programs (pcsx4all, PPSSPP, the video player) are not recorded. The capture layer is verified on the GB350 only.

## 14. Reproducing the measurements

```bat
python apps\usb_mode\pc\r36.py sh "devmem 0x1884400C 16; sleep 0.01; devmem 0x1884400C 16"   & rem frame counter
python apps\usb_mode\pc\r36.py sh "cat /tmp/tfusbd.log"                                        & rem service log
python apps\usb_mode\pc\r36.py sh "chrt -p $(pidof tfmtp)"                                      & rem SCHED_IDLE
python apps\usb_mode\pc\r36.py key probe                                                        & rem button rewrite period
python apps\usb_mode\pc\r36.py shot screen.png
```
