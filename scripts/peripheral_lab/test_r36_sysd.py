"""Tests for unified r36_sysd peripheral daemon (keys, PA/HP, backlight, ADC, clean shutdown)."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ZIG = Path(r"C:\Users\palpa\Tools\zig-x86_64-windows-0.17.0\zig.exe")


def test_r36_sysd_full_loop_and_mips_compile(tmp_path):
    sysd = ROOT / "scripts/peripheral_lab/r36_sysd.c"
    harness = tmp_path / "sysd_test.c"
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

#define R36_SYSD_MOCK 1
#define R36_SYSD_LIBRARY_ONLY 1

#define FD_EVDEV   10
#define FD_BL_MAX  11
#define FD_BL_CUR  12
#define FD_GPIO15  13
#define FD_GPIO19  14
#define FD_ADC1    15
#define FD_ADC5    16
#define FD_STATUS  17
#define FD_CONF    18

static int bl_raw_written = -1;
static int gpio15_level = 1; /* active-low HP unplugged */
static int gpio19_amp_written = -1;
static uint8_t adc1_val = 153; /* 50% */
static uint8_t adc5_val = 140; /* charging */
static int swapoff_called, umount_called, reboot_called, sync_called;
static unsigned int reboot_cmd_seen;
static char status_buf[128];
static char conf_buf[128] = "volume_pct=60\\nbrightness_pct=80\\n";

struct r36_ev_queue_item {{ uint16_t type; uint16_t code; int32_t value; }};
static struct r36_ev_queue_item ev_q[32];
static int ev_head, ev_tail;

static void push_key(uint16_t code, int32_t value) {{
    ev_q[ev_tail].type = 1;
    ev_q[ev_tail].code = code;
    ev_q[ev_tail].value = value;
    ev_tail++;
}}

static int mock_open(const char *path, int flags, ...) {{
    (void)flags;
    if (!strcmp(path, "/dev/input/event1")) return FD_EVDEV;
    if (!strcmp(path, "/sys/class/backlight/backlight/max_brightness")) return FD_BL_MAX;
    if (!strcmp(path, "/sys/class/backlight/backlight/brightness")) return FD_BL_CUR;
    if (!strcmp(path, "/sys/class/gpio/gpio15/value")) return FD_GPIO15;
    if (!strcmp(path, "/sys/class/gpio/gpio19/value")) return FD_GPIO19;
    if (!strcmp(path, "/dev/check_adc1")) return FD_ADC1;
    if (!strcmp(path, "/dev/check_adc5")) return FD_ADC5;
    if (!strcmp(path, "/tmp/r36-battery.status")) return FD_STATUS;
    if (!strcmp(path, "/mnt/sdcard/cubegm/r36_sysd.conf")) return FD_CONF;
    errno = ENOENT;
    return -1;
}}

static int mock_close(int fd) {{ (void)fd; return 0; }}

static ssize_t mock_read(int fd, void *buf, size_t count) {{
    if (fd == FD_BL_MAX) {{
        const char *s = "200\\n";
        size_t n = strlen(s);
        memcpy(buf, s, n);
        return (ssize_t)n;
    }}
    if (fd == FD_GPIO15) {{
        char *c = (char *)buf;
        c[0] = gpio15_level ? '1' : '0';
        c[1] = '\\n';
        return 2;
    }}
    if (fd == FD_ADC1 && count >= 1) {{ *(uint8_t *)buf = adc1_val; return 1; }}
    if (fd == FD_ADC5 && count >= 1) {{ *(uint8_t *)buf = adc5_val; return 1; }}
    if (fd == FD_CONF) {{
        size_t n = strlen(conf_buf);
        if (n > count) n = count;
        memcpy(buf, conf_buf, n);
        return (ssize_t)n;
    }}
    if (fd == FD_EVDEV) {{
        if (ev_head >= ev_tail) {{ errno = EAGAIN; return -1; }}
        assert(count == 16 || count >= 16);
        struct {{ long tv_sec; long tv_usec; uint16_t type; uint16_t code; int32_t value; }} ev = {{
            0, 0, ev_q[ev_head].type, ev_q[ev_head].code, ev_q[ev_head].value
        }};
        ev_head++;
        memcpy(buf, &ev, sizeof(ev));
        return (ssize_t)sizeof(ev);
    }}
    return -1;
}}

static ssize_t mock_write(int fd, const void *buf, size_t count) {{
    char tmp[128];
    size_t copy = count < sizeof(tmp) - 1 ? count : sizeof(tmp) - 1;
    memcpy(tmp, buf, copy);
    tmp[copy] = '\\0';
    if (fd == FD_BL_CUR) {{ bl_raw_written = atoi(tmp); return (ssize_t)count; }}
    if (fd == FD_GPIO19) {{ gpio19_amp_written = atoi(tmp); return (ssize_t)count; }}
    if (fd == FD_STATUS) {{ memcpy(status_buf, tmp, copy + 1); return (ssize_t)count; }}
    if (fd == FD_CONF) {{ memcpy(conf_buf, tmp, copy + 1); return (ssize_t)count; }}
    return -1;
}}

static void mock_sync(void) {{ sync_called++; }}
static int mock_swapoff(const char *p) {{ assert(!strcmp(p, "/mnt/sdcard/cubegm/pagefile.sys")); swapoff_called++; return 0; }}
static int mock_umount(const char *p) {{ assert(!strcmp(p, "/mnt/sdcard")); umount_called++; return 0; }}
static int mock_reboot(unsigned int cmd) {{ reboot_cmd_seen = cmd; reboot_called++; return 0; }}

#define open    mock_open
#define close   mock_close
#define read    mock_read
#define write   mock_write
#define sync    mock_sync
#define swapoff mock_swapoff
#define umount  mock_umount
#define reboot  mock_reboot

#include "{sysd.as_posix()}"

#undef open
#undef close
#undef read
#undef write
#undef sync
#undef swapoff
#undef umount
#undef reboot

int main(void) {{
    struct r36_sysd_state st;
    assert(r36_sysd_init(&st, NULL) == 0);
    /* Initial: volume 60, brightness 80% of max 200 -> 160, HP unplugged -> PA 1 */
    assert(st.max_brightness == 200);
    assert(bl_raw_written == 160);
    assert(gpio19_amp_written == 1);

    /* Step at t=100ms polls battery (50%, charging=1) */
    assert(r36_sysd_step(&st, 100) == 0);
    assert(strstr(status_buf, "percent=50 charging=1") != NULL);

    /* FN + VOL_DOWN -> brightness 70% -> 140 */
    push_key(R36_DIRECT_CODE_FN, 1);
    push_key(R36_DIRECT_CODE_VOL_DOWN, 1);
    push_key(R36_DIRECT_CODE_FN, 0);
    assert(r36_sysd_step(&st, 200) == 0);
    assert(st.keys.brightness_pct == 70 && bl_raw_written == 140);
    assert(strstr(conf_buf, "brightness_pct=70") != NULL);

    /* Headphone inserted (GPIO15 -> 0) disables speaker PA (GPIO19 -> 0) */
    gpio15_level = 0;
    assert(r36_sysd_step(&st, 300) == 0);
    assert(gpio19_amp_written == 0);

    /* Unplug headphone restores PA -> 1 */
    gpio15_level = 1;
    assert(r36_sysd_step(&st, 400) == 0);
    assert(gpio19_amp_written == 1);

    /* Short POWER press (<1500ms) -> sleep toggles PA=0, backlight=0; second wakes */
    push_key(R36_DIRECT_CODE_POWER, 1);
    assert(r36_sysd_step(&st, 1000) == 0);
    push_key(R36_DIRECT_CODE_POWER, 0);
    assert(r36_sysd_step(&st, 1500) == 0);
    assert(st.sleeping == 1 && gpio19_amp_written == 0 && bl_raw_written == 0);

    push_key(R36_DIRECT_CODE_POWER, 1);
    assert(r36_sysd_step(&st, 2000) == 0);
    push_key(R36_DIRECT_CODE_POWER, 0);
    assert(r36_sysd_step(&st, 2200) == 0);
    assert(st.sleeping == 0 && gpio19_amp_written == 1 && bl_raw_written == 140);

    /* Long POWER hold (>=1500ms) -> clean shutdown */
    push_key(R36_DIRECT_CODE_POWER, 1);
    assert(r36_sysd_step(&st, 6000) == 0);
    assert(r36_sysd_step(&st, 7500) == 1);
    assert(gpio19_amp_written == 0 && bl_raw_written == 0);
    assert(sync_called >= 2 && swapoff_called == 1 && umount_called == 1);
    assert(reboot_called == 1 && reboot_cmd_seen == RB_POWER_OFF);

    puts("R36_SYSD_TEST=PASS");
    return 0;
}}
'''
    )

    exe = tmp_path / "sysd_test.exe"
    subprocess.run(
        [
            "gcc",
            "-std=gnu11",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{(ROOT / 'scripts/peripheral_lab')}",
            str(harness),
            "-o",
            str(exe),
        ],
        check=True,
        capture_output=True,
        timeout=20,
    )
    res = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=5)
    assert "R36_SYSD_TEST=PASS" in res.stdout

    if ZIG.exists():
        mips_elf = tmp_path / "r36-sysd.elf"
        subprocess.run(
            [
                str(ZIG),
                "cc",
                "-target",
                "mipsel-linux.4.4-musleabi",
                "-march=mips32r2",
                "-msoft-float",
                "-static",
                "-Os",
                "-Wall",
                "-Wextra",
                "-Werror",
                str(sysd),
                "-o",
                str(mips_elf),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        assert mips_elf.stat().st_size > 0


def test_r36_sysd_idle_fade_screen_off_and_auto_poweroff(tmp_path):
    sysd = ROOT / "scripts/peripheral_lab/r36_sysd.c"
    harness = tmp_path / "sysd_idle_test.c"
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

#define R36_SYSD_MOCK 1
#define R36_SYSD_LIBRARY_ONLY 1

#define FD_EVDEV      10
#define FD_EVDEV_GAME 19
#define FD_BL_MAX     11
#define FD_BL_CUR     12
#define FD_GPIO15     13
#define FD_GPIO19     14
#define FD_ADC1       15
#define FD_ADC5       16
#define FD_STATUS     17
#define FD_CONF       18

static int bl_raw_written = -1;
static int gpio15_level = 1;
static int gpio19_amp_written = -1;
static int swapoff_called, umount_called, reboot_called, sync_called;
static unsigned int reboot_cmd_seen;
static char conf_buf[256] =
    "volume_pct=60\\nbrightness_pct=100\\nscreen_off_sec=20\\nauto_poweroff_sec=40\\n";

struct r36_ev_queue_item {{ int fd; uint16_t type; uint16_t code; int32_t value; }};
static struct r36_ev_queue_item ev_q[32];
static int ev_head, ev_tail;

static void push_ev(int fd, uint16_t code, int32_t value) {{
    ev_q[ev_tail].fd = fd;
    ev_q[ev_tail].type = 1;
    ev_q[ev_tail].code = code;
    ev_q[ev_tail].value = value;
    ev_tail++;
}}

static int mock_open(const char *path, int flags, ...) {{
    (void)flags;
    if (!strcmp(path, "/dev/input/event1")) return FD_EVDEV;
    if (!strcmp(path, "/dev/input/event0")) return FD_EVDEV_GAME;
    if (!strcmp(path, "/sys/class/backlight/backlight/max_brightness")) return FD_BL_MAX;
    if (!strcmp(path, "/sys/class/backlight/backlight/brightness")) return FD_BL_CUR;
    if (!strcmp(path, "/sys/class/gpio/gpio15/value")) return FD_GPIO15;
    if (!strcmp(path, "/sys/class/gpio/gpio19/value")) return FD_GPIO19;
    if (!strcmp(path, "/tmp/r36-battery.status")) return FD_STATUS;
    if (!strcmp(path, "/mnt/sdcard/cubegm/r36_sysd.conf")) return FD_CONF;
    errno = ENOENT;
    return -1;
}}

static int mock_close(int fd) {{ (void)fd; return 0; }}

static ssize_t mock_read(int fd, void *buf, size_t count) {{
    if (fd == FD_BL_MAX) {{
        const char *s = "200\\n";
        size_t n = strlen(s);
        memcpy(buf, s, n);
        return (ssize_t)n;
    }}
    if (fd == FD_GPIO15) {{
        char c[4];
        int n = snprintf(c, sizeof(c), "%d\\n", gpio15_level);
        memcpy(buf, c, (size_t)n);
        return (ssize_t)n;
    }}
    if (fd == FD_CONF) {{
        size_t n = strlen(conf_buf);
        if (n >= count) n = count - 1;
        memcpy(buf, conf_buf, n);
        return (ssize_t)n;
    }}
    if (fd == FD_EVDEV || fd == FD_EVDEV_GAME) {{
        int i;
        for (i = ev_head; i < ev_tail; i++) {{
            if (ev_q[i].fd == fd) {{
                struct {{
                    long tv_sec;
                    long tv_usec;
                    uint16_t type;
                    uint16_t code;
                    int32_t value;
                }} ev = {{ 0, 0, ev_q[i].type, ev_q[i].code, ev_q[i].value }};
                ev_q[i].fd = -1;
                while (ev_head < ev_tail && ev_q[ev_head].fd == -1) ev_head++;
                if (count < sizeof(ev)) {{ errno = EINVAL; return -1; }}
                memcpy(buf, &ev, sizeof(ev));
                return (ssize_t)sizeof(ev);
            }}
        }}
        errno = EAGAIN;
        return -1;
    }}
    errno = ENOENT;
    return -1;
}}

static ssize_t mock_write(int fd, const void *buf, size_t count) {{
    char tmp[256];
    size_t n = count < sizeof(tmp) - 1 ? count : sizeof(tmp) - 1;
    memcpy(tmp, buf, n);
    tmp[n] = '\\0';
    if (fd == FD_BL_CUR) {{ bl_raw_written = atoi(tmp); return (ssize_t)count; }}
    if (fd == FD_GPIO19) {{ gpio19_amp_written = atoi(tmp); return (ssize_t)count; }}
    if (fd == FD_CONF) {{ snprintf(conf_buf, sizeof(conf_buf), "%s", tmp); return (ssize_t)count; }}
    return (ssize_t)count;
}}

static void mock_sync(void) {{ sync_called++; }}
static int mock_swapoff(const char *p) {{ (void)p; swapoff_called++; return 0; }}
static int mock_umount(const char *p) {{ (void)p; umount_called++; return 0; }}
static int mock_reboot(unsigned int cmd) {{ reboot_called++; reboot_cmd_seen = cmd; return 0; }}

#define open mock_open
#define close mock_close
#define read mock_read
#define write mock_write
#define sync mock_sync
#define swapoff mock_swapoff
#define umount mock_umount
#define reboot mock_reboot
#include "{sysd.as_posix()}"
#undef open
#undef close
#undef read
#undef write
#undef sync
#undef swapoff
#undef umount
#undef reboot

int main(void) {{
    struct r36_sysd_state st;
    assert(r36_sysd_init(&st, NULL) == 0);
    assert(st.conf.screen_off_sec == 20 && st.conf.auto_poweroff_sec == 40);
    assert(bl_raw_written == 200);

    /* Initial activity at t=1000ms */
    assert(r36_sysd_step(&st, 1000) == 0);
    assert(st.dim_active == 0 && bl_raw_written == 200);

    /* At t=15000ms (14s idle < 15s fade start): still full brightness */
    assert(r36_sysd_step(&st, 15000) == 0);
    assert(st.dim_active == 0 && bl_raw_written == 200);

    /* At t=18500ms (17.5s idle, 2.5s before 20s screen_off): ~50% dim */
    assert(r36_sysd_step(&st, 18500) == 0);
    assert(st.dim_active == 1 && st.dim_pct == 50 && bl_raw_written == 100);

    /* User presses button on game evdev (event0) during fade -> brightness immediately restored */
    push_ev(FD_EVDEV_GAME, 304, 1);
    assert(r36_sysd_step(&st, 19000) == 0);
    assert(st.dim_active == 0 && st.sleeping == 0 && bl_raw_written == 200);

    /* Let it reach full screen_off at 19000 + 20000 = 39000ms */
    assert(r36_sysd_step(&st, 36500) == 0);
    assert(st.dim_active == 1 && bl_raw_written == 100);
    assert(r36_sysd_step(&st, 39000) == 0);
    assert(st.sleeping == 1 && st.idle_screen_off == 1 && bl_raw_written == 0 && gpio19_amp_written == 0);

    /* User input wakes screen from idle screen-off */
    push_ev(FD_EVDEV_GAME, 304, 1);
    assert(r36_sysd_step(&st, 40000) == 0);
    assert(st.sleeping == 0 && st.idle_screen_off == 0 && bl_raw_written == 200 && gpio19_amp_written == 1);

    /* Auto poweroff after 40s idle (40000 + 40000 = 80000ms) */
    assert(r36_sysd_step(&st, 80000) == 1);
    assert(reboot_called == 1 && reboot_cmd_seen == RB_POWER_OFF);
    assert(swapoff_called == 1 && umount_called == 1);

    /* Disabled timers (0) never dim or poweroff */
    reboot_called = 0;
    snprintf(conf_buf, sizeof(conf_buf),
             "volume_pct=60\\nbrightness_pct=80\\nscreen_off_sec=0\\nauto_poweroff_sec=0\\n");
    assert(r36_sysd_init(&st, NULL) == 0);
    assert(r36_sysd_step(&st, 1000) == 0);
    assert(r36_sysd_step(&st, 5000000) == 0);
    assert(st.dim_active == 0 && st.sleeping == 0 && reboot_called == 0);

    puts("R36_SYSD_IDLE_TEST=PASS");
    return 0;
}}
'''
    )
    exe = tmp_path / "sysd_idle_test.exe"
    subprocess.run(
        [
            "gcc",
            "-std=gnu11",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{(ROOT / 'scripts/peripheral_lab')}",
            str(harness),
            "-o",
            str(exe),
        ],
        check=True,
        capture_output=True,
        timeout=20,
    )
    res = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=5)
    assert "R36_SYSD_IDLE_TEST=PASS" in res.stdout


def test_r36_power_settings_ui_and_mips_compile(tmp_path):
    settings_c = ROOT / "scripts/peripheral_lab/r36_power_settings.c"
    harness = tmp_path / "settings_test.c"
    harness.write_text(
        f'''
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define R36_POWER_SETTINGS_MOCK 1
#define R36_SYSD_MOCK 1

static char conf_buf[256] =
    "volume_pct=60\\nbrightness_pct=80\\nscreen_off_sec=120\\nauto_poweroff_sec=600\\n";

static int mock_open(const char *path, int flags, ...) {{
    (void)flags;
    if (!strcmp(path, "/mnt/sdcard/cubegm/r36_sysd.conf")) return 20;
    errno = ENOENT;
    return -1;
}}
static int mock_close(int fd) {{ (void)fd; return 0; }}
static ssize_t mock_read(int fd, void *buf, size_t count) {{
    if (fd == 20) {{
        size_t n = strlen(conf_buf);
        if (n >= count) n = count - 1;
        memcpy(buf, conf_buf, n);
        return (ssize_t)n;
    }}
    return -1;
}}
static ssize_t mock_write(int fd, const void *buf, size_t count) {{
    if (fd == 20) {{
        size_t n = count < sizeof(conf_buf) - 1 ? count : sizeof(conf_buf) - 1;
        memcpy(conf_buf, buf, n);
        conf_buf[n] = '\\0';
        return (ssize_t)count;
    }}
    return -1;
}}

static void *mock_mmap(void *a, size_t l, int p, int f, int fd, long o) {{
    (void)a; (void)l; (void)p; (void)f; (void)fd; (void)o;
    return (void *)(-1);
}}
static int mock_munmap(void *a, size_t l) {{ (void)a; (void)l; return 0; }}

#define open mock_open
#define close mock_close
#define read mock_read
#define write mock_write
#define mmap mock_mmap
#define munmap mock_munmap
#include "{settings_c.as_posix()}"
#undef open
#undef close
#undef read
#undef write
#undef mmap
#undef munmap

int main(void) {{
    static uint16_t fb[R36_FB_WIDTH * R36_FB_HEIGHT];
    struct r36_power_ui_state ui;

    r36_power_ui_init(&ui, NULL);
    assert(ui.conf.screen_off_sec == 120);
    assert(ui.conf.auto_poweroff_sec == 600);

    /* Row 0 (screen_off): RIGHT -> 300s (5M) */
    assert(r36_power_ui_step_key(&ui, KEY_RIGHT, 1) == R36_UI_CONTINUE);
    assert(ui.conf.screen_off_sec == 300);

    /* Row 1 (auto_poweroff): DOWN then LEFT -> 300s, LEFT again -> OFF (0) */
    assert(r36_power_ui_step_key(&ui, KEY_DOWN, 1) == R36_UI_CONTINUE);
    assert(r36_power_ui_step_key(&ui, KEY_LEFT, 1) == R36_UI_CONTINUE);
    assert(ui.conf.auto_poweroff_sec == 300);
    assert(r36_power_ui_step_key(&ui, KEY_LEFT, 1) == R36_UI_CONTINUE);
    assert(ui.conf.auto_poweroff_sec == 0);

    /* Render framebuffer without crashing */
    r36_power_ui_render(fb, &ui);
    assert(fb[0] == 0x0842u);

    /* Save and exit */
    assert(r36_power_ui_step_key(&ui, BTN_SOUTH, 1) == R36_UI_SAVED_EXIT);
    assert(strstr(conf_buf, "screen_off_sec=300") != NULL);
    assert(strstr(conf_buf, "auto_poweroff_sec=0") != NULL);

    puts("R36_POWER_SETTINGS_TEST=PASS");
    return 0;
}}
'''
    )
    exe = tmp_path / "settings_test.exe"
    subprocess.run(
        [
            "gcc",
            "-std=gnu11",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{(ROOT / 'scripts/peripheral_lab')}",
            str(harness),
            "-o",
            str(exe),
        ],
        check=True,
        capture_output=True,
        timeout=20,
    )
    res = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=5)
    assert "R36_POWER_SETTINGS_TEST=PASS" in res.stdout

    if ZIG.exists():
        mips_elf = tmp_path / "r36-power-settings.elf"
        subprocess.run(
            [
                str(ZIG),
                "cc",
                "-target",
                "mipsel-linux.4.4-musleabi",
                "-march=mips32r2",
                "-msoft-float",
                "-static",
                "-Os",
                "-Wall",
                "-Wextra",
                "-Werror",
                str(settings_c),
                "-o",
                str(mips_elf),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        assert mips_elf.stat().st_size > 0
