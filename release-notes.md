# 🔴🔴🔴 THIS IS AN EXPERIMENTAL BUILD — DO NOT UPGRADE 🔴🔴🔴

# TreeFrogUI v2.0.0_a prerelease

This build explores a new MuOS-inspired theme renderer. It is an early compatibility port and is not a recommended update for daily use.

## MuOS-inspired theme renderer

- Adds an `.ini` scheme renderer that reads supported MuOS theme colors, transparency settings, typography, list and grid geometry, and per-screen scheme files. TreeFrogUI keeps its own runtime and maps supported theme settings onto FrogUI screens.
- Adds the `UI Theme` choice for built-in styles and installed schemes. Theme selection remains separate from Explore Content layout.
- Press **L2** in the Explore Content root to cycle Vertical, Horizontal, and System View in any theme. **Select** remains the core picker.
- MinUIfied Vertical uses a vertical launcher menu. MinUIfied Grid keeps its grid launcher.
- Adds experimental ports of Analogue, Art Book Next, CatOS ROYGBIV, Def-not-SNES, dsOS, GbOS, MinUIfied, Pip-Boy, Pip-Boy Frameless, and Pip-Boy Tube. Per-theme credits are retained in the scheme folders and summarized in `frogui/schemes/ATTRIBUTION.md`.
- This is a compatibility layer, not a `.muxthm` installer. MuOS binary fonts, partial opacity, animations, and screens without a FrogUI equivalent are not supported by this experiment.

## Other changes since v1.9.0_f

- Sets QuickNES as the default NES core.
- Fixes the GitHub Pages scraper instructions for muOS: extract its ZIP at the SD-card root so artwork lands under `MUOS/info/catalogue/`.

## Demo-only theme licensing note

This demo includes imported community theme assets with their upstream credits retained, despite the lack of per-theme license files in the downloaded archives. Their redistribution status remains unverified. This is a demo-only decision; do not carry these assets into a stable release until their individual terms or author permissions are confirmed. See `frogui/schemes/ATTRIBUTION.md` for the audit details.

For a fresh installation, use the full archive and matching `install_first/<device>/` files. To update an existing installation, copy `update.zip` to the SD-card root and reboot. **Do not use this experimental build to upgrade a daily-use card.**
