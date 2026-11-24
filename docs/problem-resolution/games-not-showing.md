# Games not showing

If some or all of your games are missing from the game list, the problem is usually related to the File Cache or incorrect ROM folder locations and file formats.

The following solutions were tested on an SF3000HD.

## 1. Clear or rebuild the File Cache

One of the most common reasons games do not appear is the File Cache feature.

The cache was introduced in FrogUI as Folder Cache in commit `6aca15f` on July 28, 2026, and renamed to File Cache on July 31, 2026.

TreeFrogUI v1.0.14 (August 15, 2026) is the first release tag whose FrogUI submodule includes this feature.

### Option A: Rebuild Cache Files (recommended)

If your installed TreeFrogUI version provides this option:

1. Turn on your device.
2. Open the TreeFrogUI settings.
3. Find and select **Rebuild Cache Files**.
4. Wait for the process to finish.
5. Return to your game list and check whether your games appear.

This is the easiest way to rebuild the cache without manually accessing the SD card.

### Option B: Manually clear the cache

If the rebuild option is unavailable or does not solve the problem:

1. Turn off your device.
2. Remove the SD card and connect it to your computer.
3. Open the `frogui/` folder on the SD card.
4. Delete the `cache` folder inside `frogui/`.
5. Safely eject the SD card and put it back into your device.
6. Turn on your device and check whether your games appear again.

### Preventing the issue

If you do not want to use this feature, you can disable the File Cache option in the TreeFrogUI settings.

This prevents the cache from being used again. [ if your library is big, the list opening can be slower. ]

## 2. Check your ROM folder locations and file formats

Depending on where you downloaded your Stock OS image, the default ROM folder structure may be different.

TreeFrogUI expects ROMs to be placed in the correct system folder.

The general folder structure should look like this:

```text
/roms/
  ├── SNES/
  ├── GBA/
  ├── MAME/
  ├── NDS/
  └── PS/
```

Each ROM must be placed in the folder corresponding to its system or emulator core.

### Check your ROM file extensions

Some systems also require specific file formats. For example:

| System            | Expected format |
| ----------------- | --------------- |
| MAME              | `.zip`          |
| Nintendo DS       | `.nds`          |
| PlayStation 1     | `.iso` or `.img`|
| SNES              | `.sfc` or `.smc`|
| Game Boy Advance  | `.gba`          |

Make sure your ROMs are in the correct folders and use supported file extensions.

If your games are stored in a different directory, move them to the appropriate folder under `/roms/`.

## Tested device

- **Device:** SF3000HD
- **TreeFrogUI version:** [Add the exact version tested]

If neither solution fixes the problem, consider sharing your device model, TreeFrogUI version and ROM folder structure when reporting the issue.
