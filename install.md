# TreeFrogUI Installation Guide

This guide covers the installation of **TreeFrogUI** on the **Datafrog SF3000** and **R36SX** (firmware **v2.6** / **v2.7**) handhelds. The build auto-detects the device at boot.

> [!NOTE]
> **R36SX clones (R36HD, and likely SF3000HD — untested, worth checking):** these
> use the same software stack but ship **different kernels / device trees** per HW
> revision. Don't boot them on the generic v2.7 kernel — follow the
> [R36SX clones](#r36sx-clones-r36hd-etc) section below instead.

---

## Before you start

> [!IMPORTANT]
> **Prerequisite:** You must have the original **stock OS** installed on your SD card. TreeFrogUI runs on top of the stock operating system files. Clean stock OS backups:
> - 📦 **SF3000:** [Stock OS SD Card Backup (7z)](https://github.com/Q-ta-s/q-ta-s.github.io/releases/download/sf3000/SF3000_sdcard.7z)
> - 📦 **R36SX v2.6:** [Minimal Backup](https://drive.google.com/file/d/1xTCNNRKfQmFJr2Zkd1oCBRChuWiidIBD)
> - 📦 **R36SX v2.7:** [Minimal Backup](https://drive.google.com/file/d/12G3CQAWkaRMWbrY_YmGH8nstGbs1hB-O)
> 
> **Backup your files:** Before installing TreeFrogUI or restoring any stock backups, make sure to back up your current physical SD card, or at least the following files:
> - `cubegm/icube`
> - `cubegm/icube_start.sh`

---

## Installation Steps

1. **Download:** Get the latest TreeFrogUI release archive from the [Releases](https://github.com/tzubertowski/treefrog-ui/releases) page.
2. **Copy:** Copy over the extracted `sdcard/` contents directly to the **ROOT** of your SD card. Choose to replace/overwrite files when prompted.
3. **Boot logo (SF3000 only):** TreeFrogUI ships with the **R36SX** boot logo by default. If you are on an **SF3000**, run the included fixer on the SD card root to swap in the SF3000-format logo:
   - **Windows:** double-click `fix_bootlogo_sf3000.bat`
   - **Linux/macOS:** run `./fix_bootlogo_sf3000.sh`
   (R36SX users do nothing — the default is already correct.)
4. **Boot:** Eject the SD card safely, insert it back into the device, and power it on. TreeFrogUI will launch automatically.
5. **ROMs:** Put your game ROMs in the corresponding subfolders inside the `roms/` directory on the root of your SD card (e.g., `roms/GBA/` for GBA games, `roms/FC/` for NES games). See the folder mapping table in the [README.md](README.md) for the full list of folder names.

---

## R36SX clones (R36HD, etc.)

Clones (e.g. **R36HD**, and possibly **SF3000HD** — untested, worth checking) run
the same stock software but boot a **different kernel and device tree** for their
hardware revision. If you flash the plain v2.7 backup they won't boot (black screen
/ no display), because that kernel/DTB doesn't match the clone's hardware. The fix
is to keep your clone's own boot files on top of the v2.7 setup:

1. **Backup your clone's stock boot files first.** On your clone's **original**
   stock SD card these live in the **`cubegm/`** folder at the SD root. Copy these
   out and keep them safe (note the device tree is named `dtb.bin`, not `*.dtb`):
   - `cubegm/vmlinux.uImage` — kernel
   - `cubegm/avp.uImage` — secondary boot image
   - `cubegm/dtb.bin` — device tree
2. **Set up the v2.7 minimal backup.** Format/restore your SD card with the
   **R36SX v2.7 Minimal Backup**:
   [Minimal Backup](https://drive.google.com/file/d/12G3CQAWkaRMWbrY_YmGH8nstGbs1hB-O).
3. **Copy your clone's boot files over the v2.7 setup.** Drop the three files from
   step 1 into the v2.7 SD's **`cubegm/`** folder (SD root → `cubegm/`), overwriting
   the ones that came with it:
   - `cubegm/vmlinux.uImage`
   - `cubegm/avp.uImage`
   - `cubegm/dtb.bin`

   This pairs your clone's own kernel + device tree with the v2.7 userland.
4. **Do the standard TreeFrogUI install** on top (the [Installation Steps](#installation-steps)
   above). Treat the clone as an R36SX — do **not** run the SF3000 boot-logo fixer.

> [!TIP]
> If it still won't boot after this, your clone likely has yet another kernel/DTB
> revision. Double-check you copied **your own device's** boot files (not someone
> else's), and that all three files made it over.

---

## In-Game Shortcuts

When playing games, use the following button combinations:
- **`SELECT + START`** - Opens the in-game picoarch menu (for all cores *except* PCSX4ALL).
- **`SELECT + L`** - Opens the emulator menu (for PCSX4ALL *only*) or loads a state (slot 0, default) for other cores.
- **`SELECT + R`** - Saves a state (slot 0, default) for all cores *except* PCSX4ALL.
- **`SELECT + Y`** - Cycles fast-forward: **off → 2× → 3× → off**. Audio mutes while fast-forwarding.
- **`SELECT + B`** - Hold to rewind.

---

## PlayStation 1 BIOS (recommended)

PCSX4ALL works best with a **real PS1 BIOS**. Copy `scph1001.bin` to:

```
/mnt/sdcard/cubegm/cores/.pcsx4all/scph1001.bin
```

(The filename is matched case-insensitively, so `SCPH1001.BIN` also works.) If the
file is absent, PCSX4ALL falls back to an HLE BIOS that causes **graphical
glitches, worse performance, and broken/hanging memory-card saves** (e.g. Harvest
Moon). With the real BIOS, memory cards (`.pcsx4all/memcards/`) and compatibility
work correctly.

**Speed toggles:** for heavy 3D games (e.g. Tekken 3) that don't run full speed,
open the PCSX4ALL menu with **`SELECT + L`** and turn on **Pixel Skip** and/or
**Interlace** — they trade a little image quality for a real speed boost.

---

## Arduboy

The **`arduboy`** folder uses the **Ardens** core (fast) and accepts both `.hex`
and `.arduboy` files. If a game misbehaves, the older cycle-accurate **arduous**
core is still available — put that game in an **`arduous`** folder instead (it is
much slower; `.hex` only).

---

## Troubleshooting & Feedback

- **Right analog stick doesn't do analog (R36SX):** this is expected and **cannot be fixed in software**. On the R36SX the right stick is wired to act like the **X / A / B / Y buttons** — it only sends on/off presses, with no analog "how far / which direction" value, and the console never exposes a real analog reading to apps. So in TreeFrogUI the right stick mirrors the face buttons (accidental drift is filtered out). It is a hardware limitation, not a bug.
- **Distorted / sideways boot logo (SF3000):** the package defaults to the R36SX logo. On SF3000 run `fix_bootlogo_sf3000.bat` (Windows) or `fix_bootlogo_sf3000.sh` (Linux/macOS) from the SD card root to install the correct SF3000 logo.
- **Black Screen / Only Battery Icon Visible:** If nothing loads or only the battery icon is visible after the boot logo, set up your SD card with the clean stock OS backup for your device first, then copy the TreeFrogUI files over:
  - **SF3000:** [Stock OS SD Card Backup (7z)](https://github.com/Q-ta-s/q-ta-s.github.io/releases/download/sf3000/SF3000_sdcard.7z)
  - **R36SX v2.6:** [Minimal Backup](https://drive.google.com/file/d/1xTCNNRKfQmFJr2Zkd1oCBRChuWiidIBD)
  - **R36SX v2.7:** [Minimal Backup](https://drive.google.com/file/d/12G3CQAWkaRMWbrY_YmGH8nstGbs1hB-O)
- **Submit Feedback Anonymously**: Help improve the project by submitting bugs, performance issues, or compatibility reports on the [v0.1.0 Feedback Form](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header).
- **GitHub Issues**: You can also open an issue on the [GitHub repository](https://github.com/tzubertowski/treefrog-ui/issues).

