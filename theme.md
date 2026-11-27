# Customising TreeFrogUI

TreeFrogUI supports colour themes, custom fonts, one global wallpaper, per-system backgrounds and game thumbnails.

---

## Box art, game covers and thumbnails

TreeFrogUI can show box art, cover images or gameplay thumbnails beside the selected game. The Recents game switcher prefers box art; when none is available, it uses the latest gameplay screenshot instead.

### Recommended: get box art automatically in three steps

Use **[Mini Scraper for CFW](https://github.com/tzubertowski/mini-scraper-cfw/releases)** to download box art without finding, resizing or renaming every image yourself. Ready-to-run desktop ZIPs are available for Windows x64, Linux x64 and macOS ARM64; the app needs no account and includes everything it needs.

1. Download the latest desktop ZIP for your computer, extract it and run Mini Scraper.
2. Choose the SD card or ROM folder, confirm the detected **TreeFrogUI** format, and leave artwork source option 1 selected: **Automatic (Libretro Thumbnails) · no login**.
3. Press **Add artwork**.

Mini Scraper matches covers to the ROM filenames and writes each image beside its ROM using the filename TreeFrogUI expects. Existing artwork is preserved unless you explicitly choose to replace it.

### Add box art manually

Place each cover image in a hidden `.res/` folder next to the ROM. Match the ROM filename without its extension:

```text
roms/GBA/Advance Wars.gba
roms/GBA/.res/Advance Wars.png
```

Name the image after the ROM filename without its extension, then use a supported image extension: `.png`, `.jpg`, `.jpeg` or `.bmp`.

PNG, JPG, JPEG and BMP images can be any resolution. Images larger than the 250×200 preview area are downscaled automatically with their aspect ratio preserved. PNG transparency is supported. Keep files reasonably small because they are decoded while browsing.

Older headerless `.rgb565` thumbnail sets also work at these fixed sizes: `64×64`, `128×128`, `160×160`, `200×200`, `250×200`, and `200×250`.

In-game savestate and last-screen images are captured automatically and need no manual setup.

---

## Appearance settings

### Install a MuOS theme on the device

Use TreeFrogUI [v2.0.0_d](https://github.com/tzubertowski/TreeFrogUI/releases/tag/v2.0.0_d) or later. This version includes the fix for theme installation on SF3000.

1. Pick a theme from the [MustardOS theme library](https://theme.muos.dev/) and download its `.muxthm` archive. Keep the file zipped.
2. Copy it to **`ARCHIVE/` at the root of the SD card**, next to `cubegm/` and `roms/`. Create `ARCHIVE/` if needed.
3. On the handheld, open **Apps → Theme Installer**, highlight the archive and press **A**. Wait for **Install Complete**. Press **B** to return to the archive list, then **B** again to return to Apps.
4. Open **Settings → Appearance → UI theme**. If Appearance is a folder, open it with **A** first. Use **Left/Right** to select the installed theme. You can return here and select **TreeFrogUI** or **ProMinimal** at any time.

If a theme with that name is already installed, TreeFrogUI keeps both copies and adds a suffix to the new one. Imported themes can show a separate main menu. From the Explore Content system list, press **B** to return to that menu.

### How compatibility works

TreeFrogUI imports supported MuOS scheme settings, colours, and artwork into `frogui/schemes/`. It draws them with FrogUI's own renderer. The importer requires a `640x480` asset folder and a default scheme profile. On SF3000's 854×480 panel, the imported 640×480 wallpaper and navigation use a centered canvas. Theme features such as animated artwork and platform-specific screens may render differently. See the [FrogUI theme format notes](https://github.com/tzubertowski/FrogUI/blob/r36sx/THEMING.md) for the supported fields.

Open **`>> Settings`** at the bottom of the main system list. Use Up/Down to select an option and Left/Right to change it. Press A or B to close Settings and save.

| Setting | What it changes |
|---|---|
| **UI theme** | Selects TreeFrogUI, ProMinimal or an installed MuOS theme |
| **Theme colours** | Selects a palette for TreeFrogUI or ProMinimal. Imported themes use their own colours |
| **Background Theme Pack** | Selects a folder of themed background artwork |
| **Explore Content layout** | Press **L2** in Explore Content to cycle Vertical, Horizontal and System View |
| **Icon Pack** | Chooses System View artwork independently from backgrounds |
| **Friendly System Names** | Expands folder codes such as `ps` and `gba` |
| **Font** | Menu typeface |
| **Brightness** | Screen brightness |
| **Animations** | Background crossfades and other UI motion |
| **Battery Colour Mode** | Uses a green, blue or red battery status light |
| **Background Images** | Enables wallpapers and per-system backgrounds |
| **Wallpaper** | Selects one image for every TreeFrogUI screen |
| **Wallpaper Fit** | Controls how the selected wallpaper fills the display |
| **Hide Extensions** | Hides file extensions in game lists |
| **Hide Empty Folders** | Hides system folders with no games |

Settings are stored in `/mnt/sdcard/frogui/settings.txt`.

### Background theme packs

Theme packs live in a folder under `/mnt/sdcard/frogui/theme-packs/`. Select one in
Settings → Appearance → **Background Theme Pack**. Packs use the same filenames
as per-system backgrounds: `main.jpg`, `settings.jpg`, `recents.jpg`,
`favourites.jpg`, or a ROM folder name such as `gba.jpg`. The shipped
`Art_Book_Next` pack preserves the original artwork. The test packs include
per-system artwork adapted from **Elementerial**, **Iconic** and
**PlayStation-X**.

`Art_Book_NextUI` is the updated NextUI resource set adapted from
[Leviathanium's ArtBookNextUI theme](https://github.com/Leviathanium/NextUI-Themes/tree/main/Catalog/Themes/ArtBookNextUI.theme).
It is center-cropped to the supported 854×480 display size and keeps the
original pack available for comparison.

`Nao_Black` is another adapted background set from
[Leviathanium's Nao-Black theme](https://github.com/Leviathanium/NextUI-Themes/tree/main/Catalog/Themes/Nao-Black.theme).

## FroggyThemes manager

The optional FroggyThemes application is available from the Apps view when the
release includes its launcher. It manages installed folders under
`/mnt/sdcard/frogui/theme-packs/` and `/mnt/sdcard/frogui/icon-packs/`, applies matching
background/icon presets, and leaves the artwork in place. Press Y to cycle
alphabetical, reverse-alphabetical, and newest-first order; press Select + Start
to return to TreeFrogUI.

`PrettyTreeFrog` is an original CC0 pack with dark rainforest scenes and
matching per-system artwork for the SF3000/SF3500 family. Its companion
`PrettyTreeFrog` system-icon pack is installed separately and can be mixed with
other background packs.

The supplied packs include explicit artwork aliases for the short TreeFrogUI
folder names used on the device (for example `a26`, `m2k`, `pcesgx` and
`ps1r`), so these systems do not fall back to the generic main image.
ScummVM uses `scummvm.jpg` in each theme pack. Each supplied pack has its own
composition, matched to that pack's artwork layout.

Built-in backgrounds ship as opaque panel-sized images. FrogUI selects the
matching `640x480/` or `854x480/` folder from the detected display; 854×480
source files remain the fallback when no normalized copy is needed. PNG
transparency is flattened into the variants so it cannot expose black decoder
pixels.

### Which background is used

| Background Images | Wallpaper | Result |
|---|---|---|
| Off | Any value | Plain background using the selected theme |
| On | None | Per-system and per-screen backgrounds |
| On | An image | That wallpaper on every screen |

A selected wallpaper overrides per-system art. Turning **Background Images** off only hides the images; it does not forget your wallpaper choice.

---

## System list styles

**Vertical** is the standard text list. **Horizontal** is the animated
left/right system carousel. **System View** is a four-column, two-row console
grid inspired by OnionOS. It uses the selected theme colours and L1/R1 for the
top-level tabs. Its background follows the highlighted
system and uses `main.*` as the fallback. Use the D-pad to move between systems;
pages follow the selection automatically.

System View icons live in `/mnt/sdcard/frogui/system-icons/` and are named after
ROM folders, for example `gba.png` and `ps1.png`. Custom folders without an icon
fall back to initials. Extra sets live in
`/mnt/sdcard/frogui/icon-packs/<pack>/`; select them with **Icon Pack** without
changing the colour theme or background pack. Transparent colour PNGs are
supported. The supplied collection credits every Onion pack and creator in
`frogui/icon-packs/README.md`.

### Horizontal system picker

Set Settings → Appearance → **Style** to **Horizontal**. Choose colours
separately with **Theme**; the carousel uses the selected theme.

The main system screen changes to a left/right carousel. System names slide with the selection, wrap at both ends, and the background crossfades to the selected system. Game lists, Recents, Favourites and Settings keep the standard vertical layout.

The carousel uses the same per-system background files described below. It also supports `recents.*`, `favourites.*`, `settings.*` and the `main.*` fallback. Turn **Animations** off for instant movement and background changes.

**Friendly System Names** works in every style. Turn it on to show names such
as **PlayStation** and **Game Boy Advance** instead of the actual `ps` and `gba`
folder names.

---

## File cache

**File Cache** is off by default. Turn it on only if repeated library scans are
slow. **Rebuild File Cache** clears old entries, enables the cache and rebuilds
the main library index immediately. Individual system folders refresh when
opened.

---

## Global wallpaper

1. Copy an image to `/mnt/sdcard/frogui/wallpapers/`.
2. Restart TreeFrogUI so it rescans the folder.
3. Open Settings → Appearance → **Wallpaper** and select the filename.
4. Set **Wallpaper Fit** to suit the image.

Supported formats are `.png`, `.jpg`, `.jpeg`, and `.bmp`. Extensions are matched without regard to case. TreeFrogUI lists up to 63 custom wallpapers.

Any image size works. For the least scaling, use the native panel size:

- **640×480** for R36SX, R36 HD and GB350.
- **854×480** for SF3000, SF3000 HD, SF3100 and SF3500.

### Wallpaper fit modes

| Mode | Result |
|---|---|
| **Fill** | Preserves aspect ratio, covers the display and crops the excess |
| **Fit** | Preserves aspect ratio and shows the whole image; unused space uses the theme colour |
| **Stretch** | Fills the display without cropping; may distort the image |
| **Center** | Keeps the original pixel size, centred; large images are cropped |
| **Tile** | Repeats the image at its original size |

Use **None** under Wallpaper to return to per-system backgrounds.

### Wallpaper troubleshooting

- **The image is not listed:** check that it is in `frogui/wallpapers/`, uses a supported format, and restart TreeFrogUI.
- **The image is selected but not visible:** turn **Background Images** on.
- **Text is hard to read:** use a darker image, change the theme, or disable background images.

---

## Per-system backgrounds

Per-system backgrounds change with the current screen or ROM folder. They are used when **Background Images** is on and **Wallpaper** is set to **None**.

Place the files directly in `/mnt/sdcard/frogui/`:

| Screen or folder | Filename |
|---|---|
| Main system list and fallback | `main.png` |
| Recent games | `recents.png` |
| Favourites | `favourites.png` |
| Settings | `settings.png` |
| A ROM folder | The folder name plus `.png`, for example `GBA.png` or `FC.png` |

The base filename must exactly match the ROM folder name, including case. Use a lower-case `.png`, `.jpg`, `.jpeg`, or `.bmp` extension.

Per-system images stretch to the full panel. Use **640×480** on R36SX, R36 HD and GB350, or **854×480** on the SF3000 family, to avoid distortion. If a screen has no matching image, TreeFrogUI falls back to `main.*`.

Dark, low-contrast images work best because menu text is drawn over them.

---

## Built-in colour themes

TreeFrogUI's built-in themes include:

| Theme | Style |
|---|---|
| `MinUI Style` | Minimal dark |
| `Emerald` | Dark green |
| `Orange` | High-contrast orange |
| `Golden` | Gold and yellow |
| `Rose` | Grey and rose |
| `Purple` | Deep purple |
| `Prosty's Pink` | Bright pink and white |
| `Green` | Natural green |
| `Red` | Retro red |
| `Commodore 64` | Blue and lavender |
| `Game Boy` | Four-shade green |
| `NES` | Off-white and grey |
| `Amber CRT` | Amber on black |
| `Green CRT` | Green on black |
| `DOS` | Blue with yellow headers |
| `Famicom` | Maroon and gold |
| `SNES` | Light grey and purple |
| `Matrix` | Green and black |
| `Sajnaps Green` | Dark arcade green |
| `Q_ta's Light Wii` | Light grey and blue |
| `Q_ta's Dark Wii` | Dark grey and blue |
| `Desoxyn's Purple` | Neon purple on black |
| `Ocean` | Deep blue and cyan |
| `Sunset` | Purple and orange |
| `Mono Dark` | Dark grey and white |
| `Nord` | Cool arctic blue |
| `Dracula` | Dark purple and pink |
| `Gruvbox` | Warm sand and yellow |
| `Tokyo Night` | Blue, purple and cyan |
| `Solarized Dark` | Dark teal and yellow |

The Allium palette ports are `alium_default`, `alium_alliumboy`, `alium_blue`,
`alium_boxart`, `alium_brown`, `alium_bubblegum`, `alium_eva_01`, `alium_min`,
`alium_pastel`, `alium_snes`, `alium_spruceos`, and `alium_synthwave`.
Select **alium_Nunito** under Font for Allium's default **Nunito Bold** face.
Turn Background Images off to see the plain colors. These ports adapt the
source RGB palette to RGB565; wallpapers, transparency, and layouts are not
included. Credits and licenses ship in `frogui/fonts/alium_README.md` and
`frogui/fonts/alium_Nunito-OFL.txt`.

---

## Custom fonts

Copy a `.ttf` or `.otf` file to `/mnt/sdcard/frogui/fonts/`, restart TreeFrogUI, then select it under Settings → Appearance → **Font**.

TreeFrogUI also scans `/mnt/sdcard/cubegm/fonts/`. If neither font folder contains a usable file, the embedded GamePocket and Monogram fonts remain available as a fallback. The release ships with BPreplayBold as the default.
