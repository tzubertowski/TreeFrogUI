"""Tests for hc16xx-adc-ro (/dev/check_adc1, /dev/check_adc5) and userspace battery OSD curve."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
ZIG = Path(r"C:\Users\palpa\Tools\zig-x86_64-windows-0.17.0\zig.exe")


def _write_linux_mock_headers(inc_dir: Path) -> None:
    linux = inc_dir / "linux"
    (linux / "iio").mkdir(parents=True, exist_ok=True)

    (linux / "kernel.h").write_text(
        """#ifndef MOCK_LINUX_KERNEL_H
#define MOCK_LINUX_KERNEL_H
#include <stddef.h>
#include <stdint.h>
#include <errno.h>

typedef uint8_t u8;
typedef int64_t loff_t;

#ifndef __iomem
#define __iomem
#endif
#ifndef __user
#define __user
#endif
#ifndef BIT
#define BIT(nr) (1UL << (nr))
#endif
#ifndef ARRAY_SIZE
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#endif
#ifndef container_of
#define container_of(ptr, type, member) \\
    ((type *)((char *)(ptr) - offsetof(type, member)))
#endif
#ifndef IS_ERR
#define IS_ERR(x) ((uintptr_t)(x) >= (uintptr_t)(-4095L))
#define PTR_ERR(x) ((int)(intptr_t)(x))
#endif
#endif
"""
    )

    (linux / "io.h").write_text(
        """#ifndef MOCK_LINUX_IO_H
#define MOCK_LINUX_IO_H
#include <stdint.h>
static inline uint8_t readb(const volatile void *addr) {
    return *(const volatile uint8_t *)addr;
}
#endif
"""
    )

    (linux / "clk.h").write_text(
        """#ifndef MOCK_LINUX_CLK_H
#define MOCK_LINUX_CLK_H
struct clk { int dummy; };
struct device;
struct clk *devm_clk_get_enabled(struct device *dev, const char *id);
#endif
"""
    )

    (linux / "of.h").write_text(
        """#ifndef MOCK_LINUX_OF_H
#define MOCK_LINUX_OF_H
struct of_device_id { char compatible[64]; };
#endif
"""
    )

    (linux / "module.h").write_text(
        """#ifndef MOCK_LINUX_MODULE_H
#define MOCK_LINUX_MODULE_H
#define THIS_MODULE NULL
#define MODULE_DEVICE_TABLE(type, name)
#define MODULE_LICENSE(x)
#define MODULE_DESCRIPTION(x)
#endif
"""
    )

    (linux / "uaccess.h").write_text(
        """#ifndef MOCK_LINUX_UACCESS_H
#define MOCK_LINUX_UACCESS_H
#include <stddef.h>
unsigned long copy_to_user(void *to, const void *from, unsigned long n);
#endif
"""
    )

    (linux / "fs.h").write_text(
        """#ifndef MOCK_LINUX_FS_H
#define MOCK_LINUX_FS_H
#include <stddef.h>
#include <sys/types.h>
#include <linux/kernel.h>
struct file { void *private_data; };
struct file_operations {
    void *owner;
    ssize_t (*read)(struct file *, char *, size_t, loff_t *);
    loff_t (*llseek)(struct file *, loff_t, int);
};
static inline loff_t noop_llseek(struct file *f, loff_t off, int whence) {
    (void)f; (void)whence;
    return off;
}
#endif
"""
    )

    (linux / "miscdevice.h").write_text(
        """#ifndef MOCK_LINUX_MISCDEVICE_H
#define MOCK_LINUX_MISCDEVICE_H
#include <stdint.h>
#include <linux/fs.h>
#define MISC_DYNAMIC_MINOR 255
struct miscdevice {
    int minor;
    const char *name;
    const struct file_operations *fops;
    uint16_t mode;
};
int misc_register(struct miscdevice *misc);
void misc_deregister(struct miscdevice *misc);
#endif
"""
    )

    (linux / "iio" / "iio.h").write_text(
        """#ifndef MOCK_LINUX_IIO_H
#define MOCK_LINUX_IIO_H
#include <stddef.h>
enum { IIO_VOLTAGE = 0 };
enum { IIO_CHAN_INFO_RAW = 0 };
enum { IIO_VAL_INT = 1 };
#define INDIO_DIRECT_MODE 1
struct iio_chan_spec {
    int type;
    int indexed;
    int channel;
    unsigned long info_mask_separate;
};
struct iio_dev;
struct iio_info {
    int (*read_raw)(struct iio_dev *, const struct iio_chan_spec *, int *, int *, long);
};
struct iio_dev {
    const char *name;
    const struct iio_info *info;
    int modes;
    const struct iio_chan_spec *channels;
    int num_channels;
    void *priv;
};
struct device;
struct iio_dev *devm_iio_device_alloc(struct device *dev, int sizeof_priv);
static inline void *iio_priv(struct iio_dev *indio) { return indio->priv; }
int devm_iio_device_register(struct device *dev, struct iio_dev *indio);
#endif
"""
    )

    (linux / "platform_device.h").write_text(
        """#ifndef MOCK_LINUX_PLATFORM_DEVICE_H
