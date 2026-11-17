/* SPDX-License-Identifier: MIT
 * Userspace helper for USB OTG role switching and external USB Wi-Fi /
 * Bluetooth adapter bring-up diagnostics on Linux 7.2.
 */
#ifndef R36_USB_OTG_WIFI_BT_PROBE_H
#define R36_USB_OTG_WIFI_BT_PROBE_H

#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#ifndef R36_OTG_PROBE_MOCK
#include <fcntl.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <unistd.h>
#endif

#ifndef F_OK
#define F_OK 0
#endif

#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif

#define R36_USB0_ROLE_SWITCH_PATH "/sys/class/usb_role/18844000.usb-role-switch/role"
#define R36_USB0_MUSB_MODE_PATH   "/sys/devices/platform/soc/18844000.usb/musb-hdrc.0.auto/mode"

#define R36_USB_CLASS_WIRELESS    0xE0u
#define R36_USB_SUBCLASS_RF       0x01u
#define R36_USB_PROTO_BT          0x01u

#define R36_HCI_CMD_PKT           0x01u
#define R36_HCI_EVT_PKT           0x04u
#define R36_HCI_EV_CMD_COMPLETE   0x0Eu
#define R36_HCI_OP_READ_BD_ADDR   0x1009u

enum r36_otg_dev_kind {
    R36_OTG_DEV_IGNORE = 0,
    R36_OTG_DEV_UNKNOWN = 1,
    R36_OTG_DEV_WIFI = 2,
    R36_OTG_DEV_BLUETOOTH = 3
};

struct r36_wifi_probe_status {
    int sysfs_wireless_found;
    int brought_up;
    int last_errno;
    char mac[24];
};

static inline void r36_trim_right(char *s)
{
    size_t n;
    if (!s) return;
    n = strlen(s);
    while (n > 0u && (s[n - 1u] == '\n' || s[n - 1u] == '\r' || s[n - 1u] == ' ' || s[n - 1u] == '\t'))
        s[--n] = '\0';
}

static inline int r36_otg_set_role(const char *role_path, const char *role)
{
    char wbuf[32];
    char rbuf[64];
    int fd, wlen;
    ssize_t n;
    size_t rpos = 0;

    if (!role_path || !role ||
        (strcmp(role, "host") != 0 && strcmp(role, "peripheral") != 0 && strcmp(role, "device") != 0)) {
        errno = EINVAL;
        return -1;
    }

    wlen = snprintf(wbuf, sizeof(wbuf), "%s\n", role);
    if (wlen <= 0 || (size_t)wlen >= sizeof(wbuf)) {
        errno = EINVAL;
        return -1;
    }

    fd = open(role_path, O_WRONLY | O_TRUNC | O_CLOEXEC);
    if (fd < 0)
        return -1;
    n = write(fd, wbuf, (size_t)wlen);
    if (n != (ssize_t)wlen) {
        int saved = (n < 0) ? errno : EIO;
        close(fd);
        errno = saved;
        return -1;
    }
    close(fd);

    fd = open(role_path, O_RDONLY | O_CLOEXEC);
    if (fd < 0)
        return -1;
    while (rpos + 1u < sizeof(rbuf)) {
        n = read(fd, rbuf + rpos, sizeof(rbuf) - 1u - rpos);
        if (n < 0 && errno == EINTR)
            continue;
        if (n <= 0)
            break;
        rpos += (size_t)n;
    }
    close(fd);
    rbuf[rpos] = '\0';
    r36_trim_right(rbuf);

    if (strcmp(rbuf, role) != 0) {
        errno = EIO;
        return -1;
    }
    return 0;
}

