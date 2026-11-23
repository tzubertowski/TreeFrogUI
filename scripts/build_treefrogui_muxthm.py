#!/usr/bin/env python3
"""Generate TreeFrogUI MuOS artwork and preview from the shipped 640x480 art."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sdcard/frogui/640x480"
THEME = ROOT / "assets/themes/TreeFrogUI_MuOS"
WALL = THEME / "640x480/image/wall"
ART = {
    "muxlaunch.png": "main.jpg",
    "muxlaunch/default.png": "main.jpg",
    "muxlaunch/explore.png": "main.jpg",
    "muxlaunch/history.png": "recents.jpg",
    "muxlaunch/collection.png": "favourites.jpg",
    "muxlaunch/config.png": "settings.jpg",
    "muxlaunch/apps.png": "settings.jpg",
    "muxplore.png": "main.jpg",
    "muxhistory.png": "recents.jpg",
    "muxcollect.png": "favourites.jpg",
    "muxconfig.png": "settings.jpg",
    "muxapp.png": "settings.jpg",
}
SYSTEM_ART = {
    "fc": "nes.jpg", "sfc": "snes.jpg", "gb": "gb.jpg", "gbc": "gb.jpg",
    "gba": "gba.jpg", "md": "md.jpg", "ps": "psx.jpg", "ps1": "psx.jpg",
    "psp": "psp.jpg", "arcade": "m2k.jpg",
}


def save_png(source: Path, output: Path) -> None:
    with Image.open(source) as image:
        image = image.convert("RGB")
        assert image.size == (640, 480), f"{source}: expected 640x480, got {image.size}"
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output, "PNG", optimize=True)
    with Image.open(output) as image:
        assert image.size == (640, 480) and image.mode == "RGB", output


def make_preview() -> None:
    font_path = THEME / "640x480/font/default.ttf"
    with Image.open(SOURCE / "main.jpg") as image:
        preview = image.convert("RGB").resize((288, 216), Image.Resampling.LANCZOS)
    preview = Image.blend(preview, Image.new("RGB", preview.size, "black"), 0.55)
    draw = ImageDraw.Draw(preview)
    draw.rectangle((0, 0, 287, 35), fill="#080808")
    draw.text((12, 10), "TREEFROGUI MUOS", font=ImageFont.truetype(font_path, 16), fill="white")
    labels = ("Explore Content", "Favourites", "History", "Apps", "Settings")
    for row, label in enumerate(labels):
        y = 51 + row * 29
        if row == 0:
            draw.rectangle((8, y, 280, y + 25), fill="white")
            color = "black"
        else:
            color = "white"
        draw.text((18, y + 4), label, font=ImageFont.truetype(font_path, 13), fill=color)
    preview_path = THEME / "640x480/preview.png"
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview.save(preview_path, "PNG", optimize=True)
    with Image.open(preview_path) as check:
        assert check.size == (288, 216) and check.mode == "RGB", preview_path


def main() -> None:
    for destination, filename in ART.items():
        save_png(SOURCE / filename, WALL / destination)
    for element, filename in SYSTEM_ART.items():
        save_png(SOURCE / filename, WALL / "muxplore" / f"{element}.png")
    make_preview()
    print(f"Generated TreeFrogUI MuOS artwork under {THEME}")


if __name__ == "__main__":
    main()
