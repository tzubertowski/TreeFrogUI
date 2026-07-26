> [!IMPORTANT]
> v1.0.9 fixes **PS1 hi-res games freezing/blacking out** (Colin McRae, Worms Armageddon), **positional PS1 buttons**, **automatic PS1 BIOS**, and the **lingering battery icon**.
> 
> 📋 **[Submit Anonymous Feedback (Google Forms)](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v1.0.9

Five things. That's the version.

- **📐 Aspect ratio picker.** New single control in the in-game Video menu: Integer, Native (what the core wants), 4:3, 16:9, 3:2, 5:4, 8:7, 16:10, or Fill. Replaces the old Screen size toggle - one list, per game. Integer stays exact and fast; picking a ratio reshapes only when it has to. Now you can get the picture wrong in more precise ways. (PS1's non-square modes like 256-wide games are aspect-corrected too, no longer squished.)
- **🩹 PS1 hi-res games stop freezing and blacking out.** Colin McRae Rally, Worms Armageddon and friends flip into a tall 480-line video mode that the display driver quietly chokes on - black screen or a frozen picture while the game plays on underneath. Those frames are scaled back down to something the driver can actually show now, on every device. The cars still understeer into the scenery, but you get to watch.
- **🎮 PS1 buttons now match their positions.** Cross (confirm) is the south button, Circle east, Square west, Triangle north - so what the game tells you to press lines up with where it is on the pad. Only applies to fresh setups; if you'd already remapped, your choice is kept. Press south to confirm the things you'll regret.
- **💿 PS1 BIOS just works now.** Drop any real BIOS (`scph*.bin`) into `cubegm/bios/` and PCSX4ALL finds it and switches HLE off on its own - no menu ritual, no exact filename. If you'd already set one by hand, it's left alone. One less thing to get wrong before the disappointment starts.
- **🔋 The battery icon stops haunting your games.** It used to linger over the screen after a game launched, reminding you the clock is running down on the battery and on everything else. It gets wiped now, over and over, so you don't have to think about it.

*Everything else already shipped in v1.0.8. The Nearest filter still messes up the menu sometimes. It is what it is.*

**Updating:** copy `cubegm/` and `frogui/` over your card, then copy your device's `install_first/<device>/` folder again. ROMs, saves, and settings are untouched.

---

*Overview, features, install guide, troubleshooting, and porting info live in the [README](README.md).*
