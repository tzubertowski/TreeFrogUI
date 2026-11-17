/* SPDX-License-Identifier: MIT */
#ifndef R36_USB_FFS_MTP_ADB_H
#define R36_USB_FFS_MTP_ADB_H

#include <errno.h>
#include <stdint.h>
#include <string.h>

/* Linux FunctionFS v2 wire structures (<linux/usb/functionfs.h>, little-endian)
 * and ADB transport protocol for composite MTP + ADB over HC16xx MUSB USB0.
 *
 * Endpoint budget against drivers/usb/musb/hc16xx.c (hc16xx_fifo_cfg: 5 TX + 5 RX):
 *   ffs.mtp: 2 TX (ep1 bulk IN, ep3 int IN) + 1 RX (ep2 bulk OUT)
 *   ffs.adb: 1 TX (ep1 bulk IN)             + 1 RX (ep2 bulk OUT)
 *   Total  : 3 TX + 2 RX <= 5 TX + 5 RX hardware FIFOs.
 */

#define R36_FFS_DESCRIPTORS_MAGIC_V2 3u
#define R36_FFS_STRINGS_MAGIC        2u

#define R36_FFS_HAS_FS_DESC    0x01u
#define R36_FFS_HAS_HS_DESC    0x02u
#define R36_FFS_HAS_MS_OS_DESC 0x08u

#define R36_USB_DT_INTERFACE          0x04u
#define R36_USB_DT_ENDPOINT           0x05u
#define R36_USB_CLASS_STILL_IMAGE     0x06u
#define R36_USB_CLASS_VENDOR_SPEC     0xffu
#define R36_USB_SUBCLASS_ADB          0x42u
#define R36_USB_PROTOCOL_ADB          0x01u
#define R36_USB_DIR_OUT               0x00u
#define R36_USB_DIR_IN                0x80u
#define R36_USB_ENDPOINT_XFER_BULK    0x02u
#define R36_USB_ENDPOINT_XFER_INT     0x03u

#define R36_MTP_ADB_VID               "0x18d1"
#define R36_MTP_ADB_PID               "0x4e22"
#define R36_HC16XX_MUSB_MAX_TX_EPS    5u
#define R36_HC16XX_MUSB_MAX_RX_EPS    5u
#define R36_MTP_ADB_REQUIRED_TX_EPS   3u
#define R36_MTP_ADB_REQUIRED_RX_EPS   2u

#pragma pack(push, 1)
struct r36_usb_interface_desc {
    uint8_t bLength;
    uint8_t bDescriptorType;
    uint8_t bInterfaceNumber;
    uint8_t bAlternateSetting;
    uint8_t bNumEndpoints;
    uint8_t bInterfaceClass;
    uint8_t bInterfaceSubClass;
    uint8_t bInterfaceProtocol;
    uint8_t iInterface;
};

struct r36_usb_endpoint_desc_no_audio {
    uint8_t  bLength;
    uint8_t  bDescriptorType;
    uint8_t  bEndpointAddress;
    uint8_t  bmAttributes;
    uint16_t wMaxPacketSize;
    uint8_t  bInterval;
};

struct r36_usb_os_desc_header {
    uint8_t  interface;
    uint32_t dwLength;
    uint16_t bcdVersion;
    uint16_t wIndex;
    uint8_t  bCount;
    uint8_t  Reserved;
};

struct r36_usb_ext_compat_desc {
    uint8_t bFirstInterfaceNumber;
    uint8_t Reserved1;
    uint8_t CompatibleID[8];
    uint8_t SubCompatibleID[8];
    uint8_t Reserved2[6];
};

struct r36_ffs_mtp_descriptors_v2 {
    uint32_t magic;
    uint32_t length;
    uint32_t flags;
    uint32_t fs_count;
    uint32_t hs_count;
    uint32_t ms_os_count;
    struct r36_usb_interface_desc         fs_intf;
    struct r36_usb_endpoint_desc_no_audio fs_bulk_in;
    struct r36_usb_endpoint_desc_no_audio fs_bulk_out;
    struct r36_usb_endpoint_desc_no_audio fs_int_in;
    struct r36_usb_interface_desc         hs_intf;
    struct r36_usb_endpoint_desc_no_audio hs_bulk_in;
    struct r36_usb_endpoint_desc_no_audio hs_bulk_out;
    struct r36_usb_endpoint_desc_no_audio hs_int_in;
    struct r36_usb_os_desc_header         ms_os_header;
    struct r36_usb_ext_compat_desc        ms_os_compat;
};

