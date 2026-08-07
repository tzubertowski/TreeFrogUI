> [!IMPORTANT]
> v1.0.12 changes the main navigation and fixes aspect-ratio scaling across supported devices.
>
> **[Submit anonymous feedback](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v1.0.12

- **Top-level tabs.** Recents, Games and Settings are now tabs instead of entries in the system list.
- **System View.** A third system-list style adds a paged console-icon grid. The background follows the highlighted system and falls back to the pack's main image when needed.
- **Icon packs.** System View artwork is selectable independently from backgrounds, with ten credited Onion community packs included. Bright icons automatically use a contrasting selection tile.
- **New defaults.** Fresh installs use System View, the Pixel icon pack, Red colours, friendly system names and 20% background dimming.
- **Simple controls.** Use L1/R1 to change tabs everywhere. Left/Right also changes tabs in Vertical; Horizontal and System View keep the D-pad for systems.
- **Faster Recents.** GameSwitcher screenshots are decoded once and kept in memory. Entering Recents no longer reloads the same image on every transition frame.
- **Faster return to Games.** The system list and selected background stay in memory instead of rescanning the SD card or decoding the same image after leaving Recents.
- **Cleaner navigation.** Tabs use one short crossfade instead of a slow panel slide. The active tab uses brighter theme text, inactive tabs are muted and bottom controls remain separate pillboxes.
- **Hardware aspect-ratio fixes.** Native, Integer, Fill and forced ratios account for both 640x480 and 854x480 panels. Fixed ratios reshape only the small core frame and leave final scaling to the hardware driver.
- **Volume control fix.** TreeFrogUI no longer restarts cubevol on launch, fixing Volume Down requiring repeated presses.
- **Small UI feedback.** Long lists have a scroll indicator. Saved actions show short confirmation messages.

**Updating:** copy `cubegm/` and `frogui/` over the card, then copy `install_first/<device>/` again. ROMs, saves and settings are untouched.

---

*Overview, features, install guide, troubleshooting and porting information are in the [README](README.md).*
