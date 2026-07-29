> [!IMPORTANT]
> v1.0.10_b gives the UI a **fresh look** (bigger bold font, custom wallpaper, a proper battery icon), makes **big ROM folders load fast**, reworks the **Settings menu**, adds an **aspect-ratio picker** and a PS1 **Hi-Res Fix**, keeps **volume control working in games**, and fixes **PS1 hi-res freezing/blacking out**, **positional PS1 buttons**, **automatic PS1 BIOS**, and the **lingering battery icon**.
> 
> 📋 **[Submit Anonymous Feedback (Google Forms)](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v1.0.10_b

Now it's pretty, too.

- **🎨 New look.** Bigger, bolder text (the same clean font MinUI/NextUI use) with more breathing room, so the menus are easier to read on the little screen. The PCSX4ALL (PS1) menus now match too - same font, theme colours, and rounded selection, rendered crisply at full resolution. Same layout, less squinting.
- **🎨 Battery Colour Mode.** New Settings → Appearance toggle: instead of a fill bar, the battery shows a single colour dot - green (70-100%), blue (30-70%), red (0-30%). Minimal, at a glance.
- **🔋 A real battery icon.** The frontend and the in-game menu now show a proper battery indicator (with a charging bolt) in place of the stock one - reads the actual charge level, turns red when it's nearly time to plug in. It draining is still your problem.
- **🖼️ Custom wallpaper.** Settings → Appearance → **Wallpaper**: drop images in `frogui/wallpapers/` and pick one to use across every screen, instead of the per-system art. **Wallpaper Fit** offers Windows-style Fill / Fit / Stretch / Center / Tile. Make it yours; play nothing, beautifully.
- **⚡ Big ROM folders load fast.** Folders with thousands of games used to crawl when opening and scrolling. The listing is sorted properly now (not the old slow way) and cached between visits, so a folder you've seen before opens instantly. Add or remove a game and it refreshes on its own. There's a Folder Cache toggle in Settings if you ever want it off. More time to not decide what to play.
- **🗂️ Settings menu, reorganized.** Options are grouped under headers (Appearance, Library, Gameplay, System) and indented so you can actually find things. New toggles: **Hide Extensions** (drop the `.gb`/`.gba` clutter from names) and **Background Images** (turn off the per-system art for a plain background). Same settings, less squinting.
- **📐 Aspect ratio picker.** New single control in the in-game Video menu: Integer, Native (what the core wants), 4:3, 16:9, 3:2, 5:4, 8:7, 16:10, or Fill. Replaces the old Screen size toggle - one list, per game. Integer and Native stay exact and free; a forced ratio reshapes in a single pass only when you pick one. Now you can get the picture wrong in more precise ways. (PS1's non-square modes like 256-wide games are aspect-corrected too, no longer squished.)
- **🔊 Volume control survives games.** The frontend used to kill and restart the volume daemon to redraw its little on-screen icon, which quietly took your volume buttons with it. It's left alone now - the icon comes back on its own, and the buttons keep working. Turn it down; it won't help.
- **🩹 PS1 hi-res games stop freezing and blacking out.** Colin McRae Rally, Worms Armageddon and friends flip into a tall 480-line video mode that the display driver quietly chokes on - black screen or a frozen picture while the game plays on underneath. Those frames are scaled back down to something the driver can actually show now, on every device. The cars still understeer into the scenery, but you get to watch.
- **🎮 PS1 buttons now match their positions.** Cross (confirm) is the south button, Circle east, Square west, Triangle north - so what the game tells you to press lines up with where it is on the pad. Only applies to fresh setups; if you'd already remapped, your choice is kept. Press south to confirm the things you'll regret.
- **💿 PS1 BIOS just works now.** Drop any real BIOS (`scph*.bin`) into `cubegm/bios/` and PCSX4ALL finds it and switches HLE off on its own - no menu ritual, no exact filename. If you'd already set one by hand, it's left alone. One less thing to get wrong before the disappointment starts.
- **🔋 The battery icon stops haunting your games.** It used to linger over the screen after a game launched, reminding you the clock is running down on the battery and on everything else. It gets wiped now, over and over, so you don't have to think about it.

*Everything else already shipped in v1.0.8. The Nearest filter still messes up the menu sometimes. It is what it is.*

**Updating:** copy `cubegm/` and `frogui/` over your card, then copy your device's `install_first/<device>/` folder again. ROMs, saves, and settings are untouched.

---

*Overview, features, install guide, troubleshooting, and porting info live in the [README](README.md).*