struct r36_ffs_adb_descriptors_v2 {
    uint32_t magic;
    uint32_t length;
    uint32_t flags;
    uint32_t fs_count;
    uint32_t hs_count;
    struct r36_usb_interface_desc         fs_intf;
    struct r36_usb_endpoint_desc_no_audio fs_bulk_in;
    struct r36_usb_endpoint_desc_no_audio fs_bulk_out;
    struct r36_usb_interface_desc         hs_intf;
    struct r36_usb_endpoint_desc_no_audio hs_bulk_in;
    struct r36_usb_endpoint_desc_no_audio hs_bulk_out;
};

struct r36_ffs_one_string {
    uint32_t magic;
    uint32_t length;
    uint32_t str_count;
    uint32_t lang_count;
    uint16_t code;
    char     str1[16];
};
#pragma pack(pop)

_Static_assert(sizeof(struct r36_usb_interface_desc) == 9, "USB interface descriptor must be 9 bytes");
_Static_assert(sizeof(struct r36_usb_endpoint_desc_no_audio) == 7, "no-audio endpoint descriptor must be 7 bytes");
_Static_assert(sizeof(struct r36_usb_os_desc_header) == 11, "FunctionFS OS desc header must be 11 bytes");
_Static_assert(sizeof(struct r36_usb_ext_compat_desc) == 24, "MS OS compat entry must be 24 bytes");
_Static_assert(R36_MTP_ADB_REQUIRED_TX_EPS <= R36_HC16XX_MUSB_MAX_TX_EPS, "TX endpoints exceed HC16xx MUSB FIFO table");
_Static_assert(R36_MTP_ADB_REQUIRED_RX_EPS <= R36_HC16XX_MUSB_MAX_RX_EPS, "RX endpoints exceed HC16xx MUSB FIFO table");

static inline void r36_build_ffs_mtp_descriptors(struct r36_ffs_mtp_descriptors_v2 *out)
{
    memset(out, 0, sizeof(*out));
    out->magic = R36_FFS_DESCRIPTORS_MAGIC_V2;
    out->length = sizeof(*out);
    out->flags = R36_FFS_HAS_FS_DESC | R36_FFS_HAS_HS_DESC | R36_FFS_HAS_MS_OS_DESC;
    out->fs_count = 4;
    out->hs_count = 4;
    out->ms_os_count = 1;

    out->fs_intf = (struct r36_usb_interface_desc){
        .bLength = 9, .bDescriptorType = R36_USB_DT_INTERFACE,
        .bInterfaceNumber = 0, .bAlternateSetting = 0, .bNumEndpoints = 3,
        .bInterfaceClass = R36_USB_CLASS_STILL_IMAGE, .bInterfaceSubClass = 1, .bInterfaceProtocol = 1,
        .iInterface = 1,
    };
    out->fs_bulk_in = (struct r36_usb_endpoint_desc_no_audio){
        .bLength = 7, .bDescriptorType = R36_USB_DT_ENDPOINT,
        .bEndpointAddress = 1 | R36_USB_DIR_IN, .bmAttributes = R36_USB_ENDPOINT_XFER_BULK,
        .wMaxPacketSize = 64, .bInterval = 0,
    };
    out->fs_bulk_out = (struct r36_usb_endpoint_desc_no_audio){
        .bLength = 7, .bDescriptorType = R36_USB_DT_ENDPOINT,
        .bEndpointAddress = 2 | R36_USB_DIR_OUT, .bmAttributes = R36_USB_ENDPOINT_XFER_BULK,
        .wMaxPacketSize = 64, .bInterval = 0,
    };
    out->fs_int_in = (struct r36_usb_endpoint_desc_no_audio){
        .bLength = 7, .bDescriptorType = R36_USB_DT_ENDPOINT,
        .bEndpointAddress = 3 | R36_USB_DIR_IN, .bmAttributes = R36_USB_ENDPOINT_XFER_INT,
        .wMaxPacketSize = 28, .bInterval = 6,
    };

    out->hs_intf = out->fs_intf;
    out->hs_bulk_in = out->fs_bulk_in;
    out->hs_bulk_in.wMaxPacketSize = 512;
    out->hs_bulk_out = out->fs_bulk_out;
    out->hs_bulk_out.wMaxPacketSize = 512;
    out->hs_int_in = out->fs_int_in;

    out->ms_os_header = (struct r36_usb_os_desc_header){
        .interface = 0, .dwLength = 16 + sizeof(struct r36_usb_ext_compat_desc),
        .bcdVersion = 0x0100, .wIndex = 0x0004, .bCount = 1, .Reserved = 0,
    };
    out->ms_os_compat.bFirstInterfaceNumber = 0;
    out->ms_os_compat.Reserved1 = 1;
    memcpy(out->ms_os_compat.CompatibleID, "MTP\0\0\0\0\0", 8);
}

