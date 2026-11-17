/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef R36_USB_MTP_ADB_MOCK
#include <dirent.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#endif

#include "usb_ffs_mtp_adb.h"

/* Composite Linux 7.2 FunctionFS service running MTP (ffs.mtp) and ADB (ffs.adb)
 * simultaneously on HC16xx MUSB USB0 (idVendor=0x18d1, idProduct=0x4e22).
 *
 * Ordering contract required by drivers/usb/gadget/function/f_fs.c:
 *   1. Create configfs gadget, functions/ffs.mtp, functions/ffs.adb, and links
 *      in configs/c.1/.
 *   2. Mount functionfs instances "mtp" -> /dev/ffs-mtp and "adb" -> /dev/ffs-adb.
 *   3. Open both ep0 nodes and write FunctionFS v2 descriptors + strings so both
 *      instances enter FFS_ACTIVE.
 *   4. Open bulk/interrupt endpoints (/dev/ffs-mtp/ep1..3, /dev/ffs-adb/ep1..2).
 *   5. Bind the single UDC (musb-hdrc.0.auto) last.
 */

#define R36_COMPOSITE_GADGET_DIR "/sys/kernel/config/usb_gadget/r36composite"
#define R36_FFS_MTP_DIR          "/dev/ffs-mtp"
#define R36_FFS_ADB_DIR          "/dev/ffs-adb"

#define R36_MTP_CT_COMMAND  1u
#define R36_MTP_CT_DATA     2u
#define R36_MTP_CT_RESPONSE 3u

#define R36_MTP_OP_GetDeviceInfo           0x1001u
#define R36_MTP_OP_OpenSession             0x1002u
#define R36_MTP_OP_CloseSession            0x1003u
#define R36_MTP_OP_GetStorageIDs           0x1004u
#define R36_MTP_OP_GetStorageInfo          0x1005u
#define R36_MTP_OP_GetObjectHandles        0x1007u
#define R36_MTP_OP_GetObjectInfo           0x1008u
#define R36_MTP_OP_GetObject               0x1009u
#define R36_MTP_OP_DeleteObject            0x100Bu
#define R36_MTP_OP_SendObjectInfo          0x100Cu
#define R36_MTP_OP_SendObject              0x100Du
#define R36_MTP_OP_GetDevicePropDesc       0x1014u
#define R36_MTP_OP_GetPartialObject        0x101Bu
#define R36_MTP_OP_GetObjectPropsSupported 0x9801u
#define R36_MTP_OP_TF_Info                 0x9A00u

#define R36_MTP_RC_OK                      0x2001u
#define R36_MTP_RC_GeneralError            0x2002u
#define R36_MTP_RC_OperationNotSupported   0x2005u
#define R36_MTP_RC_IncompleteTransfer      0x2007u
#define R36_MTP_RC_InvalidStorageID        0x2008u
#define R36_MTP_RC_InvalidObjectHandle     0x2009u
#define R36_MTP_RC_DevicePropNotSupported  0x200Au
#define R36_MTP_RC_AccessDenied            0x200Fu
#define R36_MTP_RC_NoValidObjectInfo       0x2015u
#define R36_MTP_RC_InvalidParentObject     0x201Au
#define R36_MTP_RC_InvalidParameter        0x201Du
#define R36_MTP_RC_SessionAlreadyOpen      0x201Eu

#define R36_MTP_FMT_UNDEFINED              0x3000u
#define R36_MTP_FMT_ASSOCIATION            0x3001u

#define R36_MTP_STORAGE_ID                 0x00010001u
#define R36_MTP_ROOT_HANDLE                0xFFFFFFFFu
#define R36_MTP_MAX_OBJECTS                256u

#define R36_MTP_TRANSPORT_NONE             0
#define R36_MTP_TRANSPORT_FFS              1
#define R36_MTP_TRANSPORT_LEGACY           2

struct r36_composite_fds {
    int mtp_ep0;
    int mtp_in;
    int mtp_out;
    int mtp_int;
    int adb_ep0;
    int adb_in;
    int adb_out;
    char bound_udc[128];
    char last_phase[64];
};

struct r36_mtp_obj {
    uint32_t parent;
    char     name[128];
    uint8_t  is_dir;
    uint8_t  used;
};

struct r36_mtp_adb_runtime {
    struct r36_composite_fds fds;
    struct r36_adb_session   adb;
    int                      mtp_transport_mode;
    int                      mtp_legacy_fd;
    int                      mtp_legacy_active;
    int                      mtp_session_open;
    uint32_t                 mtp_session_id;
    char                     mtp_root[256];
    struct r36_mtp_obj       objs[R36_MTP_MAX_OBJECTS];
    uint32_t                 obj_count;
    uint32_t                 send_parent;
    char                     send_name[128];
    uint32_t                 send_size;
    uint8_t                  send_is_dir;
    uint32_t                 send_handle;
    int                      send_pending;
    int                      adb_sync_mode;
    int                      adb_pending_close;
    char                     adb_sync_root[256];
    char                     adb_send_path[512];
    uint8_t                  adb_send_buf[65536];
    size_t                   adb_send_len;
    int                      adb_send_active;
    uint8_t                  adb_pending_out[R36_ADB_MAXDATA];
    uint32_t                 adb_pending_len;
    unsigned int             mtp_commands_handled;
    unsigned int             adb_packets_handled;
};

static void r36_init_composite_fds(struct r36_composite_fds *f)
{
    memset(f, 0, sizeof(*f));
    f->mtp_ep0 = f->mtp_in = f->mtp_out = f->mtp_int = -1;
    f->adb_ep0 = f->adb_in = f->adb_out = -1;
    strcpy(f->last_phase, "not_started");
}