#define MOCK_LINUX_PLATFORM_DEVICE_H
struct device { int id; };
struct platform_device { struct device dev; };
struct of_device_id;
struct device_driver {
    const char *name;
    const struct of_device_id *of_match_table;
};
struct platform_driver {
    int (*probe)(struct platform_device *);
    struct device_driver driver;
};
#define module_platform_driver(drv)
void *devm_platform_ioremap_resource(struct platform_device *pdev, unsigned int idx);
int devm_add_action_or_reset(struct device *dev, void (*action)(void *), void *data);
int dev_err_probe(struct device *dev, int err, const char *fmt, ...);
#endif
"""
    )


def test_hc16xx_adc_ro_char_nodes_calibration_and_battery_curve(tmp_path):
    inc_dir = tmp_path / "include"
    _write_linux_mock_headers(inc_dir)

    driver = ROOT / "scripts/kernel_lab/ports/hc16xx-adc-ro.c"
    osd_hdr = ROOT / "scripts/peripheral_lab/adc_battery_osd.h"
    harness = tmp_path / "hc16xx_adc_ro_test.c"

    harness.write_text(
        f'''
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <linux/platform_device.h>
#include <linux/miscdevice.h>
#include <linux/iio/iio.h>
#include <linux/clk.h>
#include <linux/uaccess.h>

static uint8_t sar_regs[8];
static struct clk fake_clk;
static struct iio_dev *registered_indio;
static struct miscdevice *registered_misc[4];
static int misc_count;
static void (*devm_actions[4])(void *);
static void *devm_action_data[4];
static int devm_action_count;

struct clk *devm_clk_get_enabled(struct device *dev, const char *id) {{
    (void)dev; (void)id; return &fake_clk;
}}

void *devm_platform_ioremap_resource(struct platform_device *pdev, unsigned int idx) {{
    (void)pdev; assert(idx == 0); return sar_regs;
}}

struct iio_dev *devm_iio_device_alloc(struct device *dev, int sizeof_priv) {{
    (void)dev;
    struct iio_dev *indio = calloc(1, sizeof(*indio));
    indio->priv = calloc(1, (size_t)sizeof_priv);
    return indio;
}}

int devm_iio_device_register(struct device *dev, struct iio_dev *indio) {{
    (void)dev;
    registered_indio = indio;
    return 0;
}}

int misc_register(struct miscdevice *misc) {{
    registered_misc[misc_count++] = misc;
    return 0;
}}

void misc_deregister(struct miscdevice *misc) {{ (void)misc; misc_count--; }}

int devm_add_action_or_reset(struct device *dev, void (*action)(void *), void *data) {{
    (void)dev;
    devm_actions[devm_action_count] = action;
    devm_action_data[devm_action_count] = data;
    devm_action_count++;
    return 0;
}}

int dev_err_probe(struct device *dev, int err, const char *fmt, ...) {{
    (void)dev; (void)fmt; return err;
}}

unsigned long copy_to_user(void *to, const void *from, unsigned long n) {{
    memcpy(to, from, n);
    return 0;
}}

#include "{driver.as_posix()}"

/* Route userspace open/read/close from adc_battery_osd.h into the registered miscdevice fops */
static struct file open_files[2];
static loff_t open_pos[2];

static int sim_open(const char *path, int flags) {{
    assert((flags & O_RDWR) == O_RDWR);
    if (!strcmp(path, "/dev/check_adc1")) {{
        open_files[0].private_data = registered_misc[0];
        open_pos[0] = 0;
        return 100;
    }}
    if (!strcmp(path, "/dev/check_adc5")) {{
        open_files[1].private_data = registered_misc[1];
        open_pos[1] = 0;
        return 101;
    }}
    return -1;
}}

static int sim_close(int fd) {{
    assert(fd == 100 || fd == 101);
    return 0;
}}

static ssize_t sim_read(int fd, void *buf, size_t count) {{
    int slot = (fd == 100) ? 0 : 1;
    struct miscdevice *m = open_files[slot].private_data;
    return m->fops->read(&open_files[slot], (char *)buf, count, &open_pos[slot]);
}}

#define open  sim_open
#define close sim_close
#define read  sim_read
#include "{osd_hdr.as_posix()}"
#undef open
#undef close
#undef read

int main(void) {{
    (void)adc_driver;

    /* Unit test calibration and channel offset math */
    assert(hc16xx_adc_channel_offset(0) == 0);
    assert(hc16xx_adc_channel_offset(3) == 3);
    assert(hc16xx_adc_channel_offset(4) == 6);
    assert(hc16xx_adc_channel_offset(5) == 7);
    assert(hc16xx_adc_calibrate_byte(180, 241) == 180);
    assert(hc16xx_adc_calibrate_byte(150, 200) == 180);
    assert(hc16xx_adc_calibrate_byte(255, 100) == 255);
    assert(hc16xx_adc_calibrate_byte(123, 0) == 123);

    /* Probe driver: IIO + /dev/check_adc1 + /dev/check_adc5 */
    struct platform_device pdev;
    memset(&pdev, 0, sizeof(pdev));
    assert(adc_probe(&pdev) == 0);
    assert(registered_indio && !strcmp(registered_indio->name, "hc16xx-adc-ro"));
    assert(registered_indio->num_channels == 6);
    assert(misc_count == 2);
    assert(!strcmp(registered_misc[0]->name, "check_adc1"));
    assert(!strcmp(registered_misc[1]->name, "check_adc5"));
    assert(registered_misc[0]->mode == 0644);

    /* IIO raw reads preserve +0..+3, +6, +7 register layout */
    sar_regs[0] = 241; /* ch0 reference */
    sar_regs[1] = 180; /* ch1 battery */
    sar_regs[6] = 77;  /* ch4 */
    sar_regs[7] = 140; /* ch5 charge */
    int v = -1;
    assert(registered_indio->info->read_raw(registered_indio, &adc_channels[1], &v, NULL, IIO_CHAN_INFO_RAW) == IIO_VAL_INT && v == 180);
    assert(registered_indio->info->read_raw(registered_indio, &adc_channels[4], &v, NULL, IIO_CHAN_INFO_RAW) == IIO_VAL_INT && v == 77);
    assert(registered_indio->info->read_raw(registered_indio, &adc_channels[5], &v, NULL, IIO_CHAN_INFO_RAW) == IIO_VAL_INT && v == 140);
    assert(registered_indio->info->read_raw(registered_indio, &adc_channels[0], &v, NULL, 999L) == -EINVAL);

    /* Userspace keeps fds open across repeated polls without lseek (ppos > 0) */
    struct r36_battery_monitor mon;
    struct r36_battery_status st;
    r36_battery_monitor_init(&mon);
    assert(r36_battery_open(&mon) == 0);

    sar_regs[0] = 241; sar_regs[1] = 180; sar_regs[7] = 140;
    assert(r36_battery_poll(&mon, &st) == 0);
    assert(st.raw_battery == 180 && st.percent == 100 && st.raw_charge == 140 && st.charging == 1);
    assert(open_pos[0] == 1 && open_pos[1] == 1);

    /* Change SAR regs without closing or seeking fds: second poll reflects new calibrated readings */
    sar_regs[0] = 200;
    sar_regs[1] = 127; /* floor(127 * 241 / 200) = 153 -> 50% */
    sar_regs[7] = 0;   /* idle -> not charging */
    assert(r36_battery_poll(&mon, &st) == 0);
    assert(st.raw_battery == 153 && st.percent == 50 && st.raw_charge == 0 && st.charging == 0);
    assert(open_pos[0] == 2 && open_pos[1] == 2);

    /* Low battery and boundary points */
    sar_regs[0] = 241; sar_regs[1] = 64; sar_regs[7] = 63;
    assert(r36_battery_poll(&mon, &st) == 0);
    assert(st.percent == 0 && st.charging == 0);

    sar_regs[1] = 63; sar_regs[7] = 64;
    assert(r36_battery_poll(&mon, &st) == 0);
    assert(st.percent == 0 && st.charging == 1);

    assert(r36_battery_percent_from_adc(0) == 0);
    assert(r36_battery_percent_from_adc(108) == 24);
    assert(r36_battery_percent_from_adc(166) == 74);
    assert(r36_battery_percent_from_adc(255) == 100);

    r36_battery_close(&mon);
    assert(mon.bat_fd == -1 && mon.chg_fd == -1);

    for (int i = devm_action_count - 1; i >= 0; i--)
        devm_actions[i](devm_action_data[i]);
    assert(misc_count == 0);
    puts("HC16XX_ADC_RO_AND_OSD=PASS");
    return 0;
}}
'''
    )

    exe = tmp_path / "hc16xx_adc_ro_test.exe"
    subprocess.run(
        [
            "gcc",
            "-std=gnu11",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{inc_dir}",
            str(harness),
            "-o",
            str(exe),
        ],
        check=True,
        capture_output=True,
        timeout=20,
    )
    res = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=5)
    assert "HC16XX_ADC_RO_AND_OSD=PASS" in res.stdout

    if ZIG.exists():
        mips_probe = tmp_path / "adc_battery_osd_mips.c"
        mips_probe.write_text(
            f'#include "{osd_hdr.as_posix()}"\n'
            'int probe_osd(struct r36_battery_monitor *m, struct r36_battery_status *s) {\n'
            '    return r36_battery_open(m) == 0 ? r36_battery_poll(m, s) : -1;\n'
            '}\n'
        )
        mips_obj = tmp_path / "adc_battery_osd_mips.o"
        subprocess.run(
            [
                str(ZIG),
                "cc",
                "-target",
                "mipsel-linux.4.4-musleabi",
                "-march=mips32r2",
                "-msoft-float",
                "-Os",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-c",
                str(mips_probe),
                "-o",
                str(mips_obj),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        assert mips_obj.stat().st_size > 0
