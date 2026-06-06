# Theming TreeFrogUI

TreeFrogUI supports a variety of visual customization options, including built-in color themes, selectable fonts, and custom folder-specific background images.

---

## Changing Settings (In-App)

At the bottom of the root system list, select **`>> Settings`** and press **A**. From here, you can:
- **Theme**: Press **Left/Right** to cycle through the 30 available built-in themes.
- **Font**: Press **Left/Right** to toggle between the supported system fonts.
- Press **A** or **B** to apply the configuration and save changes.

These options are stored in `/mnt/sdcard/frogui/settings.txt` as simple key-value pairs:
```ini
theme=Dracula
font=GamePocket
```

---

## Custom Background Images

TreeFrogUI supports loading background images from the SD card. You can configure individual backgrounds for the main systems menu, recent games, favorites list, or specific emulator/console folders.

### Image Placement & Naming

Place your image files in `/mnt/sdcard/frogui/` using the following naming conventions:

| Screen / Folder | Required Filename | Description |
|---|---|---|
| **Root Systems Menu** | `main.png` | Renders on the main systems list screen |
| **Recent Games** | `recents.png` | Renders when browsing recently played games |
| **Favorites** | `favourites.png` | Renders when browsing favorited games |
| **Console Folders** | `<Folder_Name>.png` | Renders when browsing a specific console's ROM list (e.g. `GBA.png`, `FC.png`, `SFC.png`, `MD.png`, `spec.png`) |

> [!IMPORTANT]
> The filename must **exactly match** the console's folder name in `/mnt/sdcard/roms/` (case-sensitive). For example, if your NES games folder is `FC`, the background image must be named `FC.png`.

### Technical Specifications

- **Supported Formats**: `PNG` (recommended), `JPEG` / `JPG`, and `BMP` (processed via `stb_image`).
- **Resolution**: Scaled to **854×480** pixels (the native display resolution of the SF3000 screen) upon loading. For the best visual clarity and to prevent scaling artifacts, pre-resize your background images to exactly **854×480**.
- **Aesthetic Recommendation**: Since text and interface selection pillboxes are rendered directly over the background image, it is highly recommended to use **dark, low-contrast, or semi-transparent/muted** images to ensure menu text remains clean and readable.

---

## Game Thumbnails

TreeFrogUI shows a per-game preview image in the right-hand panel while you browse a ROM list. Thumbnails are opt-in — add an image for any game you like; games without one simply show no preview.

### Image Placement & Naming

For each game, place its thumbnail in a hidden `.res/` folder **next to the ROM**, named after the ROM file with a `.rgb565` extension (no original file extension):

```
roms/GBA/Advance Wars.gba          ← the game
roms/GBA/.res/Advance Wars.rgb565  ← its thumbnail
```

So the rule is: `<rom folder>/.res/<rom filename without extension>.rgb565`.

### Format & Sizes

Thumbnails are stored as **headerless raw RGB565** (little-endian) — not PNG/JPG. The image dimensions are detected from the file size, which must be exactly `width × height × 2` bytes. Supported sizes:

| Size | Notes |
|---|---|
| `160×160` | **Recommended** |
| `64×64`, `128×128`, `200×200` | Square alternatives |
| `250×200`, `200×250` | Landscape / portrait |

### Converting an image to `.rgb565`

Use `ffmpeg` (simplest) to resize and convert artwork to the raw format:

```sh
ffmpeg -i cover.png -vf scale=160:160 -f rawvideo -pix_fmt rgb565le "Advance Wars.rgb565"
```

Then drop the result into the game's `.res/` folder. (In-game **savestate** thumbnails in the pause menu are captured automatically and need no setup — this section is only for ROM-browser previews.)

---

## Built-in Color Themes

TreeFrogUI includes 30 curated color themes to match any preference or device aesthetic. The full list of supported theme names is below:

| Theme Name | Style / Aesthetic Description |
|---|---|
| `MinUI Style` | Minimalist dark theme with clean white text |
| `Emerald` | Elegant green tones |
| `Orange` | Vibrant high-contrast orange |
| `Golden` | Sleek gold and yellow layout |
| `Rose` | Warm grey and rose-pink accents |
| `Purple` | Classic deep royal purple |
| `Prosty's Pink` | Bright pink and white theme |
| `Green` | Natural green |
| `Red` | Bold retro red |
| `Commodore 64` | C64 system blue and lavender theme |
| `Game Boy` | Nostalgic original 4-shade greenish palette |
| `NES` | Off-white and grey color scheme representing the NES |
| `Amber CRT` | Retro terminal look with amber-on-black |
| `Green CRT` | Classic arcade terminal green-on-black |
| `DOS` | Command line blue background with yellow headers |
| `Famicom` | Traditional maroon red and gold accents |
| `SNES` | Light grey console color scheme with purple accents |
| `Matrix` | Digital rain style green and black |
| `Sajnaps Green` | Dark arcade green highlight theme |
| `Q_ta's Light Wii` | Clean light-grey and sky blue theme |
| `Q_ta's Dark Wii` | Modern dark-grey and blue theme |
| `Desoxyn's Purple` | Vibrant neon purple-on-black |
| `Ocean` | Dark deep sea blue with cyan highlights |
| `Sunset` | Purple dusk color scheme with warm orange accents |
| `Mono Dark` | Monochromatic dark gray and white |
| `Nord` | Calm, cool arctic blue palette |
| `Dracula` | Popular dark developer theme with purple and pink accents |
| `Gruvbox` | Retro warm sand and yellow palette |
| `Tokyo Night` | Neon blue, purple, and cyan night theme |
| `Solarized Dark` | Classic low-contrast teal and yellow theme |

---

## Available Fonts

The following fonts are embedded directly in the frontend binaries and can be configured:

1. **`GamePocket`**: Bold, blocky pixel font optimized for readability on handheld displays.
2. **`Monogram`**: A classic, compact pixel script font suitable for listing longer ROM names.
