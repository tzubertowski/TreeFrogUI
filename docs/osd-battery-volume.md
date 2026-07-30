# On-screen OSD: battery + volume (RE notes)

How the stock battery/volume indicators work on the ALi devices, what we
reverse-engineered, what we shipped, and why the custom **volume** popup was
abandoned.

## The overlay: /dev/fb1

The battery + volume indicators are **not files or assets**. They're drawn by
**`cubevol`** (the stock GPIO/volume daemon, `rootfs/usr/bin/cubevol`, started by
zhijack at boot) directly onto **`/dev/fb1`** — a hardware ARGB **overlay layer**
that the display controller composites on top of the main framebuffer (`/dev/fb0`)
continuously, independent of what we render.

- Battery glyph: top-right of fb1.
- Volume popup: center of fb1, shown on a volume-button press for ~2s.
- cubevol has **no signal handler** and repaints only on change (charge %, volume
  press), so zeroing its fb1 region once keeps it hidden until the next repaint.

## Battery (shipped, works)

Reverse-engineered from cubevol:

- Symbols: `battery_adc_init`, `bat_level_fd`, `charging_fd`, `BatteryLevel1..4`
  + `_map` tables.
- **Battery level** = **1 raw byte read from `/dev/check_adc1`** (0..255).
  cubevol scales it (`raw * 0x10FE0762 >> 32` ≈ `raw/15`) and maps through
  hysteresis thresholds. Real packs top out around raw `224`, so our display
  curve uses `{64,153,224}` piecewise to `{0,50,100}`. Treating the byte maximum
  (`255`) as full left a charged device permanently below 100%.
- **Charging** = **1 raw byte from `/dev/check_adc5`** (NOT `check_adc2`, which
  doesn't exist on R36SX). Value is **~0 idle, ~140 charging** — threshold `>=64`.
- Both ADC nodes are **flaky when re-opened per poll**; open once **O_RDWR** and
  keep the fd (cubevol does the same).

**Shipped:** FrogUI draws its own NextUI-style battery icon in the header
(`render_battery`), and picoarch draws one in the pause menu. cubevol's own
battery glyph is hidden by zeroing just the **top-right corner** of fb1 each
frame — leaving cubevol's centered volume popup intact.

## Volume (RE'd, but custom popup ABANDONED)

Reverse-engineered:

- Symbols: `api_get_snd_volume`, `avparam_get_volume`, `avparam_save_volume`,
  `mp5_show_volume`, `cubevol_gpio_init`.
- **Live value** = `ioctl(/dev/sndC0i2so, 0x80D, &vol)` (proprietary snd device).
- **Stored value** = a **260-byte persistentmem blob**: `avparam_get_volume` does
  `ioctl(/dev/persistentmem, 0x400C2602, &req)` with `req = {flag=3, id=0,
  len=260, buf}` and the **volume is `buf[0]`**, a plain **0..100 percent**.
  (Same persistentmem GET ioctl as the backlight, different flag/id/len.)
- Volume **buttons** are owned by cubevol via GPIO (device-tree
  `key-volume-up/down`); we don't see the press, only the resulting value.

We built a custom vertical volume popup that read `buf[0]` from persistentmem,
polled for changes, and drew our own bar on fb0.

### Why it was abandoned: the fb1 blink

To show our own popup we had to hide cubevol's. But cubevol writes its popup to
the **fb1 overlay**, which the **hardware composites continuously** — asynchronous
to our render loop. On a volume press cubevol draws its popup; our per-frame
`memset(fb1, 0)` removes it, but the compositor shows it for the **sub-frame gap**
between cubevol's write and our next clear → a **one-frame blink** on every press.

Tried, none sufficient:

- Per-frame clear of the whole fb1 (persistent mmap, cleared at end of
  `retro_run`). Blink persists — it's a compositing race, not a clear-cadence
  problem.
- `FBIOBLANK(FB_BLANK_POWERDOWN)` on `/dev/fb1` to disable the layer. **No
  effect** — the OSD layer stays composited.

**The only real fix** is disabling the fb1 OSD layer at the display-controller
level (a `/dev/dis` or GMA layer-enable ioctl we have **not** cracked), so
cubevol's writes never composite. Until then, fighting cubevol on the shared
overlay always blinks.

**Decision:** keep cubevol's own volume popup (no blink, works). Ship only the
custom **battery** indicator. Revisit the custom volume popup if/when the OSD
layer-disable ioctl is found.

## Persistentmem quick reference

`struct pmem_req { u16 flag, id, len, pad; void *buf; }`, `/dev/persistentmem`:

| Field    | GET ioctl    | req                         | data          |
|----------|--------------|-----------------------------|---------------|
| Backlight| `0x400C2602` | `{1, 30, 1, 0, &byte}`      | raw 23..255   |
| Volume   | `0x400C2602` | `{3, 0, 260, 0, buf[260]}`  | `buf[0]` 0..100 |
