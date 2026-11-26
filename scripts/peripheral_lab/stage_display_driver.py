"""Port the pinned GPL display reference to guarded, fixed-timing R36 bring-up."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/kernel_lab"))
from preflight import properties

REF_COMMIT = "bff93e84fe79c9e67bde284dfe4d58054b62282b"


def replace_once(text, before, after):
    assert text.count(before) == 1, before[:120]
    return text.replace(before, after, 1)


def function_body(text, name, body):
    match = re.search(r"^static [^;{}]+\b" + re.escape(name) + r"\([^;{}]*\)\s*\{", text, re.M)
    assert match, name
    start = match.end() - 1
    depth, end = 1, start + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[:start] + "{\n" + body.strip("\n") + "\n}" + text[end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error("output must be new with an existing parent")
    reference = ROOT / "analysis/gb350-linux-reference"
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=reference).decode().strip() == REF_COMMIT
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", "kernel/drivers/gpu/drm/hichip", "kernel/include/uapi/drm/hc16xx_drm.h"], cwd=reference, check=True)
    source = reference / "kernel/drivers/gpu/drm/hichip/hc16xx_drm.c"
    text = source.read_text()
    text = replace_once(text, "// SPDX-License-Identifier: GPL-2.0\n", "// SPDX-License-Identifier: GPL-2.0\n/* R36 fixed-boot-timing port; see port_source.json for the pinned GPL source. */\n")
    board_dtb = ROOT / "analysis/boot_crypto/original_Bubbles.scr"
    tree = properties(board_dtb.read_bytes())
    timing = tree["/hcrtos/de-engine/VPInitInfo/rgb-cfg/timing-para"]
    cell = lambda name: struct.unpack(">I", timing[name])[0]
    width, height = cell("h-active-len"), cell("v-active-len")
    ht, vt = cell("h-total-len"), cell("v-total-len")
    assert ht == width + cell("h-front-len") + cell("h-sync-len") + cell("h-back-len")
    assert vt == height + cell("v-front-len") + cell("v-sync-len") + cell("v-back-len")
    assert (width, height, ht, vt) == (640, 480, 868, 518)
    clock = ht * vt * cell("frame-rate") // 1000
    boot = tree["/hcrtos/boot-fb0"]
    base, region_size = struct.unpack(">II", boot["buffer-phy-static"])
    header_size = struct.unpack(">I", boot["buffer-header-size"])[0]
    assert (base, header_size) == (0x02F91E50, 4096)

    contract = f"""/* SPDX-License-Identifier: GPL-2.0 */
