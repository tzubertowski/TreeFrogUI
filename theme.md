# Customising TreeFrogUI

TreeFrogUI supports colour themes, custom fonts, one global wallpaper, per-system backgrounds and game thumbnails.

---

## Appearance settings

Open **`>> Settings`** at the bottom of the main system list. Use Up/Down to select an option and Left/Right to change it. Press A or B to close Settings and save.

| Setting | What it changes |
|---|---|
| **Theme** | Interface colours, including the in-game menu |
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

### Which background is used

| Background Images | Wallpaper | Result |
|---|---|---|
| Off | Any value | Plain background using the selected theme |
| On | None | Per-system and per-screen backgrounds |
| On | An image | That wallpaper on every screen |

A selected wallpaper overrides per-system art. Turning **Background Images** off only hides the images; it does not forget your wallpaper choice.

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

## Game thumbnails

TreeFrogUI shows a preview image for the selected game. In the Recents game switcher, box art is preferred; if none exists, TreeFrogUI uses the latest gameplay screenshot.

Place each image in a hidden `.res/` folder next to the ROM. Match the ROM filename without its extension:

```text
roms/GBA/Advance Wars.gba
roms/GBA/.res/Advance Wars.png
```

The rule is `<ROM folder>/.res/<ROM name without extension>.<png|jpg|jpeg|bmp>`.

PNG, JPG, JPEG and BMP images can be any resolution. Images larger than the 250×200 preview area are downscaled automatically with their aspect ratio preserved. PNG transparency is supported. Keep files reasonably small because they are decoded while browsing.

Older headerless `.rgb565` thumbnail sets also work at these fixed sizes: `64×64`, `128×128`, `160×160`, `200×200`, `250×200`, and `200×250`.

In-game savestate and last-screen images are captured automatically and need no manual setup.

---

## Built-in colour themes

TreeFrogUI includes 30 colour themes:

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