static inline void r36_build_ffs_adb_descriptors(struct r36_ffs_adb_descriptors_v2 *out)
{
    memset(out, 0, sizeof(*out));
    out->magic = R36_FFS_DESCRIPTORS_MAGIC_V2;
    out->length = sizeof(*out);
    out->flags = R36_FFS_HAS_FS_DESC | R36_FFS_HAS_HS_DESC;
    out->fs_count = 3;
    out->hs_count = 3;

    out->fs_intf = (struct r36_usb_interface_desc){
        .bLength = 9, .bDescriptorType = R36_USB_DT_INTERFACE,
        .bInterfaceNumber = 0, .bAlternateSetting = 0, .bNumEndpoints = 2,
        .bInterfaceClass = R36_USB_CLASS_VENDOR_SPEC,
        .bInterfaceSubClass = R36_USB_SUBCLASS_ADB,
        .bInterfaceProtocol = R36_USB_PROTOCOL_ADB,
        .iInterface = 1,
    };
    out->fs_bulk_in = (struct r36_usb_endpoint_desc_no_audio){
        .bLength = 7, .bDescriptorType = R36_USB_DT_ENDPOINT,
        .bEndpointAddress = 1 | R36_USB_DIR_IN, .bmAttributes = R36_USB_ENDPOINT_XFER_BULK,
        .wMaxPacketSize = 64, .bInterval = 0,
    };
    out->fs_bulk_out = (struct r36_usb_endpoint_desc_no_audio){
        .bLength = 7, .bDescriptorType = R36_USB_DT_ENDPOINT,
        .bEndpointAddress = 2 | R36_USB_DIR_OUT, .bmAttributes = R36_USB_ENDPOINT_XFER_BULK,
        .wMaxPacketSize = 64, .bInterval = 0,
    };

    out->hs_intf = out->fs_intf;
    out->hs_bulk_in = out->fs_bulk_in;
    out->hs_bulk_in.wMaxPacketSize = 512;
    out->hs_bulk_out = out->fs_bulk_out;
    out->hs_bulk_out.wMaxPacketSize = 512;
}

static inline size_t r36_build_ffs_string(uint8_t *buf, size_t cap, const char *label)
{
    size_t slen = strlen(label) + 1;
    size_t total = 16 + 2 + slen;
    uint32_t magic = R36_FFS_STRINGS_MAGIC, length = (uint32_t)total, one = 1;
    uint16_t lang = 0x0409;
    if (cap < total) return 0;
    memcpy(buf + 0, &magic, 4);
    memcpy(buf + 4, &length, 4);
    memcpy(buf + 8, &one, 4);
    memcpy(buf + 12, &one, 4);
    memcpy(buf + 16, &lang, 2);
    memcpy(buf + 18, label, slen);
    return total;
}

