from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from usb_overlay import patch_musb_host_otg_support, patch_musb_irq_lifecycle

SOURCE = '''static void hc16xx_musb_enable(struct musb *musb)
{
    struct hc16xx_glue *glue = get(musb);
    enable_irq(glue->irq);
}

static void hc16xx_musb_disable(struct musb *musb)
{
    struct hc16xx_glue *glue = get(musb);
    disable_irq(glue->irq);
}

static const struct musb_platform_ops ops = {
\t.enable\t\t= hc16xx_musb_enable,
\t.disable\t= hc16xx_musb_disable,
};
int probe(void) {
\tdisable_irq(glue->irq);
\treturn 0;

err_pdev:
    return -1;
}
'''


def test_no_nested_irq_depth_or_waiting_under_musb_spinlock():
    patched = patch_musb_irq_lifecycle(SOURCE)
    assert 'enable_irq(' not in patched and 'disable_irq(' not in patched
    assert patch_musb_irq_lifecycle(patched) == patched
    assert 'Core owns IRQ registration' in patched
    # No claim that this model explains the old physical enumeration failure:
    # regression scope is removal of waiting IRQ-depth calls from the glue.
    assert '.disable' not in patched


def test_unknown_callback_or_probe_fails_closed():
    with pytest.raises(ValueError):
        patch_musb_irq_lifecycle(SOURCE.replace('disable_irq(glue->irq);', 'custom_disable();'))
    with pytest.raises(ValueError):
        patch_musb_irq_lifecycle(SOURCE.replace('err_pdev:', 'different:'))
    with pytest.raises(ValueError):
        patch_musb_irq_lifecycle(SOURCE.replace('enable_irq(glue->irq);', 'writel(1, regs);\n    enable_irq(glue->irq);'))


GLUE_FIXTURE = ROOT / 'payload/kernel_usb_cdc_vm_v2/build_usb_glue.c'


def test_patch_musb_host_otg_support_real_glue_and_fail_closed():
    if not GLUE_FIXTURE.exists():
        pytest.skip('payload/kernel_usb_cdc_vm_v2/build_usb_glue.c not present')
    raw = GLUE_FIXTURE.read_text()
    patched = patch_musb_host_otg_support(raw)
    assert patched == patch_musb_host_otg_support(patched)
    assert 'u8\t\t\trole_mode;' in patched
    assert 'readl(glue->musb->mregs + USB_O_UTMI)' not in patched
    assert 'writel(reg, glue->musb->mregs + USB_O_UTMI)' not in patched
    assert 'MUSB_DEVCTL_SESSION' in patched
    assert 'platform_device_add_data' in patched
    assert 'case MUSB_OTG:' in patched
    with pytest.raises(ValueError, match='unexpected HC16xx USB glue block'):
        patch_musb_host_otg_support(raw.replace('readl(glue->musb->mregs + USB_O_UTMI)', 'custom_utmi_read()', 1))

    integrator = (ROOT / 'scripts/kernel_lab/integrate_ports.py').read_text()
    assert 'patch_musb_host_otg_support' in integrator
    assert 'R36_OTG_WIFI_BT' in integrator


