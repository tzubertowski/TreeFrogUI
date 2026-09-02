# R36SX second microSD socket investigation

## Plain-English result

The console has a second physical microSD socket, but the stock platform only
knows how to use the first one. TreeFrogUI cannot make it a separate ROM source
without identifying additional board-level wiring or control logic.

## What we tested

All runtime tests used an R36SX with the normal system card in SD1, a known-good
FAT32 card in SD2 where applicable, and `log.txt` enabled.

| Test | Result | What it proves |
| --- | --- | --- |
| Stock boot inventory | Only `mmc0` and `/dev/mmcblk0p1` appeared. | Linux sees one MMC host and one card. |
| MMC host rescan | No `mmcblk1` appeared. | SD2 is not a late-enumerating standard MMC block device. |
| USB-storage inventory | Only two MUSB root hubs appeared; no USB device, SCSI disk, or `sdX` node. | SD2 is not an internal USB card reader. |
| SD1 system card booted from physical SD2 | Console reported no SD card. | SD2 is not a simple alternate connector for the active SD bus. |
| Add `num-slots = <2>` to active boot DTB | Console did not boot; stock DTB restored immediately. | The one MMC controller cannot safely be treated as two slots. |
| Add the same property to `cubegm/dtb.bin` | No runtime change. | `dtb.bin` is not the DTB passed to Linux on this boot path. |

The active boot DTB is the deliberately disguised `cubegm/Bubbles.scr` file.
The experimental copy was backed up as `cubegm/Bubbles.scr.treefrog-stock` and
the stock version was restored after the failed boot test.

## What the stock software and Hichip SDK say

The runtime kernel reports one DesignWare MMC host at `1884c000.mmc`, with one
slot. The stock DTB has the corresponding `mmc@1884c000` node.

The public HC16xx SDK documents that same single `hichip,dw-mshc` controller at
`0x1884c000`, IRQ 10. Its active four-bit SD pin group is:

| Pin | SD signal |
| --- | --- |
| `T00` | `D1` |
| `T01` | `D0` |
| `T02` | `CLK` |
| `T03` | `CMD` |
| `T04` | `D3` |
| `T05` | `D2` |

`T06` through `T09` are extra data lanes for the same controller's optional
eight-bit mode; they are not another SD interface. The SDK board DTS variants
do not define a second MMC-controller address or an SD2 mux-select GPIO.

## Conclusion

There is no software-visible SD2 controller to mount, and no safe device-tree
toggle to enable. The fitted SD2 socket may require an undocumented power or
bus-mux select line, may be wired for another board revision, or may not be
electrically connected for this configuration.

The next meaningful investigation is hardware continuity testing from SD2's
`CMD`, `CLK`, and `DAT0` pins to the SoC's documented SD traces and nearby
switch/level-shifter parts. Do not ship another DTB experiment until that
identifies an actual select/power signal.

## Sources

- [HC16xx D3100 board DTS](https://git.maschath.de/ignatz/hcrtos/-/blob/main/board/hc16xx/common/dts/hc16xx-db-d3100-v20.dts)
- [HC16xx pinmux definitions](https://git.maschath.de/ignatz/hcrtos/-/blob/main/components/kernel/source/include/uapi/hcuapi/pinmux/hc16xx_pinmux.h)
