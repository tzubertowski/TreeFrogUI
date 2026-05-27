# FrogUI Installation Guide

This guide covers the installation of **FrogUI** for **Datafrog SF2000** and **GB300** handhelds.

---

## Table of Contents
- [1. Prerequisites](#1-prerequisites)
- [2. Installing FrogUI](#2-installing-frogui)
- [3. Using FrogUI](#3-using-frogui)
  - [3.1 Adding ROMs](#31-adding-roms)
  - [3.2 Launching Games](#32-launching-games)
- [4. Optional: Tips & Tricks](#4-optional-tips--tricks)
  - [4.1 Customizing Themes](#41-customizing-themes)
  - [4.2 Adding Thumbnails](#42-adding-thumbnails)
  - [4.3 Recent Games History](#43-recent-games-history)
- [5. Updating GB300 to v2](#5-updating-gb300-to-v2-software-version)

---

## 1. Prerequisites

- A Datafrog SF2000 or GB300 handheld with stock operating system (or multicore, as it will be overridden)
- An SD card reader (via phone or PC) to transfer files to the SD card
- If you're using a **GB300**, make sure you're on **GB300 v2**. See [Updating GB300 to v2 software version](#5-updating-gb300-to-v2-software-version)

---

## 2. Installing FrogUI

1. Insert your SD card into your computer or phone
2. Download the [latest stable release of FrogUI](https://github.com/tzubertowski/FrogUI/releases)
   - ⚠️ **Make sure you download the archive for your correct device (GB300 or SF2000)**
3. Unzip the archive
4. Copy the contents to your SD card
5. Put the SD card back into your device and power it on
6. Done! FrogUI is now installed 🎉

---

## 3. Using FrogUI

### 3.1 Adding ROMs

1. Place **unzipped** ROMs into their respective system folders under `sd:/roms/*`
2. Check the list of supported systems and emulators in the **[How to Use Guide](HOW_TO_USE.md#complete-supported-systems-list)**
3. Example:
   - To add *Pokémon Fire Red*, copy the file like this:
     ```
     sd:/roms/gba/PokemonFireRed.gba
     ```
4. **No ROM list regeneration needed** - FrogUI scans directories dynamically, so new games appear immediately

### 3.2 Launching FrogUI
**To launch FrogUI:**
1. Power on your device
2. UI will boot to FrogUI splash screen
3. Press **A** to launch


### Navigation Controls

Once FrogUI is running, see the **[How to Use Guide](HOW_TO_USE.md)** for complete usage instructions including:
- Navigation controls
- Adding thumbnails
- Customizing themes
- Recent games history
- And more...

---

## 4. Updating GB300 to v2 Software Version

If you're using GB300 with v1 firmware or you're not sure:

1. Format the SD card to **FAT32**
2. Download:
   - [Minimal backup](https://archive.org/details/sd-card-default-sem-r-0-ms_202501)
3. Unzip the archive **directly** to the SD card
   - You should now see folders like `bios`, `resources`, `roms`, etc. on the root
4. Install Multicore following the [official guide](https://retromods.pl/blog/gb300-setup/)
5. Done! You can now follow the [FrogUI installation instructions](#2-installing-frogui)

---

## 5. Next Steps

That's it! FrogUI is now installed.

📖 See the **[How to Use Guide](HOW_TO_USE.md)** for detailed instructions on using FrogUI, adding thumbnails, customizing themes, and more.

---

## Troubleshooting

### FrogUI won't boot
- Verify the core file is at `sd:/cores/menu/core_87000000`
- Check that your device is on v2 firmware (GB300)

### Games won't launch
- Ensure ROMs are in the correct folders under `sd:/roms/`
- Verify the game file extension matches the console folder name
- Check that the appropriate core is installed in Multicore

### No thumbnails showing
- Verify `.res` folder exists in the same directory as your ROMs
- Check thumbnail filenames match ROM filenames exactly (without extension)
- Ensure thumbnails are in RGB565 format

### Debug logs

⚠️ **ONLY USE WHEN A DEVELOPER ASKS YOU, OR WHEN DEBUGGING AS A DEVELOPER**

Debug logging can cause performance degradation. Only enable when troubleshooting:

1. Create `sd:/app/log.txt` to enable debug logging
2. Check the file for FrogUI debug information
3. **DELETE `sd:/app/log.txt` WHEN DONE** - The presence of this file reduces performance
4. Check device `LOG.TXT` on SD card root for runtime errors

---

Happy gaming! 🕹️