def _write_musb_mock_headers(inc_dir: Path) -> None:
    (inc_dir / 'linux' / 'phy').mkdir(parents=True, exist_ok=True)
    (inc_dir / 'linux' / 'usb').mkdir(parents=True, exist_ok=True)

    (inc_dir / 'linux' / 'kernel.h').write_text(
        '#ifndef MOCK_KERNEL_H\n#define MOCK_KERNEL_H\n'
        '#include <stdint.h>\n#include <stddef.h>\n#include <stdbool.h>\n'
        'typedef uint8_t u8;\ntypedef uint16_t u16;\ntypedef uint32_t u32;\n'
        'typedef int spinlock_t;\n'
        '#define spin_lock_irqsave(l, f) do { (void)(l); (f) = 0; } while (0)\n'
        '#define spin_unlock_irqrestore(l, f) do { (void)(l); (void)(f); } while (0)\n'
        '#define BIT(nr) (1UL << (nr))\n'
        '#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))\n'
        '#define __iomem\n'
        '#define udelay(us) do { (void)(us); } while (0)\n'
        '#define mdelay(ms) do { (void)(ms); } while (0)\n'
        '#define dev_warn(d, ...) do { (void)(d); } while (0)\n'
        '#define dev_err(d, ...) do { (void)(d); } while (0)\n'
        '#define IS_ERR(x) ((uintptr_t)(x) >= (uintptr_t)(-4095L))\n'
        '#define PTR_ERR(x) ((int)(intptr_t)(x))\n'
        '#endif\n'
    )
    (inc_dir / 'linux' / 'errno.h').write_text('#include <errno.h>\n#ifndef EOPNOTSUPP\n#define EOPNOTSUPP 95\n#endif\n')
    (inc_dir / 'linux' / 'module.h').write_text(
        '#define MODULE_DESCRIPTION(x)\n#define MODULE_AUTHOR(x)\n#define MODULE_LICENSE(x)\n'
        '#define MODULE_DEVICE_TABLE(t, n)\n'
    )
    (inc_dir / 'linux' / 'of.h').write_text(
        '#ifndef MOCK_OF_H\n#define MOCK_OF_H\n'
        'struct device_node { int dummy; };\n'
        'struct of_device_id { char compatible[64]; };\n'
        '#define of_match_ptr(x) (x)\n#endif\n'
    )
    (inc_dir / 'linux' / 'clk.h').write_text(
        '#ifndef MOCK_CLK_H\n#define MOCK_CLK_H\n'
        'struct clk { int enabled; };\nstruct device;\n'
        'struct clk *devm_clk_get(struct device *d, const char *id);\n'
        'int clk_prepare_enable(struct clk *c);\n'
        'void clk_disable_unprepare(struct clk *c);\n#endif\n'
    )
    (inc_dir / 'linux' / 'reset.h').write_text(
        '#ifndef MOCK_RESET_H\n#define MOCK_RESET_H\n'
        'struct reset_control { int resets; };\nstruct device;\n'
        'struct reset_control *devm_reset_control_get_exclusive(struct device *d, const char *id);\n'
        'int reset_control_reset(struct reset_control *r);\n#endif\n'
    )
    (inc_dir / 'linux' / 'phy' / 'phy.h').write_text(
        '#ifndef MOCK_PHY_H\n#define MOCK_PHY_H\n'
        'enum phy_mode { PHY_MODE_USB_HOST = 1, PHY_MODE_USB_DEVICE = 2 };\n'
        'struct phy { int init_count; int power_count; enum phy_mode mode; };\nstruct device;\nstruct device_node;\n'
        'struct phy *devm_of_phy_get_by_index(struct device *d, struct device_node *np, int idx);\n'
        'int phy_init(struct phy *p);\nvoid phy_exit(struct phy *p);\n'
        'int phy_set_mode(struct phy *p, enum phy_mode m);\n'
        'int phy_power_on(struct phy *p);\nint phy_power_off(struct phy *p);\n#endif\n'
    )
    (inc_dir / 'linux' / 'usb' / 'role.h').write_text(
        '#ifndef MOCK_ROLE_H\n#define MOCK_ROLE_H\n'
        'enum usb_role { USB_ROLE_NONE = 0, USB_ROLE_HOST = 1, USB_ROLE_DEVICE = 2 };\n'
        'struct device;\n'
        'struct usb_role_switch;\n'
        'struct usb_role_switch_desc { int (*set)(struct usb_role_switch *, enum usb_role); void *driver_data; void *fwnode; };\n'
        'struct usb_role_switch { struct usb_role_switch_desc desc; };\n'
        'struct usb_role_switch *usb_role_switch_register(struct device *d, const struct usb_role_switch_desc *desc);\n'
        'void *usb_role_switch_get_drvdata(struct usb_role_switch *sw);\n#endif\n'
    )
    (inc_dir / 'linux' / 'usb' / 'usb_phy_generic.h').write_text('#ifndef MOCK_UPHY_H\n#define MOCK_UPHY_H\n#endif\n')
    (inc_dir / 'linux' / 'platform_device.h').write_text(
        '#ifndef MOCK_PDEV_H\n#define MOCK_PDEV_H\n#include <linux/kernel.h>\n#include <linux/of.h>\n'
        'typedef int irqreturn_t;\n#define IRQ_NONE 0\n#define IRQ_HANDLED 1\n'
        '#define PLATFORM_DEVID_AUTO (-1)\n#define IORESOURCE_MEM 0x200\n#define GFP_KERNEL 0\n'
        'struct resource { u32 start; u32 end; const char *name; unsigned long flags; };\n'
        '#define DEFINE_RES_IRQ_NAMED(irq, nm) (struct resource){ .start = (u32)(irq), .name = (nm), .flags = 0x400 }\n'
        'struct device { struct device *parent; struct device_node *of_node; void *driver_data; void *platform_data; };\n'
        'struct platform_device { const char *name; int id; struct device dev; };\n'
        'struct device_driver { const char *name; const struct of_device_id *of_match_table; };\n'
        'struct platform_driver { int (*probe)(struct platform_device *); void (*remove)(struct platform_device *); struct device_driver driver; };\n'
        '#define module_platform_driver(x)\n'
        'static inline void dev_set_drvdata(struct device *d, void *p) { d->driver_data = p; }\n'
        'static inline void *dev_get_drvdata(const struct device *d) { return d->driver_data; }\n'
        'static inline void platform_set_drvdata(struct platform_device *p, void *d) { p->dev.driver_data = d; }\n'
        'static inline void *platform_get_drvdata(const struct platform_device *p) { return p->dev.driver_data; }\n'
        'static inline void *dev_fwnode(struct device *d) { return d->of_node; }\n'
        'void *devm_kzalloc(struct device *d, size_t sz, int gfp);\n'
        'int platform_get_irq_byname(struct platform_device *p, const char *name);\n'
        'struct resource *platform_get_resource(struct platform_device *p, unsigned int type, unsigned int num);\n'
        'struct platform_device *platform_device_alloc(const char *name, int id);\n'
        'int platform_device_add_resources(struct platform_device *p, const struct resource *r, unsigned int num);\n'
        'int platform_device_add_data(struct platform_device *p, const void *data, size_t size);\n'
        'int platform_device_add(struct platform_device *p);\n'
        'void platform_device_put(struct platform_device *p);\n'
        'void platform_device_unregister(struct platform_device *p);\n'
        '#endif\n'
    )
    (inc_dir / 'musb_core.h').write_text(
        '#ifndef MOCK_MUSB_CORE_H\n#define MOCK_MUSB_CORE_H\n'
        '#include <linux/platform_device.h>\n#include <linux/phy/phy.h>\n'
        'enum { FIFO_TX = 1, FIFO_RX = 2 };\n'
        'enum { MUSB_UNDEFINED = 0, MUSB_HOST = 1, MUSB_PERIPHERAL = 2, MUSB_OTG = 3 };\n'
        'enum usb_dr_mode { USB_DR_MODE_UNKNOWN = 0, USB_DR_MODE_HOST = 1, USB_DR_MODE_PERIPHERAL = 2, USB_DR_MODE_OTG = 3 };\n'
        '#define MUSB_EP_FIFO_SINGLE(n, s, m) { (n), (s), (m) }\n'
        '#define MUSB_INDEXED_EP 1\n'
        '#define MUSB_INTRUSB 0x0a\n#define MUSB_INTRRX 0x04\n#define MUSB_INTRTX 0x02\n'
        '#define MUSB_INTR_RESET 0x04\n#define MUSB_FADDR 0x00\n#define MUSB_DEVCTL 0x60\n#define MUSB_DEVCTL_SESSION 0x01\n'
        '#define MUSB_HST_MODE(m) do { (m)->is_host = 1; } while (0)\n'
        '#define MUSB_DEV_MODE(m) do { (m)->is_host = 0; } while (0)\n'
        '#define is_host_active(m) ((m)->is_host)\n'
        'struct musb_fifo_cfg { int ep; int dir; int maxpacket; };\n'
        'struct musb;\n'
        'struct musb_platform_ops {\n'
        '    int (*init)(struct musb *);\n'
        '    int (*exit)(struct musb *);\n'
        '    int (*set_mode)(struct musb *, u8);\n'
        '    u32 quirks;\n'
        '};\n'
        'struct musb_hdrc_config {\n'
        '    struct musb_fifo_cfg *fifo_cfg;\n'
        '    size_t fifo_cfg_size;\n'
        '    int multipoint; int dyn_fifo; int num_eps; int ram_bits;\n'
        '};\n'
        'struct musb_hdrc_platform_data {\n'
        '    u8 mode;\n'
        '    const struct musb_hdrc_config *config;\n'
        '    const struct musb_platform_ops *platform_ops;\n'
        '};\n'
        'struct musb {\n'
        '    spinlock_t lock;\n'
        '    struct device *controller;\n'
        '    void *mregs;\n'
        '    struct phy *phy;\n'
        '    bool is_host;\n'
        '    u8 int_usb;\n'
        '    u16 int_rx; u16 int_tx;\n'
        '    irqreturn_t (*isr)(int, void *);\n'
        '};\n'
        'u8 readb(const void *addr);\nvoid writeb(u8 val, void *addr);\n'
        'u8 musb_readb(void *base, u32 off);\nvoid musb_writeb(void *base, u32 off, u8 val);\n'
        'u8 musb_clearb(void *base, u32 off);\nu16 musb_clearw(void *base, u32 off);\n'
        'void musb_ep_select(void *base, int ep);\nirqreturn_t musb_interrupt(struct musb *m);\n'
        'enum usb_dr_mode usb_get_dr_mode(struct device *d);\n'
        '#endif\n'
    )


