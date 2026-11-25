# 🔴🔴🔴 THIS IS AN EXPERIMENTAL BUILD — DO NOT UPGRADE 🔴🔴🔴

TreeFrogUI v2.0.0_c fixes theme navigation and display regressions reported on v2.0.0_b. Use a spare card for testing.

## Changes since v2.0.0_b

- Imported themes without launcher artwork now get a usable main menu. In QEMU, TokyoNightOS and Catppuccin Frappe could open Explore Content and return with B.
- Imported wallpapers and navigation share a centered canvas on the SF3000’s 854×480 display.
- Background pack selection refreshes without an extra cursor move, and adjacent footer pills have a visible gap.
- Theme Installer shows install progress, accepts additional resolution profiles such as MinUIfied, and keeps the selected archive visible when scrolling. Put `.muxthm` files in `/ARCHIVE` on the SD card.
- Virtual Boy prefers Red Viper if you build and install it separately. Beetle VB remains the bundled fallback, and existing core overrides still apply. See the [Virtual Boy setup guide](https://github.com/tzubertowski/TreeFrogUI/blob/main/docs/cores/virtual-boy.md).
- The launcher preserves recent game logs during play so crash diagnostics can survive an interrupted session.

## Known limits

Imported MuOS themes can still differ from the original, especially if they depend on unsupported artwork or animation. The reported memory-related freezes and missing PS splash are still under investigation. Red Viper binaries and the third-party regression test themes are not bundled.