/* Chunked MTP CT_DATA sender for FunctionFS bulk-IN endpoint (replaces kernel
 * ioctl MTP_SEND_FILE_WITH_HEADER on Linux 7.2 where f_mtp.ko is absent).
 */
typedef int (*r36_write_fn)(int fd, const void *buf, size_t len);
typedef int (*r36_pread_fn)(int fd, void *buf, size_t len, uint64_t offset);

static inline int r36_mtp_ffs_send_file_with_header(
    int ep_in_fd, int file_fd, uint64_t offset, uint64_t length,
    uint16_t command, uint32_t transaction_id,
    r36_write_fn write_all, r36_pread_fn pread_chunk)
{
    uint8_t hdr[12];
    uint8_t chunk[4096];
    uint64_t total64 = length + 12u;
    uint32_t total32 = total64 >= 0xffffffffULL ? 0xffffffffu : (uint32_t)total64;
    uint16_t type_data = 2u;
    uint64_t remaining = length;
    uint64_t cur_off = offset;

    if (!write_all || !pread_chunk || ep_in_fd < 0 || file_fd < 0) {
        errno = EINVAL;
        return -1;
    }
    memcpy(hdr + 0, &total32, 4);
    memcpy(hdr + 4, &type_data, 2);
    memcpy(hdr + 6, &command, 2);
    memcpy(hdr + 8, &transaction_id, 4);
    if (write_all(ep_in_fd, hdr, sizeof(hdr)) != 0)
        return -1;

    while (remaining > 0) {
        size_t want = remaining > sizeof(chunk) ? sizeof(chunk) : (size_t)remaining;
        int got = pread_chunk(file_fd, chunk, want, cur_off);
        if (got <= 0 || (size_t)got > want) {
            errno = EIO;
            return -1;
        }
        if (write_all(ep_in_fd, chunk, (size_t)got) != 0)
            return -1;
        cur_off += (uint64_t)got;
        remaining -= (uint64_t)got;
    }
    return 0;
}

/* ADB protocol v1 framing (24-byte header + payload) */
#define R36_ADB_SYNC 0x434e5953u
#define R36_ADB_CNXN 0x4e584e43u
#define R36_ADB_OPEN 0x4e45504fu
#define R36_ADB_OKAY 0x59414b4fu
#define R36_ADB_CLSE 0x45534c43u
#define R36_ADB_WRTE 0x45545257u

#define R36_ADB_VERSION   0x01000000u
#define R36_ADB_MAXDATA   4096u

struct r36_adb_msg {
    uint32_t command;
    uint32_t arg0;
    uint32_t arg1;
    uint32_t data_length;
    uint32_t data_check;
    uint32_t magic;
};

_Static_assert(sizeof(struct r36_adb_msg) == 24, "ADB header must be 24 bytes");

static inline uint32_t r36_adb_checksum(const void *data, size_t len)
{
    const uint8_t *p = (const uint8_t *)data;
    uint32_t sum = 0;
    for (size_t i = 0; i < len; i++)
        sum += p[i];
    return sum;
}

static inline void r36_adb_pack(struct r36_adb_msg *msg, uint32_t cmd, uint32_t a0, uint32_t a1,
                                const void *payload, uint32_t len)
{
    msg->command = cmd;
    msg->arg0 = a0;
    msg->arg1 = a1;
    msg->data_length = len;
    msg->data_check = payload ? r36_adb_checksum(payload, len) : 0u;
    msg->magic = cmd ^ 0xffffffffu;
}

static inline int r36_adb_validate(const struct r36_adb_msg *msg, const void *payload)
{
    if (!msg) return -1;
    if (msg->magic != (msg->command ^ 0xffffffffu)) return -1;
    if (msg->data_length > R36_ADB_MAXDATA) return -1;
    if (msg->data_length > 0) {
        if (!payload) return -1;
        if (r36_adb_checksum(payload, msg->data_length) != msg->data_check) return -1;
    } else if (msg->data_check != 0) {
        return -1;
    }
    return 0;
}

/* Minimal deterministic ADB protocol session state machine (CNXN/OPEN/WRTE/CLSE)
 * for non-interactive diagnostic / command channels over FunctionFS bulk endpoints.
 */