/* Generated from this board's actual Bubbles.scr, not GB350 timings. */
#ifndef R36_DISPLAY_CONTRACT_H
#define R36_DISPLAY_CONTRACT_H
#ifdef __KERNEL__
#include <linux/types.h>
typedef u32 r36_display_word;
#else
#include <stdint.h>
typedef uint32_t r36_display_word;
#endif
#define R36_DISPLAY_WIDTH {width}u
#define R36_DISPLAY_HEIGHT {height}u
#define R36_DISPLAY_HTOTAL {ht}u
#define R36_DISPLAY_VTOTAL {vt}u
#define R36_DISPLAY_DESC_PHYS 0x02f90000u
#define R36_DISPLAY_BOOT_BASE 0x{base:08x}u
#define R36_DISPLAY_BOOT_HEADER {header_size}u
#define R36_DISPLAY_BOOT_BYTES {region_size}u
static inline int r36_display_ddr(r36_display_word raw, r36_display_word *physical)
{{
    if (raw >= 0x10000000u) return -1;
    *physical = raw & 0x07ffffffu; /* measured 128-MiB DDR alias */
    return 0;
}}
static inline int r36_display_descriptor(r36_display_word raw, r36_display_word *physical)
{{
    if (r36_display_ddr(raw, physical) || (*physical & 31u)) return -1;
    return *physical >= R36_DISPLAY_BOOT_BASE &&
           *physical <= R36_DISPLAY_BOOT_BASE + R36_DISPLAY_BOOT_HEADER - 0x280u ? 0 : -1;
}}
static inline int r36_display_timing(r36_display_word total)
{{ return total == (R36_DISPLAY_VTOTAL << 16 | R36_DISPLAY_HTOTAL * 2u); }}
static inline int r36_display_header(const r36_display_word *w)
{{
    unsigned int format = (w[0] >> 4) & 15u, bpp, pitch = w[5] >> 16;
    r36_display_word physical;
    if (!(w[0] & 1u) || (format != 0u && format != 1u && format != 6u)) return -1;
    bpp = format == 6u ? 2u : 4u;
    if (w[2] != ((R36_DISPLAY_WIDTH - 1u) << 16) ||
        w[3] != ((R36_DISPLAY_HEIGHT - 1u) << 16) ||
        w[4] != (R36_DISPLAY_WIDTH | R36_DISPLAY_HEIGHT << 16)) return -1;
    if (pitch < R36_DISPLAY_WIDTH * bpp || pitch > 16383u || r36_display_ddr(w[7], &physical)) return -1;
    if (physical < R36_DISPLAY_BOOT_BASE + R36_DISPLAY_BOOT_HEADER) return -1;
    return (unsigned long long)physical + (R36_DISPLAY_HEIGHT - 1u) * pitch +
           R36_DISPLAY_WIDTH * bpp <= (unsigned long long)R36_DISPLAY_BOOT_BASE + R36_DISPLAY_BOOT_BYTES ? 0 : -1;
}}
#endif
"""
    text = replace_once(text, '#include <drm/hc16xx_drm.h>', '#include "hc16xx_drm.h"\n#include "r36_display_contract.h"')
    text = re.sub(r"^#define VBLANK_LINE[^\n]*\n", "", text, flags=re.M)
    text = re.sub(r"^#define ACTIVE_FIRST_LINE[^\n]*\n", "", text, flags=re.M)
    text = text.replace("ACTIVE_FIRST_LINE", "hc->active_first_line").replace("VBLANK_LINE", "hc->vblank_line")
    text = replace_once(text, "unsigned int event_age;", "u32 active_first_line, vblank_line, boot_descriptor, flip_timeouts;\n\tunsigned int event_age;")
    text = function_body(text, "hc16xx_totals_ok", "\treturn htotal == hc->native.htotal && vtotal == hc->native.vtotal;")
    text = function_body(text, "hc16xx_set_timing", """
\tif (!r36_display_timing(readl(hc->regs + DE_TOTAL)) ||
\t    htotal != hc->native.htotal || vtotal != hc->native.vtotal)
\t\tdev_err_ratelimited(hc->drm.dev, "boot timing changed; retiming disabled\\n");
""")
    for array in ("hc16xx_rates", "hc16xx_extra_modes"):
        text, count = re.subn(r"static const u16 " + array + r"\[\]\[2\] = \{.*?\n\};\n", "", text, flags=re.S)
        assert count == 1, array
    text = function_body(text, "hc16xx_connector_get_modes", """
