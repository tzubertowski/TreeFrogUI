> [!IMPORTANT]
> v1.0.11_b fixes MAME 2000 ROM-load crashes.
> 
> **[Submit anonymous feedback](https://docs.google.com/forms/d/e/1FAIpQLSfM-y2_UnERrjScqkSfkRSEfBPJ79rDwDo3GwuYWXxpkFTp4Q/viewform?usp=header)**

---

## What's New in v1.0.11_b

- **Clean ROM rejection.** Wrong or incomplete MAME 2000 sets return to the menu instead of crashing after the core reports a successful load with no video output.
- **SF hardware build.** MAME 2000 is rebuilt for the device's MIPS 74Kc CPU with DSP2 enabled. It still requires the MAME 0.37b5 romset.

**Updating:** copy `cubegm/` and `frogui/` over your card, then copy your device's `install_first/<device>/` folder again. ROMs, saves, and settings are untouched.

---

*Overview, features, install guide, troubleshooting, and porting info live in the [README](README.md).*
