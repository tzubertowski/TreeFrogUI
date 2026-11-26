"""Verify USB OTG role switch, BT HCI READ_BD_ADDR, Wi-Fi wlan0 bring-up, and kernel build config."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ZIG = Path(r"C:\Users\palpa\Tools\zig-x86_64-windows-0.17.0\zig.exe")


def test_otg_wifi_bt_dts_and_build_config():
    dts = (ROOT / "scripts/kernel_lab/r36-usb-otg.dts").read_text()
    assert '&usb0 { status = "okay"; dr_mode = "otg"; };' in dts
    assert '&usb1 { status = "okay"; dr_mode = "host"; };' in dts

    build = (ROOT / "scripts/peripheral_lab/vm_build_kernel.sh").read_text()
    for token in (
        "R36_OTG_WIFI_BT",
        "--enable USB_MUSB_DUAL_ROLE",
        "--enable USB_ROLE_SWITCH",
        "--module CFG80211 --module MAC80211",
        "--module RTL8XXXU",
        "--module RTW88_8821CU",
        "--module MT7601U",
        "--module RT2800USB",
        "--module ATH9K_HTC",
        "--module BT",
        "--module BT_HCIBTUSB",
        "INSTALL_MOD_STRIP=1 modules_install",
    ):
        assert token in build, token

    starter = (ROOT / "scripts/peripheral_lab/start_vm_kernel_build.py").read_text()
    assert "--otg-wifi-bt" in starter
    assert "R36_OTG_WIFI_BT=" in starter


def test_otg_role_bt_hci_and_wifi_sysfs_c_harness(tmp_path):
    hdr = ROOT / "scripts/peripheral_lab/usb_otg_wifi_bt_probe.h"
    sys_net = tmp_path / "sys_class_net"
    wlan0 = sys_net / "wlan0"
    (wlan0 / "wireless").mkdir(parents=True)
    (wlan0 / "address").write_text("02:11:22:33:44:55\n")
    (sys_net / "eth0").mkdir(parents=True)
    (sys_net / "eth0" / "address").write_text("02:aa:bb:cc:dd:ee\n")

    role_file = tmp_path / "usb_role"
    role_file.write_text("peripheral\n")

    harness = tmp_path / "otg_wifi_bt_test.c"
    harness.write_text(
        f'''
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int host_open(const char *p, int flags) {{ return open(p, flags); }}
static int host_close(int fd) {{ return close(fd); }}
static ssize_t host_read(int fd, void *buf, size_t count) {{ return read(fd, buf, count); }}
static ssize_t host_write(int fd, const void *buf, size_t count) {{ return write(fd, buf, count); }}
static int host_access(const char *p, int mode) {{ return access(p, mode); }}

#define R36_OTG_PROBE_MOCK 1
#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif
#ifndef EPROTO
#define EPROTO 71
#endif

#define SIOCGIFFLAGS 0x8913u
#define SIOCSIFFLAGS 0x8914u
#define IFF_UP       0x1

struct ifreq {{
    char ifr_name[16];
    short ifr_flags;
}};

static short mock_flags = 0x1002; /* IFF_BROADCAST | IFF_MULTICAST, down */
static int inject_fw_missing = 0;

static int mock_ioctl(int fd, unsigned long req, void *arg) {{
    struct ifreq *ifr = (struct ifreq *)arg;
    assert(fd == 77);
    assert(!strcmp(ifr->ifr_name, "wlan0"));
    if (req == SIOCGIFFLAGS) {{
        ifr->ifr_flags = mock_flags;
        return 0;
    }}
    if (req == SIOCSIFFLAGS) {{
        if (inject_fw_missing) {{
            errno = ENOENT;
            return -1;
        }}
        mock_flags = ifr->ifr_flags;
        return 0;
    }}
    errno = EINVAL;
    return -1;
}}

#define open   host_open
#define close  host_close
#define read   host_read
#define write  host_write
#define access host_access
#define ioctl  mock_ioctl
#include "{hdr.as_posix()}"
#undef open
#undef close
#undef read
#undef write
#undef access
#undef ioctl

int main(void) {{
    /* 1. OTG role switch write + readback verification (musb mode & usb_role_switch) */
    assert(r36_otg_set_role("{role_file.as_posix()}", "host") == 0);
    assert(r36_otg_set_role("{role_file.as_posix()}", "device") == 0);
    assert(r36_otg_set_role("{role_file.as_posix()}", "peripheral") == 0);
    assert(r36_otg_set_role("{role_file.as_posix()}", "invalid") == -1 && errno == EINVAL);

    /* 2. Adapter classification */
    assert(r36_otg_classify_usb_adapter(0x1d6bu, 0x0002u, 9, 0, 1, 9, 0, 0, 0) == R36_OTG_DEV_IGNORE);
    assert(r36_otg_classify_usb_adapter(0x0a12u, 0x0001u, 0xE0u, 1, 1, 0xE0u, 1, 1, 0) == R36_OTG_DEV_BLUETOOTH);
    assert(r36_otg_classify_usb_adapter(0x0bdau, 0x8771u, 0xFFu, 1, 1, 0xE0u, 1, 1, 0) == R36_OTG_DEV_BLUETOOTH);
    assert(r36_otg_classify_usb_adapter(0x0bdau, 0xf179u, 0, 0, 0, 0xFFu, 0xFFu, 0xFFu, 1) == R36_OTG_DEV_WIFI);
    assert(r36_otg_classify_usb_adapter(0x148fu, 0x7601u, 0, 0, 0, 0xFFu, 0xFFu, 0xFFu, 0) == R36_OTG_DEV_WIFI);
    assert(r36_otg_classify_usb_adapter(0x046du, 0xc31cu, 0, 0, 0, 3, 1, 1, 0) == R36_OTG_DEV_UNKNOWN);

    /* 3. Bluetooth HCI READ_BD_ADDR command & CMD_COMPLETE event */
    uint8_t cmd[4] = {{0}};
    r36_bt_hci_build_read_bd_addr_cmd(cmd);
    assert(cmd[0] == 0x01u && cmd[1] == 0x09u && cmd[2] == 0x10u && cmd[3] == 0x00u);

    const uint8_t evt_ok[13] = {{
        0x04u, 0x0Eu, 0x0Au, 0x01u, 0x09u, 0x10u, 0x00u,
        0x66u, 0x55u, 0x44u, 0x33u, 0x22u, 0x11u
    }};
    char mac[18] = {{0}};
    assert(r36_bt_hci_parse_bd_addr_evt(evt_ok, sizeof(evt_ok), mac) == 0);
    assert(!strcmp(mac, "11:22:33:44:55:66"));

    const uint8_t evt_err[13] = {{
        0x04u, 0x0Eu, 0x0Au, 0x01u, 0x09u, 0x10u, 0x12u,
        0, 0, 0, 0, 0, 0
    }};
    assert(r36_bt_hci_parse_bd_addr_evt(evt_err, sizeof(evt_err), mac) == -1);
    assert(r36_bt_hci_parse_bd_addr_evt(evt_ok, 8u, mac) == -1);

    /* 4. Wi-Fi sysfs + IFF_UP + missing firmware negative check */
    struct r36_wifi_probe_status wst;
    assert(r36_wifi_check_sysfs_and_bring_up("{sys_net.as_posix()}", "eth0", 77, &wst) == -1);
    assert(!wst.sysfs_wireless_found && wst.last_errno == ENODEV);

    inject_fw_missing = 1;
    assert(r36_wifi_check_sysfs_and_bring_up("{sys_net.as_posix()}", "wlan0", 77, &wst) == -1);
    assert(wst.sysfs_wireless_found && !wst.brought_up && wst.last_errno == ENOENT);
    assert(!strcmp(wst.mac, "02:11:22:33:44:55"));

    inject_fw_missing = 0;
    assert(r36_wifi_check_sysfs_and_bring_up("{sys_net.as_posix()}", "wlan0", 77, &wst) == 0);
    assert(wst.sysfs_wireless_found && wst.brought_up && wst.last_errno == 0);
    assert((mock_flags & IFF_UP) != 0);

    puts("USB_OTG_WIFI_BT_PROBE=PASS");
    return 0;
}}
'''
    )

    exe = tmp_path / "otg_wifi_bt_test.exe"
    subprocess.run(
        ["gcc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", str(harness), "-o", str(exe)],
        check=True,
        capture_output=True,
        timeout=20,
    )
    res = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=5)
    assert "USB_OTG_WIFI_BT_PROBE=PASS" in res.stdout

    if ZIG.exists():
        mips_src = tmp_path / "otg_probe_mips.c"
        mips_src.write_text(
            f'#include "{hdr.as_posix()}"\n'
            'int probe_otg_entry(const char *role_path, int sock_fd, struct r36_wifi_probe_status *w) {\n'
            '    uint8_t cmd[4];\n'
            '    r36_bt_hci_build_read_bd_addr_cmd(cmd);\n'
            '    return r36_otg_set_role(role_path, "host") +\n'
            '           r36_wifi_check_sysfs_and_bring_up("/sys/class/net", "wlan0", sock_fd, w) +\n'
            '           (int)cmd[1];\n'
            '}\n'
        )
        mips_obj = tmp_path / "otg_probe_mips.o"
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
                str(mips_src),
                "-o",
                str(mips_obj),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        assert mips_obj.stat().st_size > 0
