# 🔴🔴🔴 THIS IS AN EXPERIMENTAL BUILD — DO NOT UPGRADE 🔴🔴🔴

TreeFrogUI v2.0.0_d fixes theme installation on SF3000 and restores readable highlights and palette selection. Use a spare card for testing.

## Changes since v2.0.0_c

- Fixed a false “Theme archive contains no files” error on SF3000. The installer now counts files from the same BusyBox-compatible listing it validates, so extraction progress still works. TokyoNightOS, Art Book Next v2, and Catppuccin Frappe installed in QEMU with the MIPS BusyBox applet.
- Dismissing the install result returns to the archive list. Press **B** there to go back to Apps.
- Art Book Next v1 now uses the translucent highlight specified by the theme, so white text stays readable.
- PipBoy Frameless uses a readable background while Settings loads its wallpaper. PipBoy Tube shows the theme’s green focus marker on the selected row.
- Restored **Theme colours** under **Settings → Appearance** for TreeFrogUI and ProMinimal.

## Known limits

Imported themes can still differ from their MuOS originals. The reported freezes and missing PlayStation theme startup image remain under investigation. Third-party regression test themes and Red Viper binaries are not bundled.
