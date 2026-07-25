> [!IMPORTANT]
> v1.0.9 hardens the **PlayStation resolution-change freeze** fix so it holds on slower units. That's the whole release.
> 
> 📋 **[Submit Anonymous Feedback (Google Forms)](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v1.0.9

Five fixes. That's the version.

- **🎮 PS1 buttons now match their positions.** Cross (the confirm button) is the south button (B), Circle is A, Square is Y, Triangle is X - so what the game tells you to press lines up with where it is on the pad. Only applies to fresh setups; if you'd already remapped, your choice is kept. Press B to confirm the things you'll regret.
- **🪱 Worms Armageddon (and other PS1 hi-res) no longer boots to a black screen on R36SX.** Its hi-res mode was too large for the R36SX display path to swallow, so it gets scaled to fit now. You can see the worms. They still explode.
- **🩹 The PlayStation freeze is fixed. Again.** Colin McRae froze for everyone but me, so I added a third buffer to a problem two already claimed to solve. On some slower unit it still wedges, and I'll never see it. No performance cost, because there was no joy to begin with.
- **💿 PS1 BIOS just works now.** Drop any real BIOS (`scph*.bin`) into `cubegm/bios/` and PCSX4ALL finds it and switches HLE off on its own - no menu ritual, no exact filename. If you'd already set one by hand, it's left alone. One less thing to get wrong before the disappointment starts.
- **🔋 The battery icon stops haunting your games.** It used to linger over the screen after a game launched, reminding you the clock is running down on the battery and on everything else. It gets wiped now, over and over, so you don't have to think about it.

*Everything else already shipped in v1.0.8. The Nearest filter still messes up the menu sometimes. It is what it is.*

**Updating:** copy `cubegm/` and `frogui/` over your card, then copy your device's `install_first/<device>/` folder again. ROMs, saves, and settings are untouched.

---

*Overview, features, install guide, troubleshooting, and porting info live in the [README](README.md).*