def test_patched_hc16xx_glue_c_host_otg_peripheral_runtime(tmp_path):
    if not GLUE_FIXTURE.exists():
        pytest.skip('payload/kernel_usb_cdc_vm_v2/build_usb_glue.c not present')
    inc_dir = tmp_path / 'include'
    _write_musb_mock_headers(inc_dir)

    patched_glue = tmp_path / 'patched_hc16xx.c'
    patched_glue.write_text(patch_musb_host_otg_support(GLUE_FIXTURE.read_text()))

    harness = tmp_path / 'glue_runtime_test.c'
    harness.write_text(
        f'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <musb_core.h>
#include <linux/clk.h>
#include <linux/reset.h>
#include <linux/usb/role.h>

static uint8_t mmio[4096];
static int session_clears, session_sets;
static enum usb_dr_mode active_dr_mode = USB_DR_MODE_PERIPHERAL;
static struct clk g_clk;
static struct reset_control g_reset;
static struct phy g_phy;
static struct usb_role_switch g_role_sw;
static struct resource g_mem_res = {{ .start = 0x18844000u, .end = 0x18844fffu, .flags = IORESOURCE_MEM }};
static struct platform_device *last_child_pdev;

u8 readb(const void *addr) {{
    uintptr_t off = (const uint8_t *)addr - mmio;
    assert(off < sizeof(mmio));
    return mmio[off];
}}
void writeb(u8 val, void *addr) {{
    uintptr_t off = (uint8_t *)addr - mmio;
    assert(off < sizeof(mmio));
    mmio[off] = val;
}}
u8 musb_readb(void *base, u32 off) {{ return readb((uint8_t *)base + off); }}
void musb_writeb(void *base, u32 off, u8 val) {{
    if (off == MUSB_DEVCTL) {{
        if (!(val & MUSB_DEVCTL_SESSION)) session_clears++;
        else session_sets++;
    }}
    writeb(val, (uint8_t *)base + off);
}}
u8 musb_clearb(void *base, u32 off) {{ u8 v = musb_readb(base, off); musb_writeb(base, off, 0); return v; }}
u16 musb_clearw(void *base, u32 off) {{ (void)base; (void)off; return 0; }}
void musb_ep_select(void *base, int ep) {{ (void)base; (void)ep; }}
irqreturn_t musb_interrupt(struct musb *m) {{ (void)m; return IRQ_HANDLED; }}
enum usb_dr_mode usb_get_dr_mode(struct device *d) {{ (void)d; return active_dr_mode; }}

void *devm_kzalloc(struct device *d, size_t sz, int gfp) {{ (void)d; (void)gfp; return calloc(1, sz); }}
int platform_get_irq_byname(struct platform_device *p, const char *name) {{ (void)p; return !strcmp(name, "mc") ? 53 : 52; }}
struct resource *platform_get_resource(struct platform_device *p, unsigned int t, unsigned int n) {{
    (void)p; (void)t; (void)n; return &g_mem_res;
}}
struct platform_device *platform_device_alloc(const char *name, int id) {{
    struct platform_device *p = calloc(1, sizeof(*p));
    p->name = name; p->id = id;
    return p;
}}
int platform_device_add_resources(struct platform_device *p, const struct resource *r, unsigned int num) {{
    (void)p; (void)r; (void)num; return 0;
}}
int platform_device_add_data(struct platform_device *p, const void *data, size_t size) {{
    void *copy = malloc(size);
    memcpy(copy, data, size);
    p->dev.platform_data = copy;
    return 0;
}}
int platform_device_add(struct platform_device *p) {{ last_child_pdev = p; return 0; }}
void platform_device_put(struct platform_device *p) {{ free(p); }}
void platform_device_unregister(struct platform_device *p) {{ free(p->dev.platform_data); free(p); }}

struct clk *devm_clk_get(struct device *d, const char *id) {{ (void)d; (void)id; return &g_clk; }}
int clk_prepare_enable(struct clk *c) {{ c->enabled = 1; return 0; }}
void clk_disable_unprepare(struct clk *c) {{ c->enabled = 0; }}
struct reset_control *devm_reset_control_get_exclusive(struct device *d, const char *id) {{ (void)d; (void)id; return &g_reset; }}
int reset_control_reset(struct reset_control *r) {{ r->resets++; return 0; }}
struct phy *devm_of_phy_get_by_index(struct device *d, struct device_node *np, int idx) {{
    (void)d; (void)np; (void)idx; return &g_phy;
}}
int phy_init(struct phy *p) {{ p->init_count++; return 0; }}
void phy_exit(struct phy *p) {{ p->init_count--; }}
int phy_set_mode(struct phy *p, enum phy_mode m) {{ p->mode = m; return 0; }}
int phy_power_on(struct phy *p) {{ p->power_count++; return 0; }}
int phy_power_off(struct phy *p) {{ p->power_count--; return 0; }}
struct usb_role_switch *usb_role_switch_register(struct device *d, const struct usb_role_switch_desc *desc) {{
    (void)d; g_role_sw.desc = *desc; return &g_role_sw;
}}
void *usb_role_switch_get_drvdata(struct usb_role_switch *sw) {{ return sw->desc.driver_data; }}

#include "{patched_glue.as_posix()}"

static void run_case(enum usb_dr_mode dr_mode, u8 expected_pdata_mode, u8 expected_utmi, u8 expected_session) {{
    struct device_node np = {{0}};
    struct platform_device glue_pdev = {{ .name = "hc16xx", .dev = {{ .of_node = &np }} }};
    struct device controller = {{ .parent = &glue_pdev.dev }};
    struct musb musb;

    memset(mmio, 0, sizeof(mmio));
    mmio[USB_O_VBUS] = 0x5Au; /* adjacent register canary */
    mmio[MUSB_DEVCTL] = MUSB_DEVCTL_SESSION;
    memset(&musb, 0, sizeof(musb));
    musb.controller = &controller;
    musb.mregs = mmio;
    musb.is_host = false; /* deliberately false at init */
    session_clears = session_sets = 0;
    active_dr_mode = dr_mode;
    last_child_pdev = NULL;

    assert(hc16xx_glue_probe(&glue_pdev) == 0);
    assert(last_child_pdev && last_child_pdev->dev.platform_data);
    const struct musb_hdrc_platform_data *pdata = last_child_pdev->dev.platform_data;
    assert(pdata->mode == expected_pdata_mode);
    assert(pdata->platform_ops->init(&musb) == 0);
    assert(mmio[USB_O_UTMI] == expected_utmi);
    assert(mmio[USB_O_VBUS] == 0x5Au);
    assert((mmio[MUSB_DEVCTL] & MUSB_DEVCTL_SESSION) == expected_session);
    if (expected_session) assert(session_clears >= 1 && session_sets >= 1);

    if (dr_mode == USB_DR_MODE_OTG) {{
        assert(g_role_sw.desc.set(&g_role_sw, USB_ROLE_DEVICE) == 0);
        assert(mmio[USB_O_UTMI] == 0x9Cu && !musb.is_host);
        assert((mmio[MUSB_DEVCTL] & MUSB_DEVCTL_SESSION) == 0);
        assert(mmio[USB_O_VBUS] == 0x5Au);

        assert(g_role_sw.desc.set(&g_role_sw, USB_ROLE_HOST) == 0);
        assert(mmio[USB_O_UTMI] == 0x8Cu && musb.is_host);
        assert((mmio[MUSB_DEVCTL] & MUSB_DEVCTL_SESSION) == MUSB_DEVCTL_SESSION);
        assert(mmio[USB_O_VBUS] == 0x5Au);
    }}

    pdata->platform_ops->exit(&musb);
    hc16xx_glue_remove(&glue_pdev);
    free(platform_get_drvdata(&glue_pdev));
}}

int main(void) {{
    (void)hc16xx_driver;
    run_case(USB_DR_MODE_PERIPHERAL, MUSB_PERIPHERAL, 0x9Cu, 0);
    run_case(USB_DR_MODE_HOST, MUSB_HOST, 0x8Cu, MUSB_DEVCTL_SESSION);
    run_case(USB_DR_MODE_OTG, MUSB_OTG, 0x8Cu, MUSB_DEVCTL_SESSION);
    puts("HC16XX_MUSB_HOST_OTG_GLUE=PASS");
    return 0;
}}
'''
    )

    exe = tmp_path / 'glue_runtime_test.exe'
    subprocess.run(
        ['gcc', '-std=gnu11', '-Wall', '-Wextra', '-Wno-unused-parameter', '-Werror', f'-I{inc_dir}', str(harness), '-o', str(exe)],
        check=True,
        capture_output=True,
        timeout=20,
    )
    res = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=5)
    assert 'HC16XX_MUSB_HOST_OTG_GLUE=PASS' in res.stdout
