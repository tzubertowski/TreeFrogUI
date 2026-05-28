# TreeFrogUI Installation Guide

This guide covers the installation of **TreeFrogUI** on the **Datafrog SF3000** handheld.

---

## Before you start

> [!IMPORTANT]
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
- **`SELECT + START`** - Opens the in-game menu (picoarch menu for all libretro cores, or emulator menu for PCSX4ALL).
- **`SELECT + L`** - Load state (slot 0, default).
- **`SELECT + R`** - Save state (slot 0, default).

---

## Troubleshooting & Feedback

Since this is an initial release and was tested by a single developer, you might experience issues or bugs:
- **Submit Feedback Anonymously**: Help improve the project by submitting bugs, performance issues, or compatibility reports on the [v0.1.0 Feedback Form](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header).
- **GitHub Issues**: You can also open an issue on the [GitHub repository](https://github.com/tzubertowski/treefrog-ui/issues).

