## What's new in TreeFrogUI v1.4.0

### R36SX FN button

- Added physical FN-button support to the FrogUI button-mapping wizard.
- R36SX devices expose a 15-step mapping wizard ending in **FN**.
- FN is gated by device detection, so other devices keep the normal 14-button mapping.

### Contributor

- **[@ozkaoz](https://github.com/ozkaoz)** — R36SX FN-button implementation and physical validation.

### Install

- Recommended: use the [TreeFrogUI Installer](https://github.com/tzubertowski/TreeFrogUI-installer/releases/latest).
- Manual fresh install: apply `install_first/<device>/` from the v1.4.0 package.
- Manual update: copy `update.zip` to the SD-card root and reboot.
