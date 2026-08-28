# TreeFrogUI image viewer

Standalone viewer for images launched from `roms/images/`. JPEG and PNG use a
framebuffer renderer for reliable zoom and pan; other supported formats retain
HCRTOS's native `libffplayer` picture decoder. Colors and button mappings come
from TreeFrogUI's generated skin and keymap files.

Controls: L1/R1 changes image (Left/Right also works at 1x), A switches
Fit/Fill, X/Y zooms from 1x to 4x, the D-pad pans while zoomed, Start toggles
the HUD, and B/Select exits.
