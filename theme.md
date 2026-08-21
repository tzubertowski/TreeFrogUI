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

Mini Scraper matches covers to the ROM filenames and writes them directly to TreeFrogUI's required `.res/<ROM name>.png` locations. Existing artwork is preserved unless you explicitly choose to replace it.

### Add box art manually

Place each cover image in a hidden `.res/` folder next to the ROM. Match the ROM filename without its extension:

```text
roms/GBA/Advance Wars.gba
roms/GBA/.res/Advance Wars.png
```

The rule is `<ROM folder>/.res/<ROM name without extension>.<png|jpg|jpeg|bmp>`.

PNG, JPG, JPEG and BMP images can be any resolution. Images larger than the 250×200 preview area are downscaled automatically with their aspect ratio preserved. PNG transparency is supported. Keep files reasonably small because they are decoded while browsing.

Older headerless `.rgb565` thumbnail sets also work at these fixed sizes: `64×64`, `128×128`, `160×160`, `200×200`, `250×200`, and `200×250`.

In-game savestate and last-screen images are captured automatically and need no manual setup.

---

## Appearance settings

Open **`>> Settings`** at the bottom of the main system list. Use Up/Down to select an option and Left/Right to change it. Press A or B to close Settings and save.

| Setting | What it changes |
|---|---|
| **Theme** | Interface colours |
| **Style** | Chooses Vertical, Horizontal or System View |
| **Icon Pack** | Chooses System View artwork independently from backgrounds |
| **Friendly System Names** | Expands folder codes such as `ps` and `gba` |
| **Font** | Menu typeface |
| **Brightness** | Screen brightness |
| **Animations** | Background crossfades and other UI motion |
| **Battery Colour Mode** | Uses a green, blue or red battery status light |
| **Background Images** | Enables wallpapers and per-system backgrounds |
| **Background Theme Pack** | Selects a folder of themed background artwork |
| **Wallpaper** | Selects one image for every TreeFrogUI screen |
| **Wallpaper Fit** | Controls how the selected wallpaper fills the display |
| **Hide Extensions** | Hides file extensions in game lists |
| **Hide Empty Folders** | Hides system folders with no games |

Settings are stored in `/mnt/sdcard/frogui/settings.txt`.

### Background theme packs

Theme packs live in `/mnt/sdcard/frogui/theme-packs/<pack>/`. Select one in
Settings → Appearance → **Background Theme Pack**. Packs use the same filenames
as per-system backgrounds: `main.jpg`, `settings.jpg`, `recents.jpg`,
`favourites.jpg`, or a ROM folder name such as `gba.jpg`. The shipped
`Art_Book_Next` pack preserves the original artwork. The test packs include
per-system artwork adapted from **Elementerial**, **Iconic** and
**PlayStation-X**.

The supplied packs include explicit artwork aliases for the short TreeFrogUI
folder names used on the device (for example `a26`, `m2k`, `pcesgx` and
`ps1r`), so these systems do not fall back to the generic main image.

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
| A ROM folder | `<folder name>.png`, for example `GBA.png` or `FC.png` |

The base filename must exactly match the ROM folder name, including case. Use a lower-case `.png`, `.jpg`, `.jpeg`, or `.bmp` extension.

Per-system images stretch to the full panel. Use **640×480** on R36SX, R36 HD and GB350, or **854×480** on the SF3000 family, to avoid distortion. If a screen has no matching image, TreeFrogUI falls back to `main.*`.

Dark, low-contrast images work best because menu text is drawn over them.

---

## Built-in colour themes

TreeFrogUI includes 30 built-in themes:

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

---

## Custom fonts

Copy a `.ttf` or `.otf` file to `/mnt/sdcard/frogui/fonts/`, restart TreeFrogUI, then select it under Settings → Appearance → **Font**.

TreeFrogUI also scans `/mnt/sdcard/cubegm/fonts/`. If neither font folder contains a usable file, the embedded GamePocket and Monogram fonts remain available as a fallback. The release ships with BPreplayBold as the default.