\tstruct hc16xx_drm *hc = to_hc(connector->dev);
\tstruct drm_display_mode *mode = drm_mode_duplicate(connector->dev, &hc->native);
\tif (!mode) return 0;
\tmode->type = DRM_MODE_TYPE_DRIVER | DRM_MODE_TYPE_PREFERRED;
\tdrm_mode_probed_add(connector, mode);
\treturn 1;
""")
    text = replace_once(text, "if (mode->hdisplay < 16 || mode->vdisplay < 16 ||", "if (mode->hdisplay != hc->native.hdisplay || mode->vdisplay != hc->native.vdisplay ||")
    text = replace_once(text, "if (cs->enable) {\n\t\tdrm_mode_copy", "if (cs->enable) {\n\t\tif (!r36_display_timing(readl(to_hc(crtc->dev)->regs + DE_TOTAL)))\n\t\t\treturn -ESTALE;\n\t\tdrm_mode_copy")
    text = replace_once(text, "if (hc->event_age > 4)\n\t\t\t\tdev_warn_ratelimited", "if (hc->event_age > 4)\n\t\t\t\thc->flip_timeouts++;\n\t\t\tif (hc->event_age > 4)\n\t\t\t\tdev_warn_ratelimited")
    optional_start = text.index("\t/*\n\t * Optional: the 2D engine")
    optional_end = text.index('\tmem = of_parse_phandle', optional_start)
    text = text[:optional_start] + "\t/* First board slice: no GE clock/reset or DSI access. */\n\tmutex_init(&hc->ge_lock);\n\tmutex_init(&hc->panel_lock);\n" + text[optional_end:]
    text = replace_once(text, "if (!rmem || rmem->size < DESC_OFFSET + NUM_LAYERS * 2 * DESC_SIZE)",
                        "if (!rmem || rmem->base != R36_DISPLAY_DESC_PHYS || rmem->size != 4096)")
    before = "\t/* Colour enhancement/CSC as the bootloader set it up. */\n\tfor (i = 0; i < DESC_ENHANCE_WORDS; i++)\n\t\thc->enhance[i] = readl(hc->desc + DESC_BOOT + DESC_ENHANCE + 4 * i);"
    text = replace_once(text, before, "\tret = r36_capture_boot(hc);\n\tif (ret) return ret;")
    text = replace_once(text, "drm_mode_set_crtcinfo(&hc->native, 0);\t/* adjusted_mode is a copy */", """drm_mode_set_crtcinfo(&hc->native, 0);
\thc->active_first_line = hc->native.vtotal - hc->native.vsync_start + 1;
\thc->vblank_line = hc->active_first_line + hc->native.vdisplay;
\tif (hc->active_first_line != 17 || hc->vblank_line >= hc->native.vtotal) return -EINVAL;""")
    text = replace_once(text, "\tdrm_client_setup(drm, NULL);", "\t/* No automatic framebuffer client: userspace opts into the first modeset. */")
    text = replace_once(text, '{ .compatible = "hichip,hc16xx-display" },', '{ .compatible = "r36lab,hc16e310-display" },')
    text = replace_once(text, '.name\t\t\t= "hc16xx",', '.name\t\t\t= "r36-hc16xx",')
    text = replace_once(text, '.name\t\t= "hc16xx-drm",', '.name\t\t= "r36-hc16xx-drm",')
    text = replace_once(text, "\thc->regs = devm_platform_ioremap_resource(pdev, 0);", """\t{
\t\tstruct resource *res = platform_get_resource(pdev, IORESOURCE_MEM, 0);
\t\tif (!res || res->start != 0x1883a000 || resource_size(res) != 0x1000) return -EINVAL;
\t}
\thc->regs = devm_platform_ioremap_resource(pdev, 0);""")
    text = replace_once(text, "\tplatform_set_drvdata(pdev, hc);", "\tplatform_set_drvdata(pdev, hc);\n\tret = dma_set_mask_and_coherent(dev, DMA_BIT_MASK(32));\n\tif (ret) return ret;")
    text = replace_once(text, "\thc->native.type = DRM_MODE_TYPE_DRIVER | DRM_MODE_TYPE_PREFERRED;", """\tif (hc->native.hdisplay != R36_DISPLAY_WIDTH || hc->native.vdisplay != R36_DISPLAY_HEIGHT ||
\t    hc->native.htotal != R36_DISPLAY_HTOTAL || hc->native.vtotal != R36_DISPLAY_VTOTAL) return -EINVAL;
\thc->native.type = DRM_MODE_TYPE_DRIVER | DRM_MODE_TYPE_PREFERRED;""")
    capture = """
