## TreeFrogUI v1.4.0

### What's new

- **Cleaner SF-class audio:** mono output by default, steadier buffering, and fewer crackles on demanding cores.
- **Scrollable core menus:** long key-binding menus no longer run past the bottom of the 854×480 display.
- **Physical FN input:** R36SX FN-button support in picoarch, contributed by [@ozkaoz](https://github.com/ozkaoz) in [TreeFrogUI_picoarch#1](https://github.com/tzubertowski/TreeFrogUI_picoarch/pull/1). Thank you!
- **Cumulative updates:** this and later `1.x` update ZIPs can update any supported `1.x` installation from v1.1.0_c onward.
- **USB MTP mode:** new guided USB MODE screen and PC file access for the SD card, with safe A/B entry and exit handling.
- **MTP compatibility:** KDE/libmtp-compatible device identity, complete object metadata, and host-to-console file writes.
- **Reliable USB re-entry:** exiting USB mode now fully resets the gadget controller, so MTP can be started again without rebooting the console.
- **Quiet by default:** USB and FrogUI diagnostics now follow the existing `log.txt` opt-in switch; normal use no longer produces packet-level log spam.
- **USB Mode in Apps:** USB Mode now lives with the other utilities instead of appearing in the Games library.
- **OTG ROM library:** FAT32 USB storage with a `roms/` folder can be selected as a separate Games-library source. The UI clearly shows whether OTG storage is connected and falls back to SD when it is not.

### Contributors

- **Jose Silva** and **[MartStartIV](https://github.com/MartStartIV)** — USB OTG storage and external-ROM-library work. [MartStartIV on YouTube](https://www.youtube.com/@MartStartIV)

### Install or update

**Recommended:** use the [TreeFrogUI Installer](https://github.com/tzubertowski/TreeFrogUI-installer/releases/latest) for both fresh installations and updates.

Manual fallback:

- Fresh install: download `TreeFrogUI_v1.4.0.zip` and apply `install_first/<device>/`.
- Update: copy `update.zip` to the SD-card root and reboot.

This is a prerelease for wider device testing before promotion to stable.