static int r36_write_all_fd(int fd, const void *buf, size_t len)
{
    const uint8_t *p = (const uint8_t *)buf;
    size_t done = 0;
    while (done < len) {
        ssize_t n = write(fd, p + done, len - done);
        if (n < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (n == 0) {
            errno = EIO;
            return -1;
        }
        done += (size_t)n;
    }
    return 0;
}

static int r36_write_attr(const char *path, const char *text)
{
    int fd = open(path, O_WRONLY | O_CLOEXEC);
    int rc;
    if (fd < 0) return -1;
    rc = r36_write_all_fd(fd, text, strlen(text));
    close(fd);
    return rc;
}

static int r36_mkdir_ok(const char *path)
{
    return (mkdir(path, 0755) == 0 || errno == EEXIST) ? 0 : -1;
}

static void r36_close_fd(int *fd)
{
    if (*fd >= 0) {
        close(*fd);
        *fd = -1;
    }
}

static void r36_teardown_mtp_adb_gadget(struct r36_composite_fds *f)
{
    if (f->bound_udc[0]) {
        r36_write_attr(R36_COMPOSITE_GADGET_DIR "/UDC", "\n");
        f->bound_udc[0] = 0;
    }
    r36_close_fd(&f->mtp_int);
    r36_close_fd(&f->mtp_out);
    r36_close_fd(&f->mtp_in);
    r36_close_fd(&f->mtp_ep0);
    r36_close_fd(&f->adb_out);
    r36_close_fd(&f->adb_in);
    r36_close_fd(&f->adb_ep0);
    umount(R36_FFS_MTP_DIR);
    umount(R36_FFS_ADB_DIR);
    unlink(R36_COMPOSITE_GADGET_DIR "/os_desc/c.1");
    unlink(R36_COMPOSITE_GADGET_DIR "/configs/c.1/ffs.mtp");
    unlink(R36_COMPOSITE_GADGET_DIR "/configs/c.1/ffs.adb");
}

static int r36_setup_mtp_adb_gadget(struct r36_composite_fds *f)
{
    DIR *dir;
    struct dirent *entry;

    r36_init_composite_fds(f);
    strcpy(f->last_phase, "configfs");
    if (r36_mkdir_ok("/sys/kernel/config"))
        return -1;
    if (mount("configfs", "/sys/kernel/config", "configfs", 0, NULL) != 0 && errno != EBUSY)
        return -1;
    if (r36_mkdir_ok(R36_COMPOSITE_GADGET_DIR) || chdir(R36_COMPOSITE_GADGET_DIR) != 0)
        return -1;

    strcpy(f->last_phase, "descriptors");
    if (r36_write_attr("idVendor", R36_MTP_ADB_VID) ||
        r36_write_attr("idProduct", R36_MTP_ADB_PID) ||
        r36_write_attr("bcdUSB", "0x0200") ||
        r36_write_attr("bcdDevice", "0x0100") ||
        r36_write_attr("bDeviceClass", "0x00") ||
        r36_write_attr("bDeviceSubClass", "0x00") ||
        r36_write_attr("bDeviceProtocol", "0x00"))
        return -1;

    if (r36_mkdir_ok("strings/0x409") ||
        r36_write_attr("strings/0x409/serialnumber", "R36S-MTP-ADB") ||
        r36_write_attr("strings/0x409/manufacturer", "TreeFrogUI") ||
        r36_write_attr("strings/0x409/product", "TreeFrogUI MTP+ADB"))
        return -1;

    if (r36_mkdir_ok("configs/c.1") ||
        r36_mkdir_ok("configs/c.1/strings/0x409") ||
        r36_write_attr("configs/c.1/strings/0x409/configuration", "MTP+ADB") ||
        r36_write_attr("configs/c.1/MaxPower", "250") ||
        r36_write_attr("configs/c.1/bmAttributes", "0x80"))
        return -1;

    strcpy(f->last_phase, "os_desc");
    if (r36_write_attr("os_desc/b_vendor_code", "1") ||
        r36_write_attr("os_desc/qw_sign", "MSFT100") ||
        symlink(R36_COMPOSITE_GADGET_DIR "/configs/c.1", "os_desc/c.1") != 0 ||
        r36_write_attr("os_desc/use", "1"))
        return -1;

    strcpy(f->last_phase, "functions");
    if (r36_mkdir_ok("functions/ffs.mtp") ||
        r36_mkdir_ok("functions/ffs.adb") ||
        symlink(R36_COMPOSITE_GADGET_DIR "/functions/ffs.mtp", "configs/c.1/ffs.mtp") != 0 ||
        symlink(R36_COMPOSITE_GADGET_DIR "/functions/ffs.adb", "configs/c.1/ffs.adb") != 0)
        return -1;

    strcpy(f->last_phase, "mount_ffs");
    if (r36_mkdir_ok(R36_FFS_MTP_DIR) ||
        mount("mtp", R36_FFS_MTP_DIR, "functionfs", 0, NULL) != 0 ||
        r36_mkdir_ok(R36_FFS_ADB_DIR) ||
        mount("adb", R36_FFS_ADB_DIR, "functionfs", 0, NULL) != 0)
        goto fail;

    strcpy(f->last_phase, "init_mtp_ep0");
    f->mtp_ep0 = open(R36_FFS_MTP_DIR "/ep0", O_RDWR | O_CLOEXEC);
    if (f->mtp_ep0 < 0 || r36_ffs_init_mtp_ep0(f->mtp_ep0, r36_write_all_fd) != 0)
        goto fail;

    strcpy(f->last_phase, "init_adb_ep0");
    f->adb_ep0 = open(R36_FFS_ADB_DIR "/ep0", O_RDWR | O_CLOEXEC);
    if (f->adb_ep0 < 0 || r36_ffs_init_adb_ep0(f->adb_ep0, r36_write_all_fd) != 0)
        goto fail;

    strcpy(f->last_phase, "open_data_eps");
    f->mtp_in  = open(R36_FFS_MTP_DIR "/ep1", O_RDWR | O_CLOEXEC);
    f->mtp_out = open(R36_FFS_MTP_DIR "/ep2", O_RDWR | O_CLOEXEC);
    f->mtp_int = open(R36_FFS_MTP_DIR "/ep3", O_RDWR | O_CLOEXEC);
    f->adb_in  = open(R36_FFS_ADB_DIR "/ep1", O_RDWR | O_CLOEXEC);
    f->adb_out = open(R36_FFS_ADB_DIR "/ep2", O_RDWR | O_CLOEXEC);
    if (f->mtp_in < 0 || f->mtp_out < 0 || f->mtp_int < 0 || f->adb_in < 0 || f->adb_out < 0)
        goto fail;

    strcpy(f->last_phase, "wait_udc");
    for (unsigned int attempt = 0; attempt < 30; attempt++) {
        unsigned int count = 0;
        dir = opendir("/sys/class/udc");
        if (dir) {
            while ((entry = readdir(dir))) {
                if (entry->d_name[0] == '.') continue;
                count++;
                snprintf(f->bound_udc, sizeof(f->bound_udc), "%.127s", entry->d_name);
            }
            closedir(dir);
        }
        if (count > 1) goto fail;
        if (count == 1) {
            strcpy(f->last_phase, "bind_udc");
            if (r36_write_attr("UDC", f->bound_udc) != 0) {
                f->bound_udc[0] = 0;
                goto fail;
            }
            strcpy(f->last_phase, "bound");
            return 0;
        }
        usleep(100000);
    }
    errno = ENODEV;
fail:
    f->bound_udc[0] = 0;
    r36_teardown_mtp_adb_gadget(f);
    return -1;
}

/* Select MTP transport automatically: FunctionFS on Linux 7.2, or legacy /dev/mtp_usb on stock 4.4 */
static int r36_open_mtp_transport(struct r36_mtp_adb_runtime *rt)
{
    if (!rt) { errno = EINVAL; return -1; }
    if (rt->fds.mtp_ep0 >= 0) {
        rt->mtp_transport_mode = R36_MTP_TRANSPORT_FFS;
        return R36_MTP_TRANSPORT_FFS;
    }
    int fd = open(R36_FFS_MTP_DIR "/ep0", O_RDWR | O_CLOEXEC);
    if (fd >= 0) {
        close(fd);
        rt->mtp_transport_mode = R36_MTP_TRANSPORT_FFS;
        return R36_MTP_TRANSPORT_FFS;
    }
    fd = open("/dev/mtp_usb", O_RDWR | O_CLOEXEC);
    if (fd >= 0) {
        rt->mtp_legacy_fd = fd;
        rt->mtp_legacy_active = 1;
        rt->mtp_transport_mode = R36_MTP_TRANSPORT_LEGACY;
        return R36_MTP_TRANSPORT_LEGACY;
    }
    rt->mtp_legacy_fd = -1;
    rt->mtp_legacy_active = 0;
    rt->mtp_transport_mode = R36_MTP_TRANSPORT_NONE;
    return -1;
}

static void r36_close_mtp_transport(struct r36_mtp_adb_runtime *rt)
{
    if (!rt) return;
    if (rt->mtp_legacy_active && rt->mtp_legacy_fd >= 0) {
        close(rt->mtp_legacy_fd);
        rt->mtp_legacy_fd = -1;
    }
    rt->mtp_legacy_active = 0;
    rt->mtp_transport_mode = R36_MTP_TRANSPORT_NONE;
}

/* MTP container helpers over FunctionFS bulk endpoints */
static int r36_mtp_send_container(int ep_in, uint16_t type, uint16_t code, uint32_t tid,
                                  const void *payload, uint32_t payload_len)
{
    uint8_t stack_buf[4096];
    uint32_t total = 12u + payload_len;
    uint8_t *buf = stack_buf;
    int rc;
    if (total > sizeof(stack_buf)) {
        buf = (uint8_t *)malloc(total);
        if (!buf) { errno = ENOMEM; return -1; }
    }
    memcpy(buf + 0, &total, 4);
    memcpy(buf + 4, &type, 2);
    memcpy(buf + 6, &code, 2);
    memcpy(buf + 8, &tid, 4);
    if (payload_len > 0 && payload)
        memcpy(buf + 12, payload, payload_len);
    rc = r36_write_all_fd(ep_in, buf, total);
    if (buf != stack_buf)
        free(buf);
    return rc;
}

static int r36_mtp_send_response(int ep_in, uint16_t rc, uint32_t tid,
                                 int nr, uint32_t r0, uint32_t r1, uint32_t r2)
{
    uint32_t params[3] = { r0, r1, r2 };
    uint32_t plen = (nr > 0 && nr <= 3) ? (uint32_t)nr * 4u : 0u;
    return r36_mtp_send_container(ep_in, R36_MTP_CT_RESPONSE, rc, tid, plen ? params : NULL, plen);
}

static size_t r36_mtp_put_u16(uint8_t *dst, size_t off, uint16_t v)
{
    memcpy(dst + off, &v, 2);
    return off + 2;
}

static size_t r36_mtp_put_u32(uint8_t *dst, size_t off, uint32_t v)
{
    memcpy(dst + off, &v, 4);
    return off + 4;
}

static size_t r36_mtp_put_u64(uint8_t *dst, size_t off, uint64_t v)
{
    off = r36_mtp_put_u32(dst, off, (uint32_t)v);
    off = r36_mtp_put_u32(dst, off, (uint32_t)(v >> 32));
    return off;
}

static size_t r36_mtp_put_str(uint8_t *dst, size_t off, const char *s)
{
    uint16_t u[256];
    int n = 0;
    const uint8_t *p = (const uint8_t *)s;
    while (*p && n < 250) {
        uint32_t c;
        if (*p < 0x80u) c = *p++;
        else if ((*p & 0xE0u) == 0xC0u && p[1]) { c = ((p[0] & 0x1Fu) << 6) | (p[1] & 0x3Fu); p += 2; }
        else if ((*p & 0xF0u) == 0xE0u && p[1] && p[2]) { c = ((p[0] & 0x0Fu) << 12) | ((p[1] & 0x3Fu) << 6) | (p[2] & 0x3Fu); p += 3; }
        else if ((*p & 0xF8u) == 0xF0u && p[1] && p[2] && p[3]) {
            c = ((p[0] & 0x07u) << 18) | ((p[1] & 0x3Fu) << 12) | ((p[2] & 0x3Fu) << 6) | (p[3] & 0x3Fu); p += 4;
        } else { c = '?'; p++; }
        if (c >= 0x10000u) {
            c -= 0x10000u;
            u[n++] = (uint16_t)(0xD800u | (c >> 10));
            u[n++] = (uint16_t)(0xDC00u | (c & 0x3FFu));
        } else {
            u[n++] = (uint16_t)c;
        }
    }
    if (n == 0) {
        dst[off++] = 0;
        return off;
    }
    dst[off++] = (uint8_t)(n + 1);
    for (int i = 0; i < n; i++)
        off = r36_mtp_put_u16(dst, off, u[i]);
    off = r36_mtp_put_u16(dst, off, 0);
    return off;
}

static int r36_mtp_get_str(const uint8_t *buf, size_t len, char *out, size_t outn)
{
    if (len < 1 || outn < 1) return -1;
    int n = buf[0];
    size_t need = 1u + (size_t)n * 2u;
    size_t o = 0;
    if (len < need) return -1;
    for (int i = 0; i < n; i++) {
        uint32_t c = (uint32_t)buf[1 + 2 * i] | ((uint32_t)buf[2 + 2 * i] << 8);
        if (c == 0) break;
        if (c >= 0xD800u && c < 0xDC00u && i + 1 < n) {
            uint32_t c2 = (uint32_t)buf[3 + 2 * i] | ((uint32_t)buf[4 + 2 * i] << 8);
            c = 0x10000u + ((c - 0xD800u) << 10) + (c2 - 0xDC00u);
            i++;
        }
        if (o + 5u >= outn) break;
        if (c < 0x80u) out[o++] = (char)c;
        else if (c < 0x800u) { out[o++] = (char)(0xC0u | (c >> 6)); out[o++] = (char)(0x80u | (c & 0x3Fu)); }
        else if (c < 0x10000u) {
            out[o++] = (char)(0xE0u | (c >> 12));
            out[o++] = (char)(0x80u | ((c >> 6) & 0x3Fu));
            out[o++] = (char)(0x80u | (c & 0x3Fu));
        } else {
            out[o++] = (char)(0xF0u | (c >> 18));
            out[o++] = (char)(0x80u | ((c >> 12) & 0x3Fu));
            out[o++] = (char)(0x80u | ((c >> 6) & 0x3Fu));
            out[o++] = (char)(0x80u | (c & 0x3Fu));
        }
    }
    out[o] = 0;
    return (int)need;
}

static const char *r36_mtp_root_dir(const struct r36_mtp_adb_runtime *rt)
{
    return rt->mtp_root[0] ? rt->mtp_root : "/mnt/sdcard";
}

static int r36_mtp_is_safe_name(const char *name)
{
    if (!name || !name[0]) return 0;
    if (!strcmp(name, ".") || !strcmp(name, "..")) return 0;
    if (strchr(name, '/') || strchr(name, '\\') || strstr(name, "..")) return 0;
    return strlen(name) < sizeof(((struct r36_mtp_obj *)0)->name);
}

static int r36_mtp_obj_valid(const struct r36_mtp_adb_runtime *rt, uint32_t h)
{
    return h >= 1u && h <= R36_MTP_MAX_OBJECTS && rt->objs[h - 1u].used;
}

static uint32_t r36_mtp_find_or_add_obj(struct r36_mtp_adb_runtime *rt, uint32_t parent, const char *name, uint8_t is_dir)
{
    if (parent == 0u) parent = R36_MTP_ROOT_HANDLE;
    for (uint32_t i = 0; i < R36_MTP_MAX_OBJECTS; i++) {
        if (rt->objs[i].used && rt->objs[i].parent == parent && !strcmp(rt->objs[i].name, name)) {
            rt->objs[i].is_dir = is_dir;
            return i + 1u;
        }
    }
    for (uint32_t i = 0; i < R36_MTP_MAX_OBJECTS; i++) {
        if (!rt->objs[i].used) {
            rt->objs[i].parent = parent;
            snprintf(rt->objs[i].name, sizeof(rt->objs[i].name), "%s", name);
            rt->objs[i].is_dir = is_dir;
            rt->objs[i].used = 1u;
            if (i + 1u > rt->obj_count) rt->obj_count = i + 1u;
            return i + 1u;
        }
    }
    return 0u;
}

static void r36_mtp_mark_deleted(struct r36_mtp_adb_runtime *rt, uint32_t h)
{
    if (!r36_mtp_obj_valid(rt, h)) return;
    rt->objs[h - 1u].used = 0u;
    for (uint32_t i = 0; i < R36_MTP_MAX_OBJECTS; i++) {
        if (rt->objs[i].used && rt->objs[i].parent == h)
            r36_mtp_mark_deleted(rt, i + 1u);
    }
}

static int r36_mtp_obj_path(const struct r36_mtp_adb_runtime *rt, uint32_t handle, char *out, size_t cap)
{
    uint32_t chain[32];
    int depth = 0;
    uint32_t cur = handle;
    while (cur != 0u && cur != R36_MTP_ROOT_HANDLE) {
        if (!r36_mtp_obj_valid(rt, cur) || depth >= 32) return -1;
        chain[depth++] = cur;
        cur = rt->objs[cur - 1u].parent;
    }
    int n = snprintf(out, cap, "%s", r36_mtp_root_dir(rt));
    if (n < 0 || (size_t)n >= cap) return -1;
    size_t pos = (size_t)n;
    for (int i = depth - 1; i >= 0; i--) {
        const char *nm = rt->objs[chain[i] - 1u].name;
        int add = snprintf(out + pos, cap - pos, "/%s", nm);
        if (add < 0 || pos + (size_t)add >= cap) return -1;
        pos += (size_t)add;
    }
    return 0;
}

static int r36_mtp_read_data_phase(int ep_out, uint8_t **out_buf, uint32_t *out_total)
{
    uint8_t first[512];
    ssize_t n;
    do { n = read(ep_out, first, sizeof(first)); } while (n == 0 || (n < 0 && errno == EINTR));
    if (n < 12) return -1;
    uint32_t total = 0;
    uint16_t ctype = 0;
    memcpy(&total, first + 0, 4);
    memcpy(&ctype, first + 4, 2);
    if (ctype != R36_MTP_CT_DATA || total < 12u || total > (8u << 20)) return -1;
    uint8_t *buf = (uint8_t *)malloc(total);
    if (!buf) return -1;
    uint32_t got = (uint32_t)n > total ? total : (uint32_t)n;
    memcpy(buf, first, got);
    while (got < total) {
        uint32_t want = total - got;
        if (want > sizeof(first)) want = sizeof(first);
        n = read(ep_out, first, want);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { free(buf); return -1; }
        memcpy(buf + got, first, (size_t)n);
        got += (uint32_t)n;
    }
    *out_buf = buf;
    *out_total = total;
    return 0;
}

static uint16_t r36_mtp_send_file(struct r36_mtp_adb_runtime *rt, uint32_t handle,
                                  uint64_t off, uint64_t maxlen, int partial,
                                  uint16_t op, uint32_t tid, uint32_t *bytes_sent)
{
    char path[512];
    struct stat st;
    if (!r36_mtp_obj_valid(rt, handle) || rt->objs[handle - 1u].is_dir)
        return R36_MTP_RC_InvalidObjectHandle;
    if (r36_mtp_obj_path(rt, handle, path, sizeof(path)) != 0 || stat(path, &st) != 0)
        return R36_MTP_RC_InvalidObjectHandle;
    uint64_t sz = (uint64_t)st.st_size;
    if (off > sz) off = sz;
    uint64_t len = sz - off;
    if (partial && len > maxlen) len = maxlen;

    FILE *fp = fopen(path, "rb");
    if (!fp) return R36_MTP_RC_AccessDenied;
    if (off > 0 && fseek(fp, (long)off, SEEK_SET) != 0) {
        fclose(fp);
        return R36_MTP_RC_GeneralError;
    }

    uint8_t chunk[4096];
    uint32_t total32 = (len + 12u) >= 0xffffffffULL ? 0xffffffffu : (uint32_t)(len + 12u);
    uint16_t ctype = R36_MTP_CT_DATA;
    memcpy(chunk + 0, &total32, 4);
    memcpy(chunk + 4, &ctype, 2);
    memcpy(chunk + 6, &op, 2);
    memcpy(chunk + 8, &tid, 4);

    size_t first_room = sizeof(chunk) - 12u;
    size_t first_take = len < first_room ? (size_t)len : first_room;
    if (first_take > 0 && fread(chunk + 12, 1, first_take, fp) != first_take) {
        fclose(fp);
        return R36_MTP_RC_IncompleteTransfer;
    }
    if (r36_write_all_fd(rt->fds.mtp_in, chunk, 12u + first_take) != 0) {
        fclose(fp);
        return R36_MTP_RC_IncompleteTransfer;
    }

    uint64_t remaining = len - first_take;
    while (remaining > 0) {
        size_t want = remaining < sizeof(chunk) ? (size_t)remaining : sizeof(chunk);
        if (fread(chunk, 1, want, fp) != want || r36_write_all_fd(rt->fds.mtp_in, chunk, want) != 0) {
            fclose(fp);
            return R36_MTP_RC_IncompleteTransfer;
        }
        remaining -= want;
    }
    fclose(fp);
    *bytes_sent = (uint32_t)len;
    return R36_MTP_RC_OK;
}

/* Handle one MTP command container on /dev/ffs-mtp/ep2 -> ep1 */
static int r36_mtp_handle_one(struct r36_mtp_adb_runtime *rt, const uint8_t *pkt, size_t n)
{
    uint32_t len, tid, p[5] = { 0, 0, 0, 0, 0 };
    uint16_t type, op, rc = R36_MTP_RC_OK;
    int nr = 0;
    uint32_t r0 = 0, r1 = 0, r2 = 0;
    uint8_t data[1024];
    size_t dlen = 0;

    if (n < 12) return -1;
    memcpy(&len, pkt + 0, 4);
    memcpy(&type, pkt + 4, 2);
    memcpy(&op, pkt + 6, 2);
    memcpy(&tid, pkt + 8, 4);
    if (type != R36_MTP_CT_COMMAND) return -1;
    int np = (int)((n - 12u) / 4u);
    if (np > 5) np = 5;
    for (int i = 0; i < np; i++)
        memcpy(&p[i], pkt + 12 + (size_t)i * 4u, 4);

    switch (op) {
    case R36_MTP_OP_GetDeviceInfo: {
        static const uint16_t ops[] = {
            R36_MTP_OP_GetDeviceInfo, R36_MTP_OP_OpenSession, R36_MTP_OP_CloseSession,
            R36_MTP_OP_GetStorageIDs, R36_MTP_OP_GetStorageInfo, R36_MTP_OP_GetObjectHandles,
            R36_MTP_OP_GetObjectInfo, R36_MTP_OP_GetObject, R36_MTP_OP_DeleteObject,
            R36_MTP_OP_SendObjectInfo, R36_MTP_OP_SendObject, R36_MTP_OP_GetDevicePropDesc,
            R36_MTP_OP_GetPartialObject, R36_MTP_OP_GetObjectPropsSupported, R36_MTP_OP_TF_Info
        };
        dlen = r36_mtp_put_u16(data, dlen, 100);
        dlen = r36_mtp_put_u32(data, dlen, 6);
        dlen = r36_mtp_put_u16(data, dlen, 100);
        dlen = r36_mtp_put_str(data, dlen, "microsoft.com: 1.0;");
        dlen = r36_mtp_put_u16(data, dlen, 0);
        dlen = r36_mtp_put_u32(data, dlen, (uint32_t)(sizeof(ops) / sizeof(ops[0])));
        for (size_t i = 0; i < sizeof(ops) / sizeof(ops[0]); i++)
            dlen = r36_mtp_put_u16(data, dlen, ops[i]);
        dlen = r36_mtp_put_u32(data, dlen, 0); /* events */
        dlen = r36_mtp_put_u32(data, dlen, 1); /* device props */
        dlen = r36_mtp_put_u16(data, dlen, 0xD402u);
        dlen = r36_mtp_put_u32(data, dlen, 0); /* capture formats */
        dlen = r36_mtp_put_u32(data, dlen, 2); /* playback formats */
        dlen = r36_mtp_put_u16(data, dlen, R36_MTP_FMT_UNDEFINED);
        dlen = r36_mtp_put_u16(data, dlen, R36_MTP_FMT_ASSOCIATION);
        dlen = r36_mtp_put_str(data, dlen, "TreeFrogUI");
        dlen = r36_mtp_put_str(data, dlen, "R36S");
        dlen = r36_mtp_put_str(data, dlen, "1.0");
        dlen = r36_mtp_put_str(data, dlen, "R36S-MTP-ADB");
        if (r36_mtp_send_container(rt->fds.mtp_in, R36_MTP_CT_DATA, op, tid, data, (uint32_t)dlen) != 0)
            return -1;
        break;
    }
    case R36_MTP_OP_OpenSession:
        rt->mtp_session_open = 1;
        rt->mtp_session_id = p[0] ? p[0] : 1u;
        break;
    case R36_MTP_OP_CloseSession:
        rt->mtp_session_open = 0;
        rt->mtp_session_id = 0;
        break;
    case R36_MTP_OP_GetStorageIDs:
        dlen = r36_mtp_put_u32(data, dlen, 1u);
        dlen = r36_mtp_put_u32(data, dlen, R36_MTP_STORAGE_ID);
        if (r36_mtp_send_container(rt->fds.mtp_in, R36_MTP_CT_DATA, op, tid, data, (uint32_t)dlen) != 0)
            return -1;
        break;
    case R36_MTP_OP_GetStorageInfo: {
        if (p[0] != R36_MTP_STORAGE_ID) { rc = R36_MTP_RC_InvalidStorageID; break; }
        uint64_t total = 16ULL << 30, freeb = 1ULL << 30;
#ifndef R36_USB_MTP_ADB_MOCK
        struct statvfs v;
        if (statvfs(r36_mtp_root_dir(rt), &v) == 0) {
            total = (uint64_t)v.f_blocks * (uint64_t)v.f_frsize;
            freeb = (uint64_t)v.f_bavail * (uint64_t)v.f_frsize;
        }
#endif
        dlen = r36_mtp_put_u16(data, dlen, 0x0004u);
        dlen = r36_mtp_put_u16(data, dlen, 0x0002u);
        dlen = r36_mtp_put_u16(data, dlen, 0x0000u);
        dlen = r36_mtp_put_u64(data, dlen, total);
        dlen = r36_mtp_put_u64(data, dlen, freeb);
        dlen = r36_mtp_put_u32(data, dlen, 0xFFFFFFFFu);
        dlen = r36_mtp_put_str(data, dlen, "SD card");
        dlen = r36_mtp_put_str(data, dlen, "");
        if (r36_mtp_send_container(rt->fds.mtp_in, R36_MTP_CT_DATA, op, tid, data, (uint32_t)dlen) != 0)
            return -1;
        break;
    }
    case R36_MTP_OP_GetObjectHandles: {
        uint32_t sid = p[0], fmt = p[1], parent = (p[2] == 0u) ? R36_MTP_ROOT_HANDLE : p[2];
        if (sid != R36_MTP_STORAGE_ID && sid != 0xFFFFFFFFu) { rc = R36_MTP_RC_InvalidStorageID; break; }
        if (parent != R36_MTP_ROOT_HANDLE && (!r36_mtp_obj_valid(rt, parent) || !rt->objs[parent - 1u].is_dir)) {
            rc = R36_MTP_RC_InvalidParentObject;
            break;
        }
        char dir_path[512], child_path[1024];
        if (r36_mtp_obj_path(rt, parent, dir_path, sizeof(dir_path)) != 0) {
            rc = R36_MTP_RC_InvalidParentObject;
            break;
        }
        DIR *d = opendir(dir_path);
        if (!d) { rc = R36_MTP_RC_InvalidParentObject; break; }
        uint32_t handles[R36_MTP_MAX_OBJECTS];
        uint32_t count = 0;
        struct dirent *e;
        while ((e = readdir(d)) != NULL && count < R36_MTP_MAX_OBJECTS) {
            if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
            if (!r36_mtp_is_safe_name(e->d_name)) continue;
            snprintf(child_path, sizeof(child_path), "%s/%s", dir_path, e->d_name);
            struct stat st;
            if (stat(child_path, &st) != 0) continue;
            uint8_t is_dir = S_ISDIR(st.st_mode) ? 1u : 0u;
            uint32_t h = r36_mtp_find_or_add_obj(rt, parent, e->d_name, is_dir);
            if (!h) continue;
            uint16_t ofmt = is_dir ? R36_MTP_FMT_ASSOCIATION : R36_MTP_FMT_UNDEFINED;
            if (fmt == 0u || fmt == ofmt)
                handles[count++] = h;
        }
        closedir(d);
        uint32_t resp_len = 4u + count * 4u;
        uint8_t *hbuf = (uint8_t *)malloc(resp_len);
        if (!hbuf) return -1;
        r36_mtp_put_u32(hbuf, 0, count);
        for (uint32_t i = 0; i < count; i++)
            r36_mtp_put_u32(hbuf, 4u + i * 4u, handles[i]);
        int wr = r36_mtp_send_container(rt->fds.mtp_in, R36_MTP_CT_DATA, op, tid, hbuf, resp_len);
        free(hbuf);
        if (wr != 0) return -1;
        break;
    }
    case R36_MTP_OP_GetObjectInfo: {
        uint32_t h = p[0];
        char path[512];
        struct stat st;
        if (!r36_mtp_obj_valid(rt, h) || r36_mtp_obj_path(rt, h, path, sizeof(path)) != 0 || stat(path, &st) != 0) {
            rc = R36_MTP_RC_InvalidObjectHandle;
            break;
        }
        uint8_t is_dir = rt->objs[h - 1u].is_dir;
        uint32_t sz32 = is_dir ? 0u : ((uint64_t)st.st_size > 0xFFFFFFFFULL ? 0xFFFFFFFFu : (uint32_t)st.st_size);
        uint32_t par_out = (rt->objs[h - 1u].parent == R36_MTP_ROOT_HANDLE) ? 0u : rt->objs[h - 1u].parent;
        dlen = r36_mtp_put_u32(data, dlen, R36_MTP_STORAGE_ID);
        dlen = r36_mtp_put_u16(data, dlen, is_dir ? R36_MTP_FMT_ASSOCIATION : R36_MTP_FMT_UNDEFINED);
        dlen = r36_mtp_put_u16(data, dlen, 0u);
        dlen = r36_mtp_put_u32(data, dlen, sz32);
        dlen = r36_mtp_put_u16(data, dlen, 0u);
        for (int i = 0; i < 6; i++) dlen = r36_mtp_put_u32(data, dlen, 0u);
        dlen = r36_mtp_put_u32(data, dlen, par_out);
        dlen = r36_mtp_put_u16(data, dlen, is_dir ? 1u : 0u);
        dlen = r36_mtp_put_u32(data, dlen, 0u);
        dlen = r36_mtp_put_u32(data, dlen, 0u);
        dlen = r36_mtp_put_str(data, dlen, rt->objs[h - 1u].name);
        dlen = r36_mtp_put_str(data, dlen, "20261117T120000");
        dlen = r36_mtp_put_str(data, dlen, "20261117T120000");
        dlen = r36_mtp_put_str(data, dlen, "");
        if (r36_mtp_send_container(rt->fds.mtp_in, R36_MTP_CT_DATA, op, tid, data, (uint32_t)dlen) != 0)
            return -1;
        break;
    }
    case R36_MTP_OP_GetObject: {
        uint32_t sent_len = 0;
        rc = r36_mtp_send_file(rt, p[0], 0u, 0u, 0, op, tid, &sent_len);
        break;
    }
    case R36_MTP_OP_GetPartialObject: {
        uint32_t sent_len = 0;
        rc = r36_mtp_send_file(rt, p[0], (uint64_t)p[1], (uint64_t)p[2], 1, op, tid, &sent_len);
        if (rc == R36_MTP_RC_OK) { nr = 1; r0 = sent_len; }
        break;
    }
    case R36_MTP_OP_SendObjectInfo: {
        uint8_t *oi_pkt = NULL;
        uint32_t oi_total = 0;
        rt->send_pending = 0;
        if (r36_mtp_read_data_phase(rt->fds.mtp_out, &oi_pkt, &oi_total) != 0) {
            rc = R36_MTP_RC_IncompleteTransfer;
            break;
        }
        if (oi_total < 12u + 53u) {
            free(oi_pkt);
            rc = R36_MTP_RC_InvalidParameter;
            break;
        }
        const uint8_t *oi = oi_pkt + 12;
        uint16_t fmt = 0;
        uint32_t size = 0;
        char name[128];
        memcpy(&fmt, oi + 4, 2);
        memcpy(&size, oi + 8, 4);
        if (r36_mtp_get_str(oi + 52, oi_total - 12u - 52u, name, sizeof(name)) < 0 || !r36_mtp_is_safe_name(name)) {
            free(oi_pkt);
            rc = R36_MTP_RC_InvalidParameter;
            break;
        }
        free(oi_pkt);
        if (p[0] != R36_MTP_STORAGE_ID && p[0] != 0u) { rc = R36_MTP_RC_InvalidStorageID; break; }
        uint32_t par = (p[1] == 0u || p[1] == R36_MTP_ROOT_HANDLE) ? R36_MTP_ROOT_HANDLE : p[1];
        if (par != R36_MTP_ROOT_HANDLE && (!r36_mtp_obj_valid(rt, par) || !rt->objs[par - 1u].is_dir)) {
            rc = R36_MTP_RC_InvalidParentObject;
            break;
        }
        char dir_path[512], full_path[1024];
        if (r36_mtp_obj_path(rt, par, dir_path, sizeof(dir_path)) != 0) {
            rc = R36_MTP_RC_InvalidParentObject;
            break;
        }
        snprintf(full_path, sizeof(full_path), "%s/%s", dir_path, name);
        uint8_t is_dir = (fmt == R36_MTP_FMT_ASSOCIATION) ? 1u : 0u;
        if (is_dir && r36_mkdir_ok(full_path) != 0) {
            rc = R36_MTP_RC_AccessDenied;
            break;
        }
        uint32_t nh = r36_mtp_find_or_add_obj(rt, par, name, is_dir);
        if (!nh) { rc = R36_MTP_RC_GeneralError; break; }
        rt->send_parent = par;
        snprintf(rt->send_name, sizeof(rt->send_name), "%s", name);
        rt->send_size = size;
        rt->send_is_dir = is_dir;
        rt->send_handle = nh;
        rt->send_pending = is_dir ? 0 : 1;
        nr = 3;
        r0 = R36_MTP_STORAGE_ID;
        r1 = p[1];
        r2 = nh;
        break;
    }
    case R36_MTP_OP_SendObject: {
        char path[512];
        int ok = rt->send_pending && r36_mtp_obj_path(rt, rt->send_handle, path, sizeof(path)) == 0;
        FILE *fp = ok ? fopen(path, "wb") : NULL;
        uint8_t rx[512];
        ssize_t rn;
        do { rn = read(rt->fds.mtp_out, rx, sizeof(rx)); } while (rn == 0 || (rn < 0 && errno == EINTR));
        if (rn < 12) {
            if (fp) { fclose(fp); remove(path); }
            rt->send_pending = 0;
            rc = R36_MTP_RC_IncompleteTransfer;
            break;
        }
        uint32_t total = 0;
        memcpy(&total, rx, 4);
        uint64_t got = (uint64_t)rn;
        int werr = 0;
        if (fp && rn > 12) {
            size_t take = (got > total ? (size_t)total : (size_t)rn) - 12u;
            if (take > 0 && fwrite(rx + 12, 1, take, fp) != take) werr = 1;
        }
        while (got < total) {
            uint32_t want = (total - got) > sizeof(rx) ? (uint32_t)sizeof(rx) : (uint32_t)(total - got);
            rn = read(rt->fds.mtp_out, rx, want);
            if (rn < 0 && errno == EINTR) continue;
            if (rn <= 0) break;
            got += (uint64_t)rn;
            if (fp && !werr) {
                if (fwrite(rx, 1, (size_t)rn, fp) != (size_t)rn) werr = 1;
            }
        }
        if (fp) fclose(fp);
        rt->send_pending = 0;
        if (!ok) { rc = R36_MTP_RC_NoValidObjectInfo; break; }
        if (!fp) { rc = R36_MTP_RC_AccessDenied; break; }
        if (got < total || werr) {
            remove(path);
            r36_mtp_mark_deleted(rt, rt->send_handle);
            rc = R36_MTP_RC_IncompleteTransfer;
            break;
        }
        break;
    }
    case R36_MTP_OP_DeleteObject: {
        uint32_t h = p[0];
        char path[512];
        if (h == R36_MTP_ROOT_HANDLE) { rc = R36_MTP_RC_AccessDenied; break; }
        if (!r36_mtp_obj_valid(rt, h) || r36_mtp_obj_path(rt, h, path, sizeof(path)) != 0) {
            rc = R36_MTP_RC_InvalidObjectHandle;
            break;
        }
        if (remove(path) != 0) {
            rc = R36_MTP_RC_AccessDenied;
            break;
        }
        r36_mtp_mark_deleted(rt, h);
        break;
    }
    case R36_MTP_OP_TF_Info: {
        static const char info[] = "tfmtp-ffs 1.0 remote=1\n";
        if (r36_mtp_send_container(rt->fds.mtp_in, R36_MTP_CT_DATA, op, tid, info, (uint32_t)(sizeof(info) - 1u)) != 0)
            return -1;
        break;
    }
    default:
        rc = R36_MTP_RC_OperationNotSupported;
        break;
    }

    if (r36_mtp_send_response(rt->fds.mtp_in, rc, tid, nr, r0, r1, r2) != 0)
        return -1;
    rt->mtp_commands_handled++;
    return 0;
}

/* ADB packet TX over FunctionFS: 24-byte header and payload are separate USB bulk writes */
static int r36_adb_send_packet(int ep_in, const struct r36_adb_msg *msg, const void *payload)
{
    if (r36_write_all_fd(ep_in, msg, sizeof(*msg)) != 0)
        return -1;
    if (msg->data_length > 0 && payload) {
        if (r36_write_all_fd(ep_in, payload, msg->data_length) != 0)
            return -1;
    }
    return 0;
}

/* Handle one ADB packet (header + optional payload) on /dev/ffs-adb/ep2 -> ep1,
 * supporting CNXN, shell:<cmd>, and sync: (STAT / QUIT).
 */
typedef int (*r36_shell_exec_fn)(const char *cmd, char *out, size_t cap);

static int r36_adb_resolve_sync_path(const struct r36_mtp_adb_runtime *rt,
                                     const uint8_t *raw_path, size_t path_len,
                                     char *out, size_t cap)
{
    char rel[384];
    if (path_len == 0 || path_len >= sizeof(rel)) return -1;
    memcpy(rel, raw_path, path_len);
    rel[path_len] = 0;
    /* Strip optional ",<mode>" suffix used by ADB SEND */
    char *comma = strrchr(rel, ',');
    if (comma) *comma = 0;
    if (strstr(rel, "..")) return -1;
    if (rt->adb_sync_root[0]) {
        int n = snprintf(out, cap, "%s/%s", rt->adb_sync_root, rel[0] == '/' ? rel + 1 : rel);
        return (n > 0 && (size_t)n < cap) ? 0 : -1;
    }
    int n = snprintf(out, cap, "%s", rel);
    return (n > 0 && (size_t)n < cap) ? 0 : -1;
}

static int r36_adb_process_one(struct r36_mtp_adb_runtime *rt,
                               const struct r36_adb_msg *in_msg, const uint8_t *in_payload,
                               r36_shell_exec_fn shell_cb)
{
    struct r36_adb_msg out_msg;
    uint8_t out_payload[R36_ADB_MAXDATA];

    if (r36_adb_validate(in_msg, in_payload) != 0)
        return -1;

    if (in_msg->command == R36_ADB_CNXN) {
        if (r36_adb_handle_packet(&rt->adb, in_msg, in_payload, &out_msg, out_payload, sizeof(out_payload)) != 1)
            return -1;
        rt->adb_sync_mode = 0;
        rt->adb_send_active = 0;
        rt->adb_pending_close = 0;
        rt->adb_pending_len = 0;
        if (r36_adb_send_packet(rt->fds.adb_in, &out_msg, out_payload) != 0)
            return -1;
        rt->adb_packets_handled++;
        return 0;
    }

    if (!rt->adb.connected)
        return -1;

    if (in_msg->command == R36_ADB_OPEN) {
        char service[256];
        size_t slen = in_msg->data_length < sizeof(service) - 1 ? in_msg->data_length : sizeof(service) - 1;
        memcpy(service, in_payload, slen);
        service[slen] = 0;

        if (r36_adb_handle_packet(&rt->adb, in_msg, in_payload, &out_msg, out_payload, sizeof(out_payload)) != 1)
            return -1;
        /* Send A_OKAY first */
        if (r36_adb_send_packet(rt->fds.adb_in, &out_msg, NULL) != 0)
            return -1;

        if (!strncmp(service, "shell:", 6)) {
            char reply[1024] = {0};
            const char *cmd = service + 6;
            int rlen = shell_cb ? shell_cb(cmd, reply, sizeof(reply) - 1) : snprintf(reply, sizeof(reply), "OK:%s\n", cmd);
            if (rlen < 0) rlen = 0;
            rt->adb_sync_mode = 0;
            rt->adb_send_active = 0;
            rt->adb_pending_close = 1;
            r36_adb_pack(&out_msg, R36_ADB_WRTE, rt->adb.local_id, rt->adb.remote_id, reply, (uint32_t)rlen);
            if (r36_adb_send_packet(rt->fds.adb_in, &out_msg, reply) != 0)
                return -1;
        } else if (!strcmp(service, "sync:")) {
            rt->adb_sync_mode = 1;
            rt->adb_send_active = 0;
            rt->adb_pending_close = 0;
        }
        rt->adb_packets_handled++;
        return 0;
    }

    if (in_msg->command == R36_ADB_OKAY) {
        if (rt->adb_pending_close && rt->adb.stream_open) {
            rt->adb_pending_close = 0;
            rt->adb.stream_open = 0;
            r36_adb_pack(&out_msg, R36_ADB_CLSE, rt->adb.local_id, rt->adb.remote_id, NULL, 0);
            if (r36_adb_send_packet(rt->fds.adb_in, &out_msg, NULL) != 0)
                return -1;
        }
        rt->adb_packets_handled++;
        return 0;
    }

    if (in_msg->command == R36_ADB_WRTE) {
        if (r36_adb_handle_packet(&rt->adb, in_msg, in_payload, &out_msg, out_payload, sizeof(out_payload)) != 1)
            return -1;
        /* Acknowledge host's WRTE with A_OKAY */
        if (r36_adb_send_packet(rt->fds.adb_in, &out_msg, NULL) != 0)
            return -1;

        if (rt->adb_sync_mode && in_msg->data_length >= 8) {
            uint32_t arg_len = 0;
            memcpy(&arg_len, in_payload + 4, 4);
            if (!memcmp(in_payload, "STAT", 4) && 8u + arg_len <= in_msg->data_length) {
                char path[512];
                uint8_t stat_resp[16];
                uint32_t mode = 0, size = 0, mtime = 0;
                if (r36_adb_resolve_sync_path(rt, in_payload + 8, arg_len, path, sizeof(path)) == 0) {
                    FILE *fp = fopen(path, "rb");
                    if (fp) {
                        if (fseek(fp, 0, SEEK_END) == 0) {
                            long pos = ftell(fp);
                            if (pos >= 0) size = (uint32_t)pos;
                        }
                        fclose(fp);
                        mode = 0100644u;
                        mtime = 1700000000u;
                    }
                }
                memcpy(stat_resp + 0, "STAT", 4);
                memcpy(stat_resp + 4, &mode, 4);
                memcpy(stat_resp + 8, &size, 4);
                memcpy(stat_resp + 12, &mtime, 4);
                r36_adb_pack(&out_msg, R36_ADB_WRTE, rt->adb.local_id, rt->adb.remote_id, stat_resp, sizeof(stat_resp));
                if (r36_adb_send_packet(rt->fds.adb_in, &out_msg, stat_resp) != 0)
                    return -1;
            } else if (!memcmp(in_payload, "RECV", 4) && 8u + arg_len <= in_msg->data_length) {
                /* adb pull: stream DATA + len + bytes, then DONE + 0 */
                char path[512];
                FILE *fp = NULL;
                if (r36_adb_resolve_sync_path(rt, in_payload + 8, arg_len, path, sizeof(path)) == 0)
                    fp = fopen(path, "rb");
                if (!fp) {
                    uint8_t fail_pkt[12];
                    uint32_t flen = 4;
                    memcpy(fail_pkt + 0, "FAIL", 4);
                    memcpy(fail_pkt + 4, &flen, 4);
                    memcpy(fail_pkt + 8, "ENOENT", 4);
                    r36_adb_pack(&out_msg, R36_ADB_WRTE, rt->adb.local_id, rt->adb.remote_id, fail_pkt, sizeof(fail_pkt));
                    if (r36_adb_send_packet(rt->fds.adb_in, &out_msg, fail_pkt) != 0)
                        return -1;
                } else {
                    uint8_t sync_pkt[2048 + 16];
                    size_t nread = fread(sync_pkt + 8, 1, 2048, fp);
                    fclose(fp);
                    uint32_t clen = (uint32_t)nread, zero = 0;
                    memcpy(sync_pkt + 0, "DATA", 4);
                    memcpy(sync_pkt + 4, &clen, 4);
                    memcpy(sync_pkt + 8 + nread, "DONE", 4);
                    memcpy(sync_pkt + 12 + nread, &zero, 4);
                    r36_adb_pack(&out_msg, R36_ADB_WRTE, rt->adb.local_id, rt->adb.remote_id,
                                 sync_pkt, (uint32_t)(16 + nread));
                    if (r36_adb_send_packet(rt->fds.adb_in, &out_msg, sync_pkt) != 0)
                        return -1;
                }
            } else if (!memcmp(in_payload, "SEND", 4) && 8u + arg_len <= in_msg->data_length) {
                /* adb push start: "SEND" + path_len + "<path>,<mode>" (optionally followed by DATA/DONE in same WRTE) */
                if (r36_adb_resolve_sync_path(rt, in_payload + 8, arg_len, rt->adb_send_path, sizeof(rt->adb_send_path)) != 0)
                    return -1;
                rt->adb_send_len = 0;
                rt->adb_send_active = 1;
                size_t pos = 8u + arg_len;
                while (pos + 8u <= in_msg->data_length) {
                    uint32_t sub_len = 0;
                    memcpy(&sub_len, in_payload + pos + 4, 4);
                    if (!memcmp(in_payload + pos, "DATA", 4) && pos + 8u + sub_len <= in_msg->data_length) {
                        if (rt->adb_send_len + sub_len > sizeof(rt->adb_send_buf)) return -1;
                        memcpy(rt->adb_send_buf + rt->adb_send_len, in_payload + pos + 8, sub_len);
                        rt->adb_send_len += sub_len;
                        pos += 8u + sub_len;
                    } else if (!memcmp(in_payload + pos, "DONE", 4)) {
                        FILE *fp = fopen(rt->adb_send_path, "wb");
                        if (!fp || fwrite(rt->adb_send_buf, 1, rt->adb_send_len, fp) != rt->adb_send_len) {
                            if (fp) fclose(fp);
                            return -1;
                        }
                        fclose(fp);
                        rt->adb_send_active = 0;
                        uint8_t okay_resp[8] = { 'O', 'K', 'A', 'Y', 0, 0, 0, 0 };
                        r36_adb_pack(&out_msg, R36_ADB_WRTE, rt->adb.local_id, rt->adb.remote_id, okay_resp, sizeof(okay_resp));
                        if (r36_adb_send_packet(rt->fds.adb_in, &out_msg, okay_resp) != 0)
                            return -1;
                        break;
                    } else {
                        break;
                    }
                }
            } else if (!memcmp(in_payload, "QUIT", 4)) {
                rt->adb_sync_mode = 0;
                rt->adb_send_active = 0;
                rt->adb.stream_open = 0;
                r36_adb_pack(&out_msg, R36_ADB_CLSE, rt->adb.local_id, rt->adb.remote_id, NULL, 0);
                if (r36_adb_send_packet(rt->fds.adb_in, &out_msg, NULL) != 0)
                    return -1;
            }
        }
        rt->adb_packets_handled++;
        return 0;
    }

    if (in_msg->command == R36_ADB_CLSE) {
        if (r36_adb_handle_packet(&rt->adb, in_msg, in_payload, &out_msg, out_payload, sizeof(out_payload)) != 1)
            return -1;
        rt->adb_sync_mode = 0;
        rt->adb_send_active = 0;
        rt->adb_pending_close = 0;
        if (r36_adb_send_packet(rt->fds.adb_in, &out_msg, NULL) != 0)
            return -1;
        rt->adb_packets_handled++;
        return 0;
    }

    return -1;
}

/* Multiplexed poll step servicing both MTP (ep2->ep1) and ADB (ep2->ep1) concurrently */
static int r36_mtp_adb_poll_once(struct r36_mtp_adb_runtime *rt, int timeout_ms, r36_shell_exec_fn shell_cb)
{
    struct pollfd pfds[2] = {
        { .fd = rt->fds.mtp_out, .events = POLLIN, .revents = 0 },
        { .fd = rt->fds.adb_out, .events = POLLIN, .revents = 0 },
    };
    int ready = poll(pfds, 2, timeout_ms);
    if (ready <= 0)
        return ready;

    if (pfds[0].revents & POLLIN) {
        uint8_t mtp_rx[512];
        ssize_t n = read(rt->fds.mtp_out, mtp_rx, sizeof(mtp_rx));
        if (n < 0 || r36_mtp_handle_one(rt, mtp_rx, (size_t)n) != 0)
            return -1;
    }
    if (pfds[1].revents & POLLIN) {
        struct r36_adb_msg hdr;
        uint8_t payload[R36_ADB_MAXDATA];
        ssize_t n = read(rt->fds.adb_out, &hdr, sizeof(hdr));
        if (n != (ssize_t)sizeof(hdr) || hdr.data_length > R36_ADB_MAXDATA)
            return -1;
        if (hdr.data_length > 0) {
            ssize_t pn = read(rt->fds.adb_out, payload, hdr.data_length);
            if (pn != (ssize_t)hdr.data_length)
                return -1;
        }
        if (r36_adb_process_one(rt, &hdr, hdr.data_length ? payload : NULL, shell_cb) != 0)
            return -1;
    }
    return ready;
}

#ifndef R36_USB_MTP_ADB_LIBRARY_ONLY
static int default_shell_cb(const char *cmd, char *out, size_t cap)
{
    return snprintf(out, cap, "r36s:%s\n", cmd);
}

int main(void)
{
    struct r36_mtp_adb_runtime rt;
    memset(&rt, 0, sizeof(rt));
    r36_init_composite_fds(&rt.fds);
    rt.mtp_legacy_fd = -1;
    snprintf(rt.mtp_root, sizeof(rt.mtp_root), "/mnt/sdcard");
    if (r36_setup_mtp_adb_gadget(&rt.fds) != 0)
        r36_init_composite_fds(&rt.fds);
    if (r36_open_mtp_transport(&rt) < 0 && rt.fds.adb_ep0 < 0) {
        r36_teardown_mtp_adb_gadget(&rt.fds);
        return 1;
    }
    for (unsigned int i = 0; i < 100; i++) {
        if (r36_mtp_adb_poll_once(&rt, 100, default_shell_cb) < 0)
            break;
    }
    r36_close_mtp_transport(&rt);
    r36_teardown_mtp_adb_gadget(&rt.fds);
    return 0;
}
#endif
