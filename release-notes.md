## TreeFrogUI v1.5.0 prerelease

- FrogShell gains an optional Developer Mode with a terminal, command history,
  script and executable launching, and USB keyboard input where supported.
  Hold L1 + R1 + X + Y for about two seconds to toggle it, or create
  `frogui/developer.flag` on the SD card.
- FrogShell's on-screen keyboard adds caps, symbols, and modifier keys.
- The ebook reader combines upstream progress-saving improvements with the
  local fixes for page-turn freezes, hidden progress files, and page fit above
  the status bar. Saves use checked atomic replacement and are deferred until
  navigation settles; the MuPDF cache remains limited to 16 MB.
- Updated PS1 compatibility reports.
- Release builds now compile FrogShell and the ebook reader from source so the
  packages include their latest changes.

Thanks to [ozkaoz](https://github.com/ozkaoz) for FrogShell Developer Mode and
[Maheshivara](https://github.com/Maheshivara) for ebook reader improvements.

This is a prerelease for testing. Copy `update.zip` to the SD-card root and
reboot, or use the full ZIP and the matching `install_first/<device>/` files
for a fresh installation. Keep a backup of your card.
