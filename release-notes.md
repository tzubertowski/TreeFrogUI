> [!IMPORTANT]
> v1.0.12 changes the main navigation and fixes aspect-ratio scaling across supported devices.
>
> **[Submit anonymous feedback](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v1.0.12

- **Top-level tabs.** Recents, Games and Settings are now tabs instead of entries in the system list.
- **Simple controls.** Use L1/R1 to change tabs everywhere. Left/Right also changes tabs in the vertical Games view. Horizontal keeps Left/Right for scrolling systems.
- **Faster Recents.** GameSwitcher screenshots are decoded once and kept in memory. Entering Recents no longer reloads the same image on every transition frame.
- **Faster return to Games.** The system list and selected background stay in memory instead of rescanning the SD card or decoding the same image after leaving Recents.
- **Cleaner navigation.** Tabs use one short crossfade instead of a slow panel slide. The active tab uses brighter theme text, inactive tabs are muted and bottom controls remain separate pillboxes.
- **Hardware aspect-ratio fixes.** Native, Integer, Fill and forced ratios account for both 640x480 and 854x480 panels. Fixed ratios reshape only the small core frame and leave final scaling to the hardware driver.
- **Volume control fix.** TreeFrogUI no longer restarts cubevol on launch, fixing Volume Down requiring repeated presses.
- **Small UI feedback.** Long lists have a scroll indicator. Saved actions show short confirmation messages.

**Updating:** copy `cubegm/` and `frogui/` over the card, then copy `install_first/<device>/` again. ROMs, saves and settings are untouched.

---

*Overview, features, install guide, troubleshooting and porting information are in the [README](README.md).*
