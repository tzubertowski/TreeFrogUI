#!/usr/bin/env python3
"""Create opaque, panel-sized copies of the built-in TreeFrogUI backgrounds.

Requires Pillow when regenerating assets; normal builds use the checked-in JPEGs.
"""
from pathlib import Path
from PIL import Image


ROOT = Path(__file__).resolve().parents[1] / "sdcard/frogui"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}
SIZES = ((640, 480), (854, 480))


def background_files(folder: Path):
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def make_variant(source: Path, target: Path, size: tuple[int, int]) -> None:
    with Image.open(source) as image:
        rgba = image.convert("RGBA")
        opaque = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        opaque.alpha_composite(rgba)
        variant = opaque.convert("RGB").resize(size, Image.Resampling.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        output = target.with_suffix(".jpg")
        variant.save(output, "JPEG", quality=88, optimize=True)
    with Image.open(output) as check:
        assert check.size == size and check.mode == "RGB", output


def main() -> None:
    folders = [ROOT]
    packs = ROOT / "theme-packs"
    folders.extend(path for path in sorted(packs.iterdir()) if path.is_dir())
    generated = 0
    for folder in folders:
        for source in background_files(folder):
            with Image.open(source) as image:
                exact_854 = image.size == (854, 480) and "A" not in image.getbands()
            for width, height in SIZES:
                if width == 854 and exact_854:
                    continue
                target = folder / f"{width}x{height}" / source.name
                make_variant(source, target, (width, height))
                generated += 1
    print(f"Generated {generated} opaque panel-sized backgrounds under {ROOT}")


if __name__ == "__main__":
    main()