static inline enum r36_otg_dev_kind r36_otg_classify_usb_adapter(
    uint16_t vid, uint16_t pid,
    uint8_t dev_class, uint8_t dev_subclass, uint8_t dev_proto,
    uint8_t if_class, uint8_t if_subclass, uint8_t if_proto,
    int has_wireless_net)
{
    int bt_if_class = (dev_class == R36_USB_CLASS_WIRELESS &&
                       dev_subclass == R36_USB_SUBCLASS_RF &&
                       dev_proto == R36_USB_PROTO_BT) ||
                      (if_class == R36_USB_CLASS_WIRELESS &&
                       if_subclass == R36_USB_SUBCLASS_RF &&
                       if_proto == R36_USB_PROTO_BT);
    int vendor_bt_proto = (dev_class == 0xFFu && dev_subclass == 0x01u && dev_proto == 0x01u) ||
                          (if_class == 0xFFu && if_subclass == 0x01u && if_proto == 0x01u);

    if (vid == 0x1d6bu)
        return R36_OTG_DEV_IGNORE;

    if (bt_if_class)
        return R36_OTG_DEV_BLUETOOTH;

    if ((vid == 0x0a12u && pid == 0x0001u) ||
        (vid == 0x0bdau && (pid == 0x8771u || pid == 0xb711u || pid == 0x8761u)) ||
        (vid == 0x0a5cu && pid == 0x21e8u) ||
        (vid == 0x0e8du && pid == 0x7612u && vendor_bt_proto)) {
        return R36_OTG_DEV_BLUETOOTH;
    }

    if (has_wireless_net)
        return R36_OTG_DEV_WIFI;

    if ((vid == 0x0bdau && (pid == 0x8179u || pid == 0xf179u || pid == 0xb812u || pid == 0xc811u)) ||
        (vid == 0x148fu && (pid == 0x7601u || pid == 0x5370u)) ||
        (vid == 0x0e8du && pid == 0x7610u) ||
        (vid == 0x0cf3u && pid == 0x9271u)) {
        return R36_OTG_DEV_WIFI;
    }

    return R36_OTG_DEV_UNKNOWN;
}

static inline void r36_bt_hci_build_read_bd_addr_cmd(uint8_t out_pkt[4])
{
    if (!out_pkt) return;
    out_pkt[0] = R36_HCI_CMD_PKT;
    out_pkt[1] = (uint8_t)(R36_HCI_OP_READ_BD_ADDR & 0xFFu);
    out_pkt[2] = (uint8_t)((R36_HCI_OP_READ_BD_ADDR >> 8) & 0xFFu);
    out_pkt[3] = 0x00u;
}

static inline int r36_bt_hci_parse_bd_addr_evt(const uint8_t *pkt, size_t len,
                                               char bdaddr_str[18])
{
    uint16_t opcode;

    if (!pkt || !bdaddr_str || len < 13u) {
        errno = EINVAL;
        return -1;
    }
    if (pkt[0] != R36_HCI_EVT_PKT || pkt[1] != R36_HCI_EV_CMD_COMPLETE || pkt[2] < 10u) {
        errno = EPROTO;
        return -1;
    }
    if (len < (size_t)pkt[2] + 3u) {
        errno = EINVAL;
        return -1;
    }
    opcode = (uint16_t)pkt[4] | ((uint16_t)pkt[5] << 8);
    if (opcode != R36_HCI_OP_READ_BD_ADDR || pkt[6] != 0x00u) {
        errno = EIO;
        return -1;
    }
    snprintf(bdaddr_str, 18u, "%02X:%02X:%02X:%02X:%02X:%02X",
             pkt[12], pkt[11], pkt[10], pkt[9], pkt[8], pkt[7]);
    return 0;
}

static inline int r36_wifi_check_sysfs_and_bring_up(const char *sys_net_root,
                                                   const char *ifname,
                                                   int sock_fd,
                                                   struct r36_wifi_probe_status *out)
{
    char path[512];
    struct ifreq ifr;
    int fd;

    if (!out) {
        errno = EINVAL;
        return -1;
    }
    memset(out, 0, sizeof(*out));
    if (!sys_net_root || !ifname || !ifname[0] || sock_fd < 0) {
        errno = EINVAL;
        out->last_errno = EINVAL;
        return -1;
    }

    snprintf(path, sizeof(path), "%s/%s/wireless", sys_net_root, ifname);
    if (access(path, F_OK) != 0) {
        snprintf(path, sizeof(path), "%s/%s/phy80211", sys_net_root, ifname);
        if (access(path, F_OK) != 0) {
            errno = ENODEV;
            out->last_errno = ENODEV;
            return -1;
        }
    }
    out->sysfs_wireless_found = 1;

    snprintf(path, sizeof(path), "%s/%s/address", sys_net_root, ifname);
    fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd >= 0) {
        ssize_t n = read(fd, out->mac, sizeof(out->mac) - 1u);
        close(fd);
        if (n > 0) {
            out->mac[n] = '\0';
            r36_trim_right(out->mac);
        }
    }

    memset(&ifr, 0, sizeof(ifr));
    snprintf(ifr.ifr_name, sizeof(ifr.ifr_name), "%s", ifname);
    if (ioctl(sock_fd, SIOCGIFFLAGS, &ifr) != 0) {
        out->last_errno = errno;
        return -1;
    }
    ifr.ifr_flags = (short)(ifr.ifr_flags | IFF_UP);
    if (ioctl(sock_fd, SIOCSIFFLAGS, &ifr) != 0) {
        out->last_errno = errno;
        return -1;
    }
    out->brought_up = 1;
    out->last_errno = 0;
    return 0;
}

#endif
