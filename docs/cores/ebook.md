# Ebook reader

← [back to README](../../README.md)

The **`Ebook`** folder runs a standalone document reader (like pcsx4all / lgpt /
rockbox - a real binary, not a libretro core). It's powered by
[MuPDF](https://mupdf.com/) and reads most common ebook and document formats.

Source: [tzubertowski/TreeFrogUI_ebook_reader](https://github.com/tzubertowski/TreeFrogUI_ebook_reader).

## Adding books

Put files in **`roms/Ebook/`** (an `Ebook` entry then appears in the menu). Open
one and it renders full-screen; the driver scales the page to fill whatever panel
your device has, so it works the same on R36SX / SF3000 / SF3500 / GB350.

## Supported formats

| Format | Notes |
|--------|-------|
| **EPUB** | reflowable - honours the book's own layout by default; font/size adjustable |
| **MOBI** | reflowable (Kindle format) |
| **PDF**  | fixed layout, rendered page-by-page |
| **FB2**  | reflowable |
| **CBZ**  | comic archives (zipped images) |
| **XPS**  | fixed layout |

## Controls

**Reading:**

| Button | Action |
|--------|--------|
| **R1 / RIGHT / A** | next page |
| **L1 / LEFT / B** | previous page |
| **R2** / **L2** | jump forward / back 10% |
| **SELECT** | open / close the menu |
| **SELECT + START** | quit (progress is saved) |

**Menu** (open with **SELECT**): **UP / DOWN** move between rows.
- On **`Text size`** and **`Font`** rows, **LEFT / RIGHT** change the value. The
  change is applied when you **close the menu** (reflowing a whole book takes a
  moment, so it's done once rather than on every press - you'll see a brief
  "Reflowing..." while it re-lays out).
- **A** runs the action rows: **Resume**, **Jump forward / back (10%)**,
  **Go to start / end**, **Quit**.

## Features

- **Adjustable text size** - set an actual size in px (12-48), not vague
  bigger/smaller. Applies to reflowable formats (EPUB/MOBI/FB2).
- **Font selection** - built-in **Serif** (default), **Sans**, and **Mono**,
  **plus any custom fonts you supply** (see below).
- **Saved progress** - your page, text size, and font choice are remembered
  **per book** (stored under the hidden `.positions/` subdirectory), so reopening
  resumes exactly where you left off.
- **Full-screen, correct aspect** on every supported device (one render path,
  no per-device settings).

## Custom fonts

Drop `.ttf` / `.otf` files in any of these and they appear in the **Font** menu:

- **`roms/Ebook/fonts/`** (recommended - keeps your reading fonts with your books)
- `frogui/fonts/`
- `cubegm/fonts/`

Pick one via **Menu → Font → LEFT/RIGHT**. Custom fonts apply to reflowable
formats (they can't override a PDF's embedded fonts).

## Notes

- **PDF text size** is fixed by the document (PDFs don't reflow); the page is
  scaled to the screen. Use EPUB/MOBI for adjustable text.
- **Big books** take a second to re-lay-out when you change size or font - that's
  the "Reflowing..." step, and it only happens once when you leave the menu.
