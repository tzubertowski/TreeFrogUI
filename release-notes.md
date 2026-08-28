## TreeFrogUI v1.2.0_b

### What's new

- **Music playlists:** auto-advance, previous/next track, and persistent Sequential, Loop and Random modes.
- **Music metadata:** ID3 title, artist and album details, embedded album covers, and filename fallback.
- **Stable album artwork:** fixed flashing, disappearing, partially rendered, and delayed covers.
- **Image viewer:** reliable 1x–4x JPEG/PNG zoom, D-pad panning, and L/R page navigation.
- **Video playback:** folder navigation, auto-play next, and playback modes.
- **Unified media design:** matching themed controls across music, video, and images.
- **Arcade and Game Boy Color:** correct names, core mappings, and theme backgrounds.
- **R36HD:** tested installation support and expanded manual-install documentation.
- **FrogShell display fix:** the file manager now runs through picoarch instead of drawing directly to `/dev/fb0`. This uses the same proven rotation path on SF3000 and R36HD, with consistent 480p UI sizing.

### Install or update

**Recommended:** use the [TreeFrogUI Installer](https://github.com/tzubertowski/TreeFrogUI-installer/releases/latest) for both fresh installations and updates.

Manual fallback:

- Fresh install: download `TreeFrogUI_v1.2.0_b.zip` and apply `install_first/<device>/`.
- Update: copy `update.zip` to the SD-card root and reboot.

This is a prerelease for wider device testing before promotion to stable.
