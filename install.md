# TreeFrogUI Installation Guide

This guide covers the installation of **TreeFrogUI** on the **Datafrog SF3000** handheld.

---

## Before you start

> [!IMPORTANT]
> **Prerequisite:** You must have the original **stock OS** installed on your SD card. TreeFrogUI runs on top of the stock operating system files. If you need a clean stock OS backup, you can download it here:
> 📦 **[SF3000 Stock OS SD Card Backup (7z)](https://github.com/Q-ta-s/q-ta-s.github.io/releases/download/sf3000/SF3000_sdcard.7z)**
> 
> **Backup your files:** Before making any modifications, backup your SD card, or at least the following files:
> - `cubegm/icube`
> - `cubegm/icube_start.sh`

---

## Installation Steps

1. **Download:** Get the latest TreeFrogUI release archive from the [Releases](https://github.com/tzubertowski/treefrog-ui/releases) page.
2. **Unzip:** Unzip the contents of the archive directly onto the root of your SD card. Choose to replace/overwrite files if asked.
3. **Boot:** Eject the SD card safely, insert it back into the device, and power it on. TreeFrogUI will launch automatically.
4. **ROMs:** Put your game ROMs in the corresponding subfolders inside the `roms/` directory on the root of your SD card (e.g., `roms/GBA/` for GBA games, `roms/FC/` for NES games). See the folder mapping table in the [README.md](README.md) for the full list of folder names.

---

## In-Game Shortcuts

When playing games, use the following button combinations:
- **`SELECT + START`** - Opens the in-game picoarch menu (for all cores *except* PCSX4ALL).
- **`SELECT + L`** - Opens the emulator menu (for PCSX4ALL *only*) or loads a state (slot 0, default) for other cores.
- **`SELECT + R`** - Saves a state (slot 0, default) for all cores *except* PCSX4ALL.

---

## Troubleshooting & Feedback

Since this is an initial release and was tested by a single developer, you might experience issues or bugs:
- **Submit Feedback Anonymously**: Help improve the project by submitting bugs, performance issues, or compatibility reports on the [v0.1.0 Feedback Form](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header).
- **GitHub Issues**: You can also open an issue on the [GitHub repository](https://github.com/tzubertowski/treefrog-ui/issues).

