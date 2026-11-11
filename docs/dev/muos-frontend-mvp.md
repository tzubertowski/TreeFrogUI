# muOS frontend MVP exploration

The `muos_frontend_mvp` project is a separate sibling checkout, not a FrogUI
frontend rewrite. It hosts MustardOS frontend screens inside a libretro core
and supplies the missing host services through an adapter. FrogUI remains the
launcher/runtime and existing FrogUI cores remain responsible for games.

## What works in this MVP

- Main menu and linked MuOS screens render and navigate at the device-reported
  resolution.
- MinUIfied Horizontal uses MuOS's 2x4 grid style, avoiding its static menu
  screenshot being drawn behind a second menu.
- FrogUI folder-to-core assignments are exposed as MuOS assignments. Catalogue
  names use MuOS's system names so its normal folder artwork lookup can match.
- Game launch hands off to the selected FrogUI libretro core; shutdown and
  reboot use FrogUI's existing scripts.
- QEMU exercises navigation, linked screens, assignment, alternate core launch,
  power handoff, font loading, resolution, and collection creation.

## Boundaries and next work

The adapter is still experimental and lives outside this repository. The MuOS
frontend source changes are proposed separately to `MustardOS/frontend`; this
repository only owns the guarded TreeFrogUI deployment/rollback integration.
The card test so far covers the menu and theme, while QEMU covers the broader
host paths. More device testing is needed for storage catalogue artwork,
collections, nested MuOS modules, and low-memory handoff behavior.

MuOS permits arbitrary subfolders beneath `ROMS`; the adapter keeps FrogUI's
existing folder aliases instead of renaming or moving ROMs. Core assignment
metadata is what associates those folders with MuOS systems and catalogues.
