# Investigate later

Running list of reported quirks worth a proper look, with the current
understanding. Not blocking; parked here so they aren't lost.

## gpsp_multicore: saves fail on ZIP ROMs with multi-byte (e.g. Japanese) filenames

**Reported cause / workaround (from a user, self-diagnosed):**

- In `gpsp_multicore` there's a **"Battery Save Method"** core option. The default
  **"GPSP"** method does **not** handle multi-language ROM filenames (Japanese,
  etc.), so battery save/load silently fails for those ROMs.
- Switching **Battery Save Method -> "LIBRETRO"** fixes it: saves and loads work
  with the multi-byte filenames.
- The plain `gpsp` core never showed the problem, likely because it defaults to
  the LIBRETRO save method.
- SF2000's `gbac` core also never hit it -- probably because SF2000 didn't support
  **ZIP-compressed GBA ROMs** at all. SF3000 **does** support ZIP ROMs, which is
  why the issue surfaced here.

**Follow-up to consider:**

- Ship gpsp_multicore with **Battery Save Method defaulted to LIBRETRO** (or
  override it in our per-core options) so users don't lose saves on Japanese ZIP
  ROMs out of the box.
- Confirm no downside to LIBRETRO method for existing saves (migration / .srm
  path differences between the two methods).
- Related earlier self-resolved case: PCE core resume issue (same reporter).