static int r36_capture_boot(struct hc16xx_drm *hc)
{
\tu32 raw = readl(hc->regs + GMA_ACTIVE + GMA_DMBA), physical, words[8], line, sample;
\tvoid __iomem *boot;
\tint i;
\tif (!r36_display_timing(readl(hc->regs + DE_TOTAL)))
\t\treturn dev_err_probe(hc->drm.dev, -ESTALE, "native timing differs from board DT\\n");
\tif (readl(hc->regs + LAYER(1) + GMA_ACTIVE + GMA_CTL) & GMA_CTL_ON) return -EBUSY;
\tline = (readl(hc->regs + DE_LINE) >> 16) & 0xfff;
\tif (readl_poll_timeout(hc->regs + DE_LINE, sample, ((sample >> 16) & 0xfff) != line, 500, 40000)) return -ETIMEDOUT;
\tif (!(readl(hc->regs + GMA_ACTIVE + GMA_CTL) & GMA_CTL_ON) || r36_display_descriptor(raw, &physical))
\t\treturn dev_err_probe(hc->drm.dev, -ENODEV, "no recognized boot descriptor\\n");
\tboot = devm_ioremap(hc->drm.dev, physical, DESC_SIZE);
\tif (!boot) return -ENOMEM;
\tfor (i = 0; i < 8; i++) words[i] = readl(boot + 4 * i);
\tif (r36_display_header(words)) return -EBADMSG;
\tfor (i = 0; i < DESC_ENHANCE_WORDS; i++) hc->enhance[i] = readl(boot + DESC_ENHANCE + 4 * i);
\tif (readl(hc->regs + GMA_ACTIVE + GMA_DMBA) != raw) return -EAGAIN;
\thc->boot_descriptor = physical;
\treturn 0;
}

static ssize_t health_show(struct device *dev, struct device_attribute *attr, char *buf)
{
\tstruct hc16xx_drm *hc = dev_get_drvdata(dev);
\tu32 active = readl(hc->regs + GMA_ACTIVE + GMA_DMBA), pixel = 0, format = 0, wh = 0, pitch = 0;
\tif (active >= hc->desc_phys + DESC_OFFSET && active <= hc->desc_phys + 4096 - DESC_SIZE) {
\t\tvoid __iomem *d = hc->desc + active - hc->desc_phys;
\t\tformat = (readl(d) >> 4) & 15;
\t\tpixel = readl(d + 0x1c); wh = readl(d + 0x10); pitch = readl(d + 0x14) >> 16;
\t}
\treturn sysfs_emit(buf, "boot_descriptor=%08x active_descriptor=%08x programmed_descriptor=%08x line=%u flip_timeouts=%u timing_stable=%u active_on=%u pixel=%08x format=%u width=%u height=%u pitch=%u\\n",
\t\thc->boot_descriptor, active, hc->dmba[0],
\t\t(readl(hc->regs + DE_LINE) >> 16) & 0xfff, READ_ONCE(hc->flip_timeouts),
\t\tr36_display_timing(readl(hc->regs + DE_TOTAL)),
\t\t(unsigned int)(readl(hc->regs + GMA_ACTIVE + GMA_CTL) & GMA_CTL_ON), pixel, format, wh & 0xffff, wh >> 16, pitch);
}
static DEVICE_ATTR_RO(health);
"""
    text = replace_once(text, "static struct attribute *hc16xx_attrs[] = {", capture + "\nstatic struct attribute *hc16xx_attrs[] = {\n\t&dev_attr_health.attr,")
    text = replace_once(text, "\treturn sysfs_emit(buf, \"%s\\n\", hc->panel_off ? \"off\" : \"on\");", "\tif (!hc->dsi) return sysfs_emit(buf, \"unmanaged\\n\");\n\treturn sysfs_emit(buf, \"%s\\n\", hc->panel_off ? \"off\" : \"on\");")
    text = replace_once(text, "static void hc16xx_ge_init(", "static void __maybe_unused hc16xx_ge_init(")
    args.out.mkdir()
    (args.out / "r36_hc16xx_drm.c").write_text(text, encoding="utf-8")
    (args.out / "r36_display_contract.h").write_text(contract, encoding="ascii")
    uapi = (reference / "kernel/include/uapi/drm/hc16xx_drm.h").read_text().replace('#include "drm.h"', '#include <drm/drm.h>')
    (args.out / "hc16xx_drm.h").write_text(uapi)
    (args.out / "Makefile").write_text("obj-m += r36_hc16xx_drm.o\n")
    (args.out / "Kconfig").write_text('''config DRM_R36_HC16XX_DEPS
    bool "R36 external HC16xx display dependencies"
    depends on DRM && OF
    select APERTURE_HELPERS
    select DRM_GEM_DMA_HELPER
    select DRM_KMS_HELPER
    select VIDEOMODE_HELPERS
    help
      Build the helpers required by the separately built R36 display module.
      This option does not enable the board's display node or modeset it.
''')
    abi = """/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
