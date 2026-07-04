# TreeFrogUI Installation Guide

One TreeFrogUI package supports **six devices** - it auto-detects which one it is
at boot. Pick your device below, grab its stock backup, then follow the same
install steps for everyone.

Supported: **R36SX** (v2.6 / v2.7) · **SF3000** · **SF3000 HD** · **SF3100** ·
**SF3500** · **GB350**.

> [!IMPORTANT]
> **You must start from a clean STOCK OS card for your device.** TreeFrogUI runs
> on top of the stock system - it never replaces the protected boot files
> (`icube`, `rkgame`), it hooks the stock menu's autorun instead. That's why it
> works even on bootloader-protected devices (R36SX v2.7, SF3500-class).

---

## Step 1: Get the stock backup for YOUR device

Click your device to expand. Restore this onto your SD card first (format + copy),
**before** the TreeFrogUI files.

<details>
<summary><b>R36SX (v2.6)</b></summary>

- 📦 [R36SX v2.6 Minimal Backup](https://drive.google.com/file/d/1xTCNNRKfQmFJr2Zkd1oCBRChuWiidIBD)
- Install folder: **`install_first/r36sx/`**
- Boot logo: included in this folder (no action needed)
</details>

<details>
<summary><b>R36SX (v2.7 - bootloader protected)</b></summary>

- 📦 [R36SX v2.7 Minimal Backup](https://drive.google.com/file/d/12G3CQAWkaRMWbrY_YmGH8nstGbs1hB-O)
- Install folder: **`install_first/r36sx/`** (same xml as v2.6)
- Boot logo: included in this folder (no action needed)
- Clones (R36HD, etc.) run a different kernel/DTB - see [R36SX clones](#r36sx-clones-r36hd-etc).
</details>

<details>
<summary><b>SF3000</b></summary>

- 📦 [SF3000 Stock Backup (7z)](https://github.com/Q-ta-s/q-ta-s.github.io/releases/download/sf3000/SF3000_sdcard.7z)
- Install folder: **`install_first/sf3000/`**
- Boot logo: included in this folder (no action needed)
</details>

<details>
<summary><b>SF3000 HD</b> (HDMI-out variant)</summary>

- 📦 Stock backup: [Q-ta-s releases](https://github.com/Q-ta-s/q-ta-s.github.io/releases) - grab the SF3000 HD / v1.1 backup
- Install folder: **`install_first/sf3000hd/`**
- Boot logo: included in this folder (no action needed)
- Shares the SF3500 display + driver, so it reports as **SF3500** in `log.txt` - that's expected.
</details>

<details>
<summary><b>SF3100</b></summary>

- 📦 Stock backup: [Q-ta-s releases](https://github.com/Q-ta-s/q-ta-s.github.io/releases)
- Install folder: **`install_first/sf3100/`**
- Boot logo: included in this folder (no action needed)
- SF3500-class hardware (same panel + driver); reports as **SF3500** in `log.txt`.
</details>

<details>
<summary><b>SF3500</b></summary>

- 📦 Stock backup: [Q-ta-s releases](https://github.com/Q-ta-s/q-ta-s.github.io/releases)
- Install folder: **`install_first/sf3500/`**
- Boot logo: included in this folder (no action needed)
</details>

<details>
<summary><b>GB350</b></summary>

- 📦 Stock backup: [Q-ta-s releases](https://github.com/Q-ta-s/q-ta-s.github.io/releases)
- Install folder: **`install_first/gb350/`**
- Boot logo: included in this folder (640×480 - no action needed)
</details>

---

## Step 2: Copy the TreeFrogUI payload

1. **Download** the latest TreeFrogUI release archive from the
   [Releases](https://github.com/tzubertowski/treefrog-ui/releases) page and extract it.
2. Copy these onto the **root** of your (stock) SD card, merging/overwriting:
   - `cubegm/`
   - `frogui/`
   - `roms/`
   - `MD/`
   - the docs/README (optional)
3. Copy the contents of **your device's** `install_first/<device>/` folder onto the
   SD root too (from Step 1). This sets the stock menu's autorun to launch
   TreeFrogUI and registers the boot hook for your device.

> [!NOTE]
> The `install_first/<device>/` step is what makes it boot: it points the stock
> menu's autorun at a dummy ROM (absolute path), overrides one stock core
> (`cores/libemu_md.so`) with the TreeFrogUI launcher, and drops in the
> device-correct boot logo. Your stock `icube`/`rkgame` are never touched.

---

## Step 3: Boot & add games

1. Eject the SD card safely, insert it back into the device, power on. The stock
   menu loads, then jumps straight into TreeFrogUI.
2. Put ROMs in the matching subfolders under `roms/` (e.g. `roms/GBA/`,
   `roms/FC/`). See the folder→system table in the [README](README.md#rom-folder-setup).

**Diagnostics:** logging is **off by default** (to spare your SD card). To turn it
on, create an empty file `log.txt` at the root of the card and reboot, then check
`/mnt/sdcard/log.txt`: look for `=== zhijack boot [your-device]`. If the device
name in brackets is wrong, you copied the wrong `install_first/` folder. Delete
`log.txt` to turn logging back off. See the
[Troubleshooting & logs](README.md#troubleshooting--logs) section for details.

---

## R36SX clones (R36HD, etc.)

Clones (e.g. **R36HD**) run the same stock software but boot a **different kernel
and device tree** for their hardware revision. If you flash the plain v2.7 backup
they won't boot (black screen), because that kernel/DTB doesn't match the clone.
Keep your clone's own boot files on top of the v2.7 setup:

1. **Backup your clone's stock boot files first** (from its **original** stock card,
   in `cubegm/` at the SD root; note the device tree is `dtb.bin`, not `*.dtb`):
   - `cubegm/vmlinux.uImage` - kernel
   - `cubegm/avp.uImage` - secondary boot image
   - `cubegm/dtb.bin` - device tree
2. **Restore the [R36SX v2.7 Minimal Backup](https://drive.google.com/file/d/12G3CQAWkaRMWbrY_YmGH8nstGbs1hB-O).**
3. **Copy your clone's 3 boot files** into the v2.7 SD's `cubegm/`, overwriting.
   This pairs your clone's kernel + DTB with the v2.7 userland.
4. **Do the standard TreeFrogUI install** on top (Steps 2–3). Treat the clone as an
   R36SX - use the `install_first/r36sx/` folder.

> [!TIP]
> Still won't boot? Your clone likely has yet another kernel/DTB revision.
> Double-check you copied **your own device's** boot files and that all three made it over.

---

## In-Game Shortcuts

**SELECT** is the function key (OnionOS-style):

- **`SELECT + START`** - in-game menu (PCSX4ALL opens its own menu instead).
- **`SELECT + R2`** - save state (slot 0).
- **`SELECT + L2`** - load state (slot 0).
- **`SELECT + R1`** - fast-forward: off → 2× → 3× → off (audio mutes). Per-core toggle.
- **`SELECT + B`** - hold to rewind. Per-core toggle.
- **`SELECT + L1`** - screenshot → `.bmp` in the `screenshots/` folder on your card.

---

## PlayStation 1 BIOS (strongly recommended)

PS1 has **two cores**, each with its own BIOS location - without a real BIOS they
fall back to **HLE**, which causes graphical glitches and **broken/hanging
memory-card saves** (e.g. Harvest Moon). Drop a real `scph1001.bin` in **both** so
either core works (filenames are case-insensitive - `SCPH1001.BIN` is fine):

| Core | ROM folder | BIOS path |
|------|-----------|-----------|
| **PCSX4ALL** | `PS` | `/mnt/sdcard/cubegm/cores/.pcsx4all/scph1001.bin` |
| **pcsx_rearmed** (lightrec) | `ps1r` | `/mnt/sdcard/cubegm/bios/scph1001.bin` |

(pcsx_rearmed also accepts `scph5501.bin` / `scph7001.bin` in `cubegm/bios/`.) With
the real BIOS, memory cards and compatibility work correctly.

**Speed toggles:** for heavy 3D games (e.g. Tekken 3) that don't run full speed,
open the PCSX4ALL menu with **`SELECT + L`** and turn on **Pixel Skip** and/or
**Interlace** - they trade a little image quality for a real speed boost.

---

## Arduboy

The **`arduboy`** folder uses the **Ardens** core (fast) and accepts both `.hex`
and `.arduboy` files. If a game misbehaves, the older cycle-accurate **arduous**
core is still available - put that game in an **`arduous`** folder instead (it is
much slower; `.hex` only).

---

## Troubleshooting & Feedback

- **Black screen / only battery icon after the boot logo:** you didn't start from a
  clean stock card, or copied the wrong device's `install_first/`. Restore the stock
  backup for your device (Step 1), then redo Steps 2–3.
- **Right analog stick doesn't do analog (R36SX):** expected, **cannot be fixed in
  software**. The R36SX wires the right stick to the **X / A / B / Y buttons**
  on/off only, no analog value exposed to apps. TreeFrogUI mirrors the face buttons
  and filters drift. Hardware limitation, not a bug.
- **Distorted / sideways boot logo:** make sure you copied **your device's**
  `install_first/<device>/` folder (it includes the correct logo) - not another device's.
- **Submit feedback anonymously:** [Feedback Form](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header).
- **GitHub Issues:** [repository](https://github.com/tzubertowski/treefrog-ui/issues).
