# 🔴🔴🔴 THIS IS AN EXPERIMENTAL BUILD — DO NOT UPGRADE 🔴🔴🔴

# TreeFrogUI v2.0.0_b — MuOS themes, now at home in TreeFrogUI

MuOS themes can now travel with you. TreeFrogUI adds a new MuOS-compatible renderer and an on-device `.muxthm` installer, so you can bring supported MuOS themes into FrogUI without replacing its launcher or runtime.

## Try a MuOS theme in TreeFrogUI

- Put a `.muxthm` file in `/ARCHIVE` on the SD card, open **Apps → Theme Installer**, and choose it; FrogUI installs it and shows a clear success or failure result.
- Pick the imported theme under **Settings → Theme**. The installer keeps existing themes and gives duplicate names a suffix.
- Themes installed by users stay in place when applying this release's `update.zip`.
- The renderer reads supported MuOS palettes, transparent colors, fonts, list and grid geometry, and per-screen scheme files, then maps them onto FrogUI views.
- Switch between Vertical, Horizontal, and System View in Explore Content with **L2**; **Select** remains the core picker.
- This release includes **TreeFrogUI_MuOS.muxthm** in `/ARCHIVE`, ready to install on MuOS with Archive Manager.

## Cleaner artwork and navigation

- Background art now has opaque, display-sized variants for 640×480 and 854×480 devices, avoiding alpha-related black areas and reducing resize work while navigating.
- Adds the original CC0 PrettyTreeFrog background pack and matching System View icon pack.
- MuOS home layouts with Explore, Apps, Favourites, History, and Settings screens now return to their correct FrogUI views, and Apps can exit back to the launcher.
- Theme previews and attribution travel with the included TreeFrogUI MuOS theme; BPreplay is distributed under the SIL Open Font License.
- Sets QuickNES as the default NES core and fixes the muOS scraper instructions so artwork extracts at the SD-card root.

## Compatibility notes

This is an experimental compatibility renderer, not the MuOS frontend. Themes that rely on unsupported MuOS screens, binary fonts, partial opacity, or LVGL-only animation may look different; the installer imports the theme's 640×480 assets and supported scheme data.

For a fresh installation, use the full archive and matching `install_first/<device>/` files. To update an existing installation, copy `update.zip` to the SD-card root and reboot. **Do not use this experimental build to upgrade a daily-use card.**