#ifndef R36_DISPLAY_ABI_H
#define R36_DISPLAY_ABI_H
#include <drm/drm.h>
#include <drm/drm_mode.h>
#define R36_DISPLAY_ABI_VALUES 0x52334441u, 1u, sizeof(unsigned long), \\
    sizeof(struct drm_mode_card_res), sizeof(struct drm_mode_get_connector), \\
    sizeof(struct drm_mode_crtc), sizeof(struct drm_mode_create_dumb), \\
    sizeof(struct drm_mode_map_dumb), sizeof(struct drm_mode_fb_cmd), \\
    DRM_IOCTL_MODE_GETRESOURCES, DRM_IOCTL_MODE_GETCONNECTOR, DRM_IOCTL_MODE_GETCRTC, \\
    DRM_IOCTL_MODE_CREATE_DUMB, DRM_IOCTL_MODE_MAP_DUMB, DRM_IOCTL_MODE_ADDFB, DRM_IOCTL_MODE_SETCRTC
#endif
"""
    (args.out / "r36_display_abi.h").write_text(abi)
    text += '\n#include "r36_display_abi.h"\nconst u32 r36_display_abi[] __used __section(".r36abi") = { R36_DISPLAY_ABI_VALUES };\n'
    (args.out / "r36_hc16xx_drm.c").write_text(text, encoding="utf-8")
    dts = f"""// SPDX-License-Identifier: GPL-2.0
// Board values from original Bubbles.scr. Clock is nominal, derived from DT rate.
#include "r36-avp-poll.dts"
/ {{
    reserved-memory {{
        r36_gma_desc: gma-descriptor@2f90000 {{ reg = <0x02f90000 0x1000>; no-map; }};
    }};
    r36_display: display-controller@1883a000 {{
        compatible = "r36lab,hc16e310-display";
        reg = <0x1883a000 0x1000>;
        interrupt-parent = <&intc>;
        interrupts = <40>; /* SoC reference; hardware acceptance still required. */
        memory-region = <&r36_gma_desc>;
        /* Required by DRM's panel-mode parser; physical dimensions unknown. */
        width-mm = <0>; height-mm = <0>;
        status = "disabled";
        panel-timing {{
            clock-frequency = <{clock}>;
            hactive = <{width}>; vactive = <{height}>;
            hfront-porch = <{cell('h-front-len')}>; hsync-len = <{cell('h-sync-len')}>; hback-porch = <{cell('h-back-len')}>;
            vfront-porch = <{cell('v-front-len')}>; vsync-len = <{cell('v-sync-len')}>; vback-porch = <{cell('v-back-len')}>;
            hsync-active = <{cell('h-sync-level')}>; vsync-active = <{cell('v-sync-level')}>; de-active = <{cell('active-polarity')}>;
        }};
    }};
}};
"""
    (args.out / "r36-display.dts").write_text(dts)
    result = {"source_repository": "https://github.com/csnewman/gb350-linux", "source_commit": REF_COMMIT,
              "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "board_dtb_sha256": hashlib.sha256(board_dtb.read_bytes()).hexdigest(),
              "nominal_clock_hz": clock, "pixel_clock_measured": False, "geometry": [width, height], "totals": [ht, vt],
              "descriptor_page": "0x02f90000", "default_enabled": False, "clock_or_timing_writes_enabled": False,
              "GE_enabled": False, "DSI_panel_control_enabled": False, "hardware_verified": False,
              "port_changes": ["128-MiB descriptor/DDR guards", "active boot descriptor capture instead of external early-driver dependency",
                               "board timing guard; no retiming", "vblank after native active area", "native-mode-only enumeration",
                               "no automatic fbdev/client modeset", "flip timeout health counter", "custom board-compatible binding"],
              "files_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.out.iterdir() if p.is_file()}}
    (args.out / "port_source.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
