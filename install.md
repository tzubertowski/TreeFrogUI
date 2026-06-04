# TreeFrogUI Installation Guide

This guide covers the installation of **TreeFrogUI** on the **Datafrog SF3000** and **R36SX** (firmware **v2.6** / **v2.7**) handhelds. The build auto-detects the device at boot.

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

## In-Game Shortcuts

When playing games, use the following button combinations:
- **`SELECT + START`** - Opens the in-game picoarch menu (for all cores *except* PCSX4ALL).
- **`SELECT + L`** - Opens the emulator menu (for PCSX4ALL *only*) or loads a state (slot 0, default) for other cores.
- **`SELECT + R`** - Saves a state (slot 0, default) for all cores *except* PCSX4ALL.

---

## Troubleshooting & Feedback

- **Distorted / sideways boot logo (SF3000):** the package defaults to the R36SX logo. On SF3000 run `fix_bootlogo_sf3000.bat` (Windows) or `fix_bootlogo_sf3000.sh` (Linux/macOS) from the SD card root to install the correct SF3000 logo.
- **Black Screen / Only Battery Icon Visible:** If nothing loads or only the battery icon is visible after the boot logo, set up your SD card with the clean **[Stock OS Backup](https://github.com/Q-ta-s/q-ta-s.github.io/releases/download/sf3000/SF3000_sdcard.7z)** first, then copy the TreeFrogUI files over.
- **Submit Feedback Anonymously**: Help improve the project by submitting bugs, performance issues, or compatibility reports on the [v0.1.0 Feedback Form](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header).
- **GitHub Issues**: You can also open an issue on the [GitHub repository](https://github.com/tzubertowski/treefrog-ui/issues).

