# Runtime i18n

TreeFrogUI and PicoArch use the same runtime JSON packs and selected locale.
No translation is compiled into either frontend.

```text
/mnt/sdcard/frogui/settings.txt              # language=pl_PL
/mnt/sdcard/frogui/lang/builtin/en_US.json   # complete baseline
/mnt/sdcard/frogui/lang/builtin/pl_PL.json   # translated pack
```

The shared implementation is `FrogUI/common/i18n.c`. FrogUI links it directly;
PicoArch builds that same source file through `../FrogUI/common/`. It reads the
global `language=` setting and loads one flat UTF-8 JSON object into a bounded
key/value table. `tr_or("pico.menu.resume", "Resume game")` is the normal
call pattern: a missing key keeps its English fallback.

Packs use stable dotted keys, not English text as IDs:

```json
{
  "settings.language": "Język",
  "pico.menu.resume": "Wznów grę"
}
```

The shipped packs are `en_US`, `pl_PL`, plus English starter packs for `es_ES`,
`pt_BR`, `ja_JP`, `ru_RU`, and `zh_CN`. Contributors can translate a copy of
`en_US.json`; there is no recompilation step.

## Font policy

After a language change FrogUI checks the active pack's rendered values against
the chosen primary TTF's Unicode `cmap`. It ignores inactive locale names in
the selector. If any active value lacks a glyph, FrogUI uses
`TreeFrogUnicode.ttf` for the whole UI and draws it slightly heavier, avoiding
mixed-font labels. PicoArch uses its existing Unicode-capable menu font.

## Why JSON

JSON is editable, UTF-8 native, and can be parsed by a small dependency-free C
loader on the stock rootfs. Gettext requires locale/catalog support the device
does not provide; YAML needs a much larger parser. RTL/shaping is out of scope
for now.
