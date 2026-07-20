# PC Engine / TurboGrafx-16

← [back to README](../../README.md)

`pce` uses the **Beetle PCE Fast** (`mednafen_pce_fast_libretro.so`) libretro core.

**Crash or reset when returning from the in-game menu, on some devices (seen on
SF3000 HD)?** Turn on **Disable Soft Reset** in the core's options
(`SELECT + START` → Core Options → `pce_fast_disable_softreset`). The stock PC
Engine soft-reset combo (RUN+SELECT) can fire spuriously when control returns
to the core after the menu closes, resetting or crashing it. Disabling soft
reset removes that combo entirely and fixes it. Not all devices are affected;
if you don't see this, no action needed.
