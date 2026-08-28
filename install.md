# TreeFrogUI Installation Guide

One TreeFrogUI package supports **seven devices** - it auto-detects which one it is
at boot. Pick your device below, grab its required backup, then follow the same
install steps for everyone.

Supported: **R36SX** (v2.6 / v2.7) · **R36HD** · **SF3000** · **SF3000 HD** ·
**SF3100** · **SF3500** · **GB350**.

> [!CAUTION]
> # 🔴 **DO NOT USE THE FACTORY/PREINSTALLED STOCK OS** 🔴
>
> **Format the SD card and set it up fresh with the exact backup linked below.
> This is not optional. Installing over the stock OS causes missing audio, broken
> controls, display problems, crashes, and boot failures.**

> **Words you'll see (plain English):**
> - **SD card** = the little memory card your games live on.
> - **"root of the SD card"** = the **top level** of the card, **not inside any folder**. When you open the card on your PC and see folders like `cubegm`, `roms`, `frogui`, that first screen **is** the root.
> - **folder** = a directory you make on the card (e.g. `roms/GBA`). The folder **name** decides which system it runs.
> - **ROM** = a game file.
> - **BIOS** = an extra system file some consoles need to run (you supply it; see [BIOS files](#bios-files-required)).
> - **keep zips zipped** = for arcade games, do **not** unzip the `.zip`. Drop it in as-is.

---

## Step 1: Get the REQUIRED PROVIDED backup for YOUR device

Click your device to expand. Download the exact backup from the link in this
guide, **format the SD card**, and set it up fresh from that backup before adding
any TreeFrogUI files. Do not install in place, retain old OS files, merge with the
factory card, or substitute a different backup.

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
<summary><b>R36HD</b> (R36SX clone)</summary>

- 📦 **Use the [R36HD stock backup](https://github.com/tzubertowski/H.OS_stock_backup/releases/download/stock-backups-v1/R36HD_stock.7z) as the base.**
- If that release is unavailable, the [R36SX v2.6 Minimal Backup](https://drive.google.com/file/d/1xTCNNRKfQmFJr2Zkd1oCBRChuWiidIBD) is the compatible fallback.
- The factory R36HD/R36SX v2.7 protected menu binary does not reach the TreeFrogUI hook and stalls at the boot logo. The tested adapter fix uses the v2.6 boot/menu stack.
- The release applies the proven **`install_first/r36sx/`** hook for R36HD;
  the installer selects this automatically and includes the driver fallback.
- Full details: [R36SX clones (R36HD, etc.)](#r36sx-clones-r36hd-etc)
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

- 📦 [SF3500 Stock Backup](https://github.com/Q-ta-s/q-ta-s.github.io/releases/tag/sf3500)
- 📦 Alternate backup (**newer SF3500 revisions**): [SF3500 v1.1 Stock Backup](https://github.com/Q-ta-s/q-ta-s.github.io/releases/tag/sf3500_1) - if your SF3500 **won't boot the standard backup above** (some later hardware revisions don't), restore this one instead. Everything else is identical.
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
2. Copy these onto the **root** of the SD card restored from the provided backup,
   merging/overwriting:
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

## Offline updates

Releases provide two downloads:

- `TreeFrogUI_<version>.zip` is the complete clean-card installation.
- `update.zip` is the automatic offline update.

To update, copy the official `update.zip` directly to the SD-card root, safely
eject and boot. TreeFrogUI verifies
every file, applies the universal payload plus the correct device launcher, and
deletes `update.zip` only after success. Failures retain it for another boot and
are recorded in `update.log` at the SD-card root.

Each `update.zip` is a delta from the preceding numeric release line, ignoring
letter/suffix rebuilds. For example, every `v1.0.13_*` package is compared with
the newest retained `v1.0.12*` full release, never another `v1.0.13_*` build.
The installed base version is checked before anything changes; otherwise use
the current full ZIP.

The update replaces FrogUI settings, keymaps and emulator configuration so new
required options and migrations take effect. Previous configs are saved under
`.treefrog-update/backup-<version>/`. ROMs, BIOS files, saves, save states,
screenshots, favourites, recents, play-time data and personal media are not
deleted.

Versions released before the offline updater must be upgraded manually once,
including `install_first/<device>/`. Automatic update ZIPs work after that
one-time bootstrap.

---

## R36SX clones (R36HD, etc.)

The tested **R36HD / R36S-H.05-V1.2** adapter path uses the R36SX v2.6 boot and
menu stack. Its `rkgame`, kernel, device tree, AVP image and startup scripts match
the known-working adapter fix, while the factory R36HD/R36SX v2.7 protected
`rkgame` never loads the TreeFrogUI hook and stalls at the boot logo.

1. **Restore the [R36HD stock backup](https://github.com/tzubertowski/H.OS_stock_backup/releases/download/stock-backups-v1/R36HD_stock.7z)** to a freshly FAT32-formatted card. (The R36SX v2.6 backup remains a compatible fallback.)
2. **Copy the current TreeFrogUI universal payload** to the card as described in Steps 2-3.
3. **Apply `install_first/r36sx/`** so the R36HD display and hook configuration are installed.

Do not restore the factory R36HD boot/menu files over this setup, and do not use
the R36SX v2.7 backup as the R36HD base.

> [!IMPORTANT]
> **Use `install_first/r36sx/` for R36HD.** R36HD is an R36SX-compatible clone;
> this overlay carries the proven driver and its automatic safe-variant fallback.

> [!TIP]
> Still won't boot? Your clone likely has yet another kernel/DTB revision.
> This procedure is verified for R36S-H.05-V1.2-style R36HD hardware; retain a
> backup of your original card when testing another clone revision.

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

PS1 has two cores, each with its own BIOS location - without a real BIOS they
fall back to HLE, which causes graphical glitches and broken/hanging memory-card
saves. Full setup, BIOS paths, and speed toggles: 📖 **[docs/cores/ps1.md](docs/cores/ps1.md)**.

---

## Arduboy

The **`arduboy`** folder uses the **Ardens** core (fast) and accepts both `.hex`
and `.arduboy` files. If a game misbehaves, the older cycle-accurate **arduous**
core is still available - put that game in an **`arduous`** folder instead (it is
much slower; `.hex` only).

---

## Troubleshooting & Feedback

- **Black screen / only battery icon after the boot logo:** you didn't start from a
  required provided backup, or copied the wrong device's `install_first/`.
  Restore the exact linked backup for your device (Step 1), then redo Steps 2-3.
- **Right analog stick doesn't do analog (R36SX):** expected, **cannot be fixed in
  software**. The R36SX wires the right stick to the **X / A / B / Y buttons**
  on/off only, no analog value exposed to apps. TreeFrogUI mirrors the face buttons
  and filters drift. Hardware limitation, not a bug.
- **Distorted / sideways boot logo:** make sure you copied **your device's**
  `install_first/<device>/` folder (it includes the correct logo) - not another device's.
- **Sleep / power-button standby:** TreeFrogUI gives you **true hibernation**
  instead. Turn on **Quick Resume** + **Auto-Save/Auto-Load** (Settings) and the
  device boots straight back into your game exactly where you left off, surviving
  a full power-off with zero battery drain - better than sleep. Stock sleep/
  standby is **not supported and won't be** (it can hang the display on wake on
  R36SX and SF3500-class), so **Disable Sleep is on by default**. You're not
  missing anything.
- **PC Engine (`pce`) crashes or resets when returning from the in-game menu**
  (seen on some devices, e.g. SF3000 HD - not universal): turn on **Disable
  Soft Reset** in the core's options (SELECT+START → Core Options). The stock
  soft-reset combo can fire spuriously on menu return.
- **Submit feedback anonymously:** [Feedback Form](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header).
- **GitHub Issues:** [repository](https://github.com/tzubertowski/treefrog-ui/issues).