struct r36_adb_session {
    int      connected;
    uint32_t max_payload;
    uint32_t local_id;
    uint32_t remote_id;
    int      stream_open;
};

static inline int r36_adb_handle_packet(
    struct r36_adb_session *sess,
    const struct r36_adb_msg *in_msg, const void *in_payload,
    struct r36_adb_msg *out_msg, uint8_t *out_payload, size_t out_cap)
{
    static const char banner[] = "device::ro.product.name=r36s;ro.product.model=R36S;ro.product.device=hc16xx;\0";
    if (!sess || !in_msg || !out_msg || r36_adb_validate(in_msg, in_payload) != 0)
        return -1;

    if (in_msg->command == R36_ADB_CNXN) {
        size_t blen = sizeof(banner) - 1;
        if (out_cap < blen) return -1;
        sess->connected = 1;
        sess->max_payload = in_msg->arg1 > 0 && in_msg->arg1 < R36_ADB_MAXDATA ? in_msg->arg1 : R36_ADB_MAXDATA;
        sess->stream_open = 0;
        memcpy(out_payload, banner, blen);
        r36_adb_pack(out_msg, R36_ADB_CNXN, R36_ADB_VERSION, R36_ADB_MAXDATA, out_payload, (uint32_t)blen);
        return 1;
    }
    if (!sess->connected)
        return -1;

    if (in_msg->command == R36_ADB_OPEN) {
        if (in_msg->arg0 == 0 || in_msg->data_length == 0) return -1;
        sess->remote_id = in_msg->arg0;
        sess->local_id = 1u;
        sess->stream_open = 1;
        r36_adb_pack(out_msg, R36_ADB_OKAY, sess->local_id, sess->remote_id, NULL, 0);
        return 1;
    }
    if (in_msg->command == R36_ADB_WRTE) {
        if (!sess->stream_open || in_msg->arg0 != sess->remote_id || in_msg->arg1 != sess->local_id)
            return -1;
        r36_adb_pack(out_msg, R36_ADB_OKAY, sess->local_id, sess->remote_id, NULL, 0);
        return 1;
    }
    if (in_msg->command == R36_ADB_CLSE) {
        sess->stream_open = 0;
        r36_adb_pack(out_msg, R36_ADB_CLSE, sess->local_id, sess->remote_id, NULL, 0);
        return 1;
    }
    return 0;
}

/* Composite FunctionFS ep0 initialization helper: must write descriptors +
 * strings to both /dev/ffs-mtp/ep0 and /dev/ffs-adb/ep0 BEFORE binding UDC.
 */
static inline int r36_ffs_init_mtp_ep0(int ep0_fd, r36_write_fn write_all)
{
    struct r36_ffs_mtp_descriptors_v2 desc;
    uint8_t str_buf[64];
    size_t slen;
    if (ep0_fd < 0 || !write_all) { errno = EINVAL; return -1; }
    r36_build_ffs_mtp_descriptors(&desc);
    slen = r36_build_ffs_string(str_buf, sizeof(str_buf), "MTP");
    if (!slen) { errno = EINVAL; return -1; }
    if (write_all(ep0_fd, &desc, sizeof(desc)) != 0) return -1;
    if (write_all(ep0_fd, str_buf, slen) != 0) return -1;
    return 0;
}

static inline int r36_ffs_init_adb_ep0(int ep0_fd, r36_write_fn write_all)
{
    struct r36_ffs_adb_descriptors_v2 desc;
    uint8_t str_buf[64];
    size_t slen;
    if (ep0_fd < 0 || !write_all) { errno = EINVAL; return -1; }
    r36_build_ffs_adb_descriptors(&desc);
    slen = r36_build_ffs_string(str_buf, sizeof(str_buf), "ADB Interface");
    if (!slen) { errno = EINVAL; return -1; }
    if (write_all(ep0_fd, &desc, sizeof(desc)) != 0) return -1;
    if (write_all(ep0_fd, str_buf, slen) != 0) return -1;
    return 0;
}

#endif /* R36_USB_FFS_MTP_ADB_H */
