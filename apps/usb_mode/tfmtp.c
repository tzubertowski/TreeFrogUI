// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Pavel Kotek
/*
 * tfmtp - lazy MTP responder for TreeFrogUI on HiChip HC16xx handhelds.
 *
 * Drop-in replacement for cubegm/mtp-server:  tfmtp <root>   (root = /mnt/sdcard)
 * Talks to the Android-style f_mtp gadget function through /dev/mtp_usb.
 *
 * Unlike the stock responder it does NOT index the card up front: an object
 * handle is assigned only when the PC lists the folder that contains it, so
 * it answers the PC immediately no matter how many files the card holds.
 *
 * Log: every operation goes to stderr ("TFMTP <uptime> ..."), which
 * usb_mode.sh redirects to /mnt/sdcard/log.txt when that file exists.
 *
 * Build (device):  zig cc -target mipsel-linux-musleabi -mcpu=mips32 -static -Os -s -o tfmtp tfmtp.c
 * Build (PC test): zig cc -DTFMTP_TEST -o tfmtp_test.exe tfmtp.c   (runs a scripted session)
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <time.h>
#include <dirent.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#ifndef TFMTP_TEST
#include <sys/ioctl.h>
#include <sys/statvfs.h>
#include <sys/wait.h>
#include <signal.h>
#include <poll.h>
#include <sched.h>
#include <sys/syscall.h>
#include <sys/resource.h>
#endif

#ifdef _WIN32
#include <io.h>
#include <direct.h>
#define mkdir(p, m) _mkdir(p)
#ifndef O_BINARY
#define O_BINARY 0
#endif
#else
#define O_BINARY 0
#endif

/* ------------------------------------------------------------------ */
/* MTP constants                                                       */
/* ------------------------------------------------------------------ */
#define CT_COMMAND  1
#define CT_DATA     2
#define CT_RESPONSE 3

#define OP_GetDeviceInfo            0x1001
#define OP_OpenSession              0x1002
#define OP_CloseSession             0x1003
#define OP_GetStorageIDs            0x1004
#define OP_GetStorageInfo           0x1005
#define OP_GetNumObjects            0x1006
#define OP_GetObjectHandles         0x1007
#define OP_GetObjectInfo            0x1008
#define OP_GetObject                0x1009
#define OP_DeleteObject             0x100B
#define OP_SendObjectInfo           0x100C
#define OP_SendObject               0x100D
#define OP_GetDevicePropDesc        0x1014
#define OP_GetDevicePropValue       0x1015
#define OP_GetPartialObject         0x101B
#define OP_GetObjectPropsSupported  0x9801
#define OP_GetObjectPropDesc        0x9802
#define OP_GetObjectPropValue       0x9803
#define OP_SetObjectPropValue       0x9804
#define OP_GetObjectPropList        0x9805
#define OP_GetObjectReferences      0x9810
/* vendor extension: remote shell (only when <root>/cubegm/tfmtp.remote exists) */
#define OP_TF_Info                  0x9A00
#define OP_TF_Exec                  0x9A01
#define OP_TF_Read                  0x9A02
#define OP_TF_Write                 0x9A03
#define OP_TF_Signal                0x9A04

#define RC_OK                       0x2001
#define RC_GeneralError             0x2002
#define RC_SessionNotOpen           0x2003
#define RC_OperationNotSupported    0x2005
#define RC_IncompleteTransfer       0x2007
#define RC_InvalidStorageID         0x2008
#define RC_InvalidObjectHandle      0x2009
#define RC_DevicePropNotSupported   0x200A
#define RC_StoreFull                0x200C
#define RC_AccessDenied             0x200F
#define RC_PartialDeletion          0x2012
#define RC_NoValidObjectInfo        0x2015
#define RC_InvalidParentObject      0x201A
#define RC_InvalidParameter         0x201D
#define RC_SessionAlreadyOpen       0x201E
#define RC_TransactionCancelled     0x201F
#define RC_InvalidObjectPropCode    0xA801
#define RC_InvalidObjectPropValue   0xA803
#define RC_GroupUnsupported         0xA805
#define RC_DepthUnsupported         0xA808
#define RC_ObjectPropNotSupported   0xA80A

#define FMT_UNDEFINED   0x3000
#define FMT_ASSOCIATION 0x3001

#define DT_U16  0x0004
#define DT_U32  0x0006
#define DT_U64  0x0008
#define DT_U128 0x000A
#define DT_STR  0xFFFF

#define PROP_StorageID        0xDC01
#define PROP_ObjectFormat     0xDC02
#define PROP_ProtectionStatus 0xDC03
#define PROP_ObjectSize       0xDC04
#define PROP_ObjectFileName   0xDC07
#define PROP_DateCreated      0xDC08
#define PROP_DateModified     0xDC09
#define PROP_ParentObject     0xDC0B
#define PROP_PersistentUID    0xDC41
#define PROP_Name             0xDC44

#define DEVPROP_FriendlyName  0xD402

#define STORAGE_ID 0x00010001u
#define ROOT       0xFFFFFFFFu
#define BUFSZ      16384

static const uint16_t g_ops[] = {
    OP_GetDeviceInfo, OP_OpenSession, OP_CloseSession, OP_GetStorageIDs, OP_GetStorageInfo,
    OP_GetNumObjects, OP_GetObjectHandles, OP_GetObjectInfo, OP_GetObject, OP_DeleteObject,
    OP_SendObjectInfo, OP_SendObject, OP_GetDevicePropDesc, OP_GetDevicePropValue,
    OP_GetPartialObject, OP_GetObjectPropsSupported, OP_GetObjectPropDesc, OP_GetObjectPropValue,
    OP_SetObjectPropValue, OP_GetObjectPropList, OP_GetObjectReferences };
static const uint16_t g_remote_ops[] = { OP_TF_Info, OP_TF_Exec, OP_TF_Read, OP_TF_Write, OP_TF_Signal };
static int g_remote;            /* remote shell enabled */
static const uint16_t g_formats[] = {
    FMT_UNDEFINED, FMT_ASSOCIATION, 0x3004 /*text*/, 0x3008 /*wav*/, 0x3009 /*mp3*/,
    0x300A /*avi*/, 0x3801 /*jpeg*/, 0x3804 /*bmp*/, 0x3807 /*gif*/, 0x380B /*png*/,
    0xB982 /*mp4*/ };
static const uint16_t g_props[] = {
    PROP_StorageID, PROP_ObjectFormat, PROP_ProtectionStatus, PROP_ObjectSize,
    PROP_ObjectFileName, PROP_DateCreated, PROP_DateModified, PROP_ParentObject,
    PROP_PersistentUID, PROP_Name };
#define NELEM(a) (sizeof(a) / sizeof((a)[0]))

/* ------------------------------------------------------------------ */
/* logging                                                             */
/* ------------------------------------------------------------------ */
static double now_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}
static void L(const char *fmt, ...) {
    va_list ap;
    fprintf(stderr, "TFMTP %9.3f ", now_s());
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fputc('\n', stderr);
    fflush(stderr);
}

static const char *op_name(uint16_t op) {
    switch (op) {
    case OP_GetDeviceInfo: return "GetDeviceInfo";       case OP_OpenSession: return "OpenSession";
    case OP_CloseSession: return "CloseSession";         case OP_GetStorageIDs: return "GetStorageIDs";
    case OP_GetStorageInfo: return "GetStorageInfo";     case OP_GetNumObjects: return "GetNumObjects";
    case OP_GetObjectHandles: return "GetObjectHandles"; case OP_GetObjectInfo: return "GetObjectInfo";
    case OP_GetObject: return "GetObject";               case OP_DeleteObject: return "DeleteObject";
    case OP_SendObjectInfo: return "SendObjectInfo";     case OP_SendObject: return "SendObject";
    case OP_GetDevicePropDesc: return "GetDevicePropDesc"; case OP_GetDevicePropValue: return "GetDevicePropValue";
    case OP_GetPartialObject: return "GetPartialObject"; case OP_GetObjectPropsSupported: return "GetObjectPropsSupported";
    case OP_GetObjectPropDesc: return "GetObjectPropDesc"; case OP_GetObjectPropValue: return "GetObjectPropValue";
    case OP_SetObjectPropValue: return "SetObjectPropValue"; case OP_GetObjectPropList: return "GetObjectPropList";
    case OP_GetObjectReferences: return "GetObjectReferences";
    case OP_TF_Info: return "TF_Info";   case OP_TF_Exec: return "TF_Exec";   case OP_TF_Read: return "TF_Read";
    case OP_TF_Write: return "TF_Write"; case OP_TF_Signal: return "TF_Signal";
    default: return "?";
    }
}

/* ------------------------------------------------------------------ */
/* transport: /dev/mtp_usb (device) or an in-memory fake (PC test)     */
/* ------------------------------------------------------------------ */
struct mtp_file_range {          /* <linux/usb/f_mtp.h>; 32 bytes on MIPS o32 */
    int fd;
    long long offset;
    long long length;
    uint16_t command;
    uint32_t transaction_id;
};

#ifndef TFMTP_TEST
#define MTP_RECEIVE_FILE          _IOW('M', 1, struct mtp_file_range)
#define MTP_SEND_FILE_WITH_HEADER _IOW('M', 4, struct mtp_file_range)
_Static_assert(sizeof(struct mtp_file_range) == 32, "mtp_file_range must match the kernel (32 bytes)");
static int g_usb = -1;
static int usb_read(void *buf, size_t n) { return (int)read(g_usb, buf, n); }
static int usb_write(const void *buf, size_t n) {
    const uint8_t *p = buf;
    size_t done = 0;
    while (done < n) {
        ssize_t r = write(g_usb, p + done, n - done);
        if (r < 0) { if (errno == EINTR) continue; return -1; }
        if (r == 0) return -1;
        done += (size_t)r;
    }
    return (int)done;
}
static int usb_send_file(int fd, long long off, long long len, uint16_t op, uint32_t tid) {
    struct mtp_file_range r;
    memset(&r, 0, sizeof r);
    r.fd = fd; r.offset = off; r.length = len; r.command = op; r.transaction_id = tid;
    return ioctl(g_usb, MTP_SEND_FILE_WITH_HEADER, &r);
}
#else
/* fake USB: queue of host->device packets, captured device->host bytes */
static uint8_t *t_in[64]; static int t_inlen[64], t_inhead, t_intail;
static uint8_t t_out[4 << 20]; static size_t t_outlen;
static int usb_read(void *buf, size_t n) {
    if (t_inhead == t_intail) { errno = EIO; return -1; }
    int l = t_inlen[t_inhead];
    if ((size_t)l > n) l = (int)n;
    memcpy(buf, t_in[t_inhead], l);
    free(t_in[t_inhead]);
    t_inhead++;
    return l;
}
static int usb_write(const void *buf, size_t n) {
    memcpy(t_out + t_outlen, buf, n); t_outlen += n; return (int)n;
}
static int usb_send_file(int fd, long long off, long long len, uint16_t op, uint32_t tid) {
    uint8_t h[12]; uint32_t tl = (uint32_t)(len + 12);
    memcpy(h, &tl, 4); h[4] = CT_DATA; h[5] = 0; memcpy(h + 6, &op, 2); memcpy(h + 8, &tid, 4);
    usb_write(h, 12);
    lseek(fd, (long)off, SEEK_SET);
    long long left = len; uint8_t b[4096];
    while (left > 0) { int r = read(fd, b, left > 4096 ? 4096 : (int)left); if (r <= 0) return -1; usb_write(b, r); left -= r; }
    return 0;
}
#endif

/* ------------------------------------------------------------------ */
/* object table: handles are assigned lazily when a folder is listed   */
/* ------------------------------------------------------------------ */
typedef struct {
    uint32_t parent;     /* ROOT for top-level objects */
    uint32_t hnext;      /* hash chain */
    char *name;
    uint8_t isdir, deleted;
} obj_t;

static const char *g_root = "/mnt/sdcard";
static obj_t *g_obj;
static uint32_t g_nobj = 1, g_capobj;    /* handle 0 is never used */
#define HBITS 15
static uint32_t g_hash[1u << HBITS];

static uint32_t hkey(uint32_t parent, const char *name) {
    uint32_t h = 2166136261u ^ parent;
    for (; *name; name++) { h ^= (uint8_t)*name; h *= 16777619u; }
    return h & ((1u << HBITS) - 1);
}
static uint32_t obj_find(uint32_t parent, const char *name) {
    for (uint32_t i = g_hash[hkey(parent, name)]; i; i = g_obj[i].hnext)
        if (g_obj[i].parent == parent && !g_obj[i].deleted && !strcmp(g_obj[i].name, name)) return i;
    return 0;
}
static void hash_unlink(uint32_t h) {
    uint32_t *pp = &g_hash[hkey(g_obj[h].parent, g_obj[h].name)];
    while (*pp && *pp != h) pp = &g_obj[*pp].hnext;
    if (*pp == h) *pp = g_obj[h].hnext;
    g_obj[h].hnext = 0;
}
static uint32_t obj_add(uint32_t parent, const char *name, int isdir) {
    uint32_t f = obj_find(parent, name);
    if (f) { g_obj[f].isdir = (uint8_t)isdir; return f; }
    if (g_nobj >= g_capobj) {
        uint32_t nc = g_capobj ? g_capobj * 2 : 4096;
        obj_t *n = realloc(g_obj, nc * sizeof(obj_t));
        if (!n) return 0;
        g_obj = n; g_capobj = nc;
    }
    uint32_t i = g_nobj++;
    uint32_t k = hkey(parent, name);
    g_obj[i].parent = parent; g_obj[i].name = strdup(name);
    g_obj[i].isdir = (uint8_t)isdir; g_obj[i].deleted = 0;
    g_obj[i].hnext = g_hash[k]; g_hash[k] = i;
    return i;
}
static int obj_valid(uint32_t h) { return h > 0 && h < g_nobj && !g_obj[h].deleted; }

/* full path of an object (or of ROOT); -1 if invalid */
static int obj_path(uint32_t h, char *out, size_t n) {
    uint32_t chain[64]; int d = 0;
    while (h != ROOT) {
        if (!obj_valid(h) || d >= 64) return -1;
        chain[d++] = h; h = g_obj[h].parent;
    }
    size_t len = (size_t)snprintf(out, n, "%s", g_root);
    for (int i = d - 1; i >= 0; i--) {
        len += (size_t)snprintf(out + len, n - len, "/%s", g_obj[chain[i]].name);
        if (len >= n) return -1;
    }
    return 0;
}

static int path_isdir(const char *p) { struct stat st; return stat(p, &st) == 0 && S_ISDIR(st.st_mode); }

/* list a folder: returns malloc'd array of child handles */
static uint32_t *list_children(uint32_t parent, uint32_t *count) {
    char path[1024], cp[1280];
    uint32_t *v = NULL, n = 0, cap = 0;
    *count = 0;
    if (obj_path(parent, path, sizeof path) < 0) return NULL;
    DIR *d = opendir(path);
    if (!d) return NULL;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        const char *nm = e->d_name;
        if (!strcmp(nm, ".") || !strcmp(nm, "..")) continue;
        if (parent == ROOT && !strcmp(nm, "System Volume Information")) continue;
        int isdir;
#if defined(DT_DIR) && !defined(_WIN32)
        if (e->d_type == DT_DIR) isdir = 1;
        else if (e->d_type != DT_UNKNOWN) isdir = 0;
        else
#endif
        { snprintf(cp, sizeof cp, "%s/%s", path, nm); isdir = path_isdir(cp); }
        uint32_t h = obj_add(parent, nm, isdir);
        if (!h) continue;
        if (n >= cap) { cap = cap ? cap * 2 : 256; uint32_t *nv = realloc(v, cap * 4); if (!nv) break; v = nv; }
        v[n++] = h;
    }
    closedir(d);
    *count = n;
    return v ? v : malloc(4);
}

/* ------------------------------------------------------------------ */
/* outgoing data builder                                               */
/* ------------------------------------------------------------------ */
static uint8_t *g_tx; static size_t g_txlen, g_txcap;
static void tx_need(size_t n) {
    if (g_txlen + n <= g_txcap) return;
    size_t nc = g_txcap ? g_txcap : 65536;
    while (g_txlen + n > nc) nc *= 2;
    uint8_t *p = realloc(g_tx, nc);
    if (!p) { L("FATAL out of memory (%zu bytes)", nc); exit(3); }
    g_tx = p; g_txcap = nc;
}
static void p8(uint8_t v)   { tx_need(1); g_tx[g_txlen++] = v; }
static void p16(uint16_t v) { tx_need(2); g_tx[g_txlen++] = (uint8_t)v; g_tx[g_txlen++] = (uint8_t)(v >> 8); }
static void p32(uint32_t v) { p16((uint16_t)v); p16((uint16_t)(v >> 16)); }
static void p64(uint64_t v) { p32((uint32_t)v); p32((uint32_t)(v >> 32)); }
static void parr16(const uint16_t *a, uint32_t n) { p32(n); for (uint32_t i = 0; i < n; i++) p16(a[i]); }

/* UTF-8 -> MTP string (u8 count incl. NUL, UTF-16LE) */
static void pstr(const char *s) {
    uint16_t u[256]; int n = 0;
    const uint8_t *p = (const uint8_t *)s;
    while (*p && n < 250) {
        uint32_t c;
        if (*p < 0x80) c = *p++;
        else if ((*p & 0xE0) == 0xC0 && p[1]) { c = ((p[0] & 0x1F) << 6) | (p[1] & 0x3F); p += 2; }
        else if ((*p & 0xF0) == 0xE0 && p[1] && p[2]) { c = ((p[0] & 0x0F) << 12) | ((p[1] & 0x3F) << 6) | (p[2] & 0x3F); p += 3; }
        else if ((*p & 0xF8) == 0xF0 && p[1] && p[2] && p[3]) {
            c = ((p[0] & 0x07) << 18) | ((p[1] & 0x3F) << 12) | ((p[2] & 0x3F) << 6) | (p[3] & 0x3F); p += 4;
        } else { c = '?'; p++; }
        if (c >= 0x10000) { c -= 0x10000; u[n++] = (uint16_t)(0xD800 | (c >> 10)); u[n++] = (uint16_t)(0xDC00 | (c & 0x3FF)); }
        else u[n++] = (uint16_t)c;
    }
    if (n == 0) { p8(0); return; }
    p8((uint8_t)(n + 1));
    for (int i = 0; i < n; i++) p16(u[i]);
    p16(0);
}

/* MTP string at buf (len bytes available) -> UTF-8; returns bytes consumed or -1 */
static int gstr(const uint8_t *buf, size_t len, char *out, size_t outn) {
    if (len < 1) return -1;
    int n = buf[0]; size_t need = 1 + (size_t)n * 2; size_t o = 0;
    if (len < need) return -1;
    for (int i = 0; i < n; i++) {
        uint32_t c = buf[1 + 2 * i] | (buf[2 + 2 * i] << 8);
        if (c == 0) break;
        if (c >= 0xD800 && c < 0xDC00 && i + 1 < n) {
            uint32_t c2 = buf[3 + 2 * i] | (buf[4 + 2 * i] << 8);
            c = 0x10000 + ((c - 0xD800) << 10) + (c2 - 0xDC00); i++;
        }
        if (o + 5 >= outn) break;
        if (c < 0x80) out[o++] = (char)c;
        else if (c < 0x800) { out[o++] = (char)(0xC0 | (c >> 6)); out[o++] = (char)(0x80 | (c & 0x3F)); }
        else if (c < 0x10000) { out[o++] = (char)(0xE0 | (c >> 12)); out[o++] = (char)(0x80 | ((c >> 6) & 0x3F)); out[o++] = (char)(0x80 | (c & 0x3F)); }
        else { out[o++] = (char)(0xF0 | (c >> 18)); out[o++] = (char)(0x80 | ((c >> 12) & 0x3F)); out[o++] = (char)(0x80 | ((c >> 6) & 0x3F)); out[o++] = (char)(0x80 | (c & 0x3F)); }
    }
    out[o] = 0;
    return (int)need;
}

static uint16_t g_curop; static uint32_t g_curtid;
static void data_begin(void) { g_txlen = 0; tx_need(12); g_txlen = 12; }
static int data_send(void) {
    uint32_t l = (uint32_t)g_txlen;
    memcpy(g_tx, &l, 4); g_tx[4] = CT_DATA; g_tx[5] = 0;
    memcpy(g_tx + 6, &g_curop, 2); memcpy(g_tx + 8, &g_curtid, 4);
    int r = usb_write(g_tx, g_txlen);
    if (r < 0) L("  data write failed: %s", strerror(errno));
    return r;
}
static void respond(uint16_t code, int np, uint32_t a, uint32_t b, uint32_t c) {
    uint8_t r[24]; uint32_t l = 12 + 4 * (uint32_t)np, pr[3] = { a, b, c };
    memcpy(r, &l, 4); r[4] = CT_RESPONSE; r[5] = 0;
    memcpy(r + 6, &code, 2); memcpy(r + 8, &g_curtid, 4);
    for (int i = 0; i < np; i++) memcpy(r + 12 + 4 * i, &pr[i], 4);
    if (usb_write(r, l) < 0) L("  response write failed: %s", strerror(errno));
}

/* read a whole host->device data phase into memory (small payloads only) */
static uint8_t g_rx[BUFSZ];
static uint8_t *read_data(uint32_t *plen) {
    int n;
    do { n = usb_read(g_rx, BUFSZ); } while (n == 0 || (n < 0 && errno == EINTR));
    if (n < 12) { L("  data phase read failed n=%d errno=%d", n, n < 0 ? errno : 0); return NULL; }
    uint32_t total; memcpy(&total, g_rx, 4);
    if (g_rx[4] != CT_DATA || total < 12 || total > (8u << 20)) { L("  bad data container type=%u len=%u", g_rx[4], total); return NULL; }
    uint8_t *b = malloc(total);
    if (!b) return NULL;
    uint32_t got = (uint32_t)n > total ? total : (uint32_t)n;
    memcpy(b, g_rx, got);
    while (got < total) {
        n = usb_read(g_rx, BUFSZ);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { L("  data phase short: %u/%u", got, total); free(b); return NULL; }
        uint32_t c = (uint32_t)n; if (c > total - got) c = total - got;
        memcpy(b + got, g_rx, c); got += c;
    }
    *plen = total;
    return b;
}

/* ------------------------------------------------------------------ */
/* object helpers                                                      */
/* ------------------------------------------------------------------ */
static uint16_t fmt_of(const char *name, int isdir) {
    if (isdir) return FMT_ASSOCIATION;
    const char *e = strrchr(name, '.');
    if (!e) return FMT_UNDEFINED;
    e++;
    if (!strcasecmp(e, "txt")) return 0x3004;
    if (!strcasecmp(e, "wav")) return 0x3008;
    if (!strcasecmp(e, "mp3")) return 0x3009;
    if (!strcasecmp(e, "avi")) return 0x300A;
    if (!strcasecmp(e, "jpg") || !strcasecmp(e, "jpeg")) return 0x3801;
    if (!strcasecmp(e, "bmp")) return 0x3804;
    if (!strcasecmp(e, "gif")) return 0x3807;
    if (!strcasecmp(e, "png")) return 0x380B;
    if (!strcasecmp(e, "mp4")) return 0xB982;
    return FMT_UNDEFINED;
}
static void mtp_date(time_t t, char *out) {
    struct tm tmv;
#ifdef _WIN32
    localtime_s(&tmv, &t);
#else
    localtime_r(&t, &tmv);
#endif
    snprintf(out, 20, "%04d%02d%02dT%02d%02d%02d", tmv.tm_year + 1900, tmv.tm_mon + 1, tmv.tm_mday,
             tmv.tm_hour, tmv.tm_min, tmv.tm_sec);
}
static int obj_stat(uint32_t h, struct stat *st) {
    char p[1024];
    if (obj_path(h, p, sizeof p) < 0) return -1;
    return stat(p, st);
}
static uint32_t parent_out(uint32_t h) { return g_obj[h].parent == ROOT ? 0 : g_obj[h].parent; }

static int prop_type(uint16_t prop) {
    switch (prop) {
    case PROP_StorageID: case PROP_ParentObject: return DT_U32;
    case PROP_ObjectFormat: case PROP_ProtectionStatus: return DT_U16;
    case PROP_ObjectSize: return DT_U64;
    case PROP_PersistentUID: return DT_U128;
    case PROP_ObjectFileName: case PROP_Name: case PROP_DateCreated: case PROP_DateModified: return DT_STR;
    default: return -1;
    }
}
/* append the value of one property of object h */
static void put_prop_value(uint32_t h, uint16_t prop, const struct stat *st) {
    char dt[20];
    switch (prop) {
    case PROP_StorageID: p32(STORAGE_ID); break;
    case PROP_ObjectFormat: p16(fmt_of(g_obj[h].name, g_obj[h].isdir)); break;
    case PROP_ProtectionStatus: p16(0); break;
    case PROP_ObjectSize: p64(g_obj[h].isdir ? 0 : (uint64_t)st->st_size); break;
    case PROP_ObjectFileName: case PROP_Name: pstr(g_obj[h].name); break;
    case PROP_DateCreated: case PROP_DateModified: mtp_date(st->st_mtime, dt); pstr(dt); break;
    case PROP_ParentObject: p32(parent_out(h)); break;
    case PROP_PersistentUID: p32(h); p32(0x54465254u /* "TRFT" */); p32(0); p32(0); break;
    }
}

static int rm_rf(const char *p) {
    struct stat st;
    if (stat(p, &st) != 0) return -1;
    if (!S_ISDIR(st.st_mode)) return unlink(p);
    DIR *d = opendir(p);
    int rc = 0;
    if (d) {
        struct dirent *e; char c[1280];
        while ((e = readdir(d)) != NULL) {
            if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
            snprintf(c, sizeof c, "%s/%s", p, e->d_name);
            if (rm_rf(c) != 0) rc = -1;
        }
        closedir(d);
    }
    if (rmdir(p) != 0) rc = -1;
    return rc;
}
static void mark_deleted(uint32_t h) {          /* object and every known descendant */
    if (!obj_valid(h)) return;
    hash_unlink(h); g_obj[h].deleted = 1;
    for (uint32_t i = 1; i < g_nobj; i++)
        if (!g_obj[i].deleted && g_obj[i].parent == h) mark_deleted(i);
}
static void sanitize_name(char *n) {
    for (char *p = n; *p; p++) if (*p == '/' || *p == '\\') *p = '_';
    if (!strcmp(n, ".") || !strcmp(n, "..") || !*n) strcpy(n, "_");
}

/* ------------------------------------------------------------------ */
/* operations                                                          */
/* ------------------------------------------------------------------ */
static int g_session;
static uint32_t g_pend_handle, g_pend_size; static int g_pend_valid;

static uint16_t do_GetDeviceInfo(void) {
    data_begin();
    p16(100); p32(6); p16(100); pstr("microsoft.com: 1.0;"); p16(0);
    {
        uint32_t n = NELEM(g_ops) + (g_remote ? NELEM(g_remote_ops) : 0);
        p32(n);
        for (uint32_t i = 0; i < NELEM(g_ops); i++) p16(g_ops[i]);
        if (g_remote) for (uint32_t i = 0; i < NELEM(g_remote_ops); i++) p16(g_remote_ops[i]);
    }
    p32(0);                                      /* events supported: none */
    { uint16_t dp = DEVPROP_FriendlyName; parr16(&dp, 1); }
    parr16(g_formats, NELEM(g_formats));         /* capture */
    parr16(g_formats, NELEM(g_formats));         /* playback */
    pstr("TreeFrogUI"); pstr("R36S handheld"); pstr("tfmtp 1.2"); pstr("TFMTP-0001");
    data_send();
    return RC_OK;
}

static uint16_t do_GetStorageInfo(uint32_t sid) {
    if (sid != STORAGE_ID) return RC_InvalidStorageID;
    uint64_t total = 0, freeb = 0;
#ifndef TFMTP_TEST
    struct statvfs v;
    if (statvfs(g_root, &v) == 0) { total = (uint64_t)v.f_blocks * v.f_frsize; freeb = (uint64_t)v.f_bavail * v.f_frsize; }
#else
    total = 16ull << 30; freeb = 1ull << 30;
#endif
    data_begin();
    p16(0x0004); p16(0x0002); p16(0x0000); p64(total); p64(freeb); p32(0xFFFFFFFFu);
    pstr("SD card"); pstr("");
    data_send();
    return RC_OK;
}

static uint16_t do_GetObjectHandles(uint32_t sid, uint32_t fmt, uint32_t parent, int count_only, uint32_t *outn) {
    if (sid != STORAGE_ID && sid != 0xFFFFFFFFu) return RC_InvalidStorageID;
    if (parent == 0) parent = ROOT;
    if (parent != ROOT && (!obj_valid(parent) || !g_obj[parent].isdir)) return RC_InvalidParentObject;
    uint32_t n = 0, *v = list_children(parent, &n);
    if (!v) return RC_InvalidParentObject;
    uint32_t k = 0;
    for (uint32_t i = 0; i < n; i++)
        if (!fmt || fmt_of(g_obj[v[i]].name, g_obj[v[i]].isdir) == fmt) v[k++] = v[i];
    *outn = k;
    if (!count_only) { data_begin(); p32(k); for (uint32_t i = 0; i < k; i++) p32(v[i]); data_send(); }
    free(v);
    return RC_OK;
}

static uint16_t do_GetObjectInfo(uint32_t h) {
    struct stat st; char dt[20];
    if (!obj_valid(h)) return RC_InvalidObjectHandle;
    if (obj_stat(h, &st) != 0) return RC_InvalidObjectHandle;
    int dir = g_obj[h].isdir;
    uint64_t sz = dir ? 0 : (uint64_t)st.st_size;
    data_begin();
    p32(STORAGE_ID); p16(fmt_of(g_obj[h].name, dir)); p16(0);
    p32(sz > 0xFFFFFFFFull ? 0xFFFFFFFFu : (uint32_t)sz);
    p16(0); p32(0); p32(0); p32(0); p32(0); p32(0); p32(0);   /* thumb fmt/size/w/h, image w/h/depth */
    p32(parent_out(h)); p16(dir ? 1 : 0); p32(0); p32(0);     /* parent, assoc type/desc, seq */
    pstr(g_obj[h].name);
    mtp_date(st.st_mtime, dt); pstr(dt); pstr(dt); pstr("");
    data_send();
    return RC_OK;
}

static uint16_t send_file_range(uint32_t h, uint64_t off, uint64_t maxlen, int partial, uint32_t *sent) {
    char p[1024]; struct stat st;
    if (!obj_valid(h) || g_obj[h].isdir) return RC_InvalidObjectHandle;
    if (obj_path(h, p, sizeof p) < 0 || stat(p, &st) != 0) return RC_InvalidObjectHandle;
    uint64_t sz = (uint64_t)st.st_size;
    if (off > sz) off = sz;
    uint64_t len = sz - off;
    if (partial && len > maxlen) len = maxlen;
    int fd = open(p, O_RDONLY | O_BINARY);
    if (fd < 0) { L("  open %s: %s", p, strerror(errno)); return RC_AccessDenied; }
    double t0 = now_s();
    int r = usb_send_file(fd, (long long)off, (long long)len, g_curop, g_curtid);
    int e = errno;
    close(fd);
    double dt = now_s() - t0;
    if (r < 0) {
        L("  send file failed after %.2fs: %s", dt, strerror(e));
        return e == ECANCELED ? RC_TransactionCancelled : RC_IncompleteTransfer;
    }
    L("  sent %llu bytes in %.2fs (%.2f MB/s)", (unsigned long long)len, dt, dt > 0 ? len / dt / 1048576.0 : 0.0);
    *sent = (uint32_t)len;
    return RC_OK;
}

static uint16_t do_DeleteObject(uint32_t h) {
    char p[1024];
    if (h == 0xFFFFFFFFu) return RC_AccessDenied;
    if (!obj_valid(h) || obj_path(h, p, sizeof p) < 0) return RC_InvalidObjectHandle;
    int r = rm_rf(p);
    L("  delete %s -> %s", p, r == 0 ? "ok" : strerror(errno));
    if (r != 0 && access(p, F_OK) == 0) return RC_PartialDeletion;
    mark_deleted(h);
    return RC_OK;
}

static uint16_t do_SendObjectInfo(uint32_t sid, uint32_t parent, uint32_t *oh) {
    uint32_t len; char name[600], dir[1024], full[1700];
    uint8_t *d = read_data(&len);
    g_pend_valid = 0;
    if (!d) return RC_IncompleteTransfer;
    uint16_t code = RC_OK;
    if (len < 12 + 53) { code = RC_InvalidParameter; goto out; }
    {
        const uint8_t *oi = d + 12;
        uint16_t fmt; uint32_t size;
        memcpy(&fmt, oi + 4, 2); memcpy(&size, oi + 8, 4);
        if (gstr(oi + 52, len - 12 - 52, name, sizeof name) < 0) { code = RC_InvalidParameter; goto out; }
        sanitize_name(name);
        if (sid != STORAGE_ID && sid != 0) { code = RC_InvalidStorageID; goto out; }
        uint32_t par = (parent == 0 || parent == 0xFFFFFFFFu) ? ROOT : parent;
        if (par != ROOT && (!obj_valid(par) || !g_obj[par].isdir)) { code = RC_InvalidParentObject; goto out; }
        if (obj_path(par, dir, sizeof dir) < 0) { code = RC_InvalidParentObject; goto out; }
        snprintf(full, sizeof full, "%s/%s", dir, name);
        L("  object info: name=\"%s\" fmt=0x%04X size=%u -> %s", name, fmt, size, full);
        if (fmt == FMT_ASSOCIATION) {
            if (mkdir(full, 0777) != 0 && errno != EEXIST) { L("  mkdir: %s", strerror(errno)); code = RC_AccessDenied; goto out; }
            *oh = obj_add(par, name, 1);
        } else {
            *oh = obj_add(par, name, 0);
            g_pend_handle = *oh; g_pend_size = size; g_pend_valid = 1;
        }
        if (!*oh) code = RC_GeneralError;
    }
out:
    free(d);
    return code;
}

static uint16_t do_SendObject(void) {
    char p[1024];
    int fd = -1, ok = g_pend_valid;
    if (ok && obj_path(g_pend_handle, p, sizeof p) == 0) {
        fd = open(p, O_WRONLY | O_CREAT | O_TRUNC | O_BINARY, 0666);
        if (fd < 0) L("  create %s: %s", p, strerror(errno));
    }
    /* always drain the data phase, even if the file can't be written */
    double t0 = now_s();
    int n;
    do { n = usb_read(g_rx, BUFSZ); } while (n == 0 || (n < 0 && errno == EINTR));
    if (n < 12) { L("  SendObject: no data container (n=%d)", n); if (fd >= 0) { close(fd); unlink(p); } return RC_IncompleteTransfer; }
    uint32_t total; memcpy(&total, g_rx, 4);
    uint64_t got = (uint64_t)n, wrote = 0; int werr = 0;
    if (fd >= 0 && n > 12) { if (write(fd, g_rx + 12, n - 12) != n - 12) werr = errno; else wrote += n - 12; }
    while (got < total) {
        n = usb_read(g_rx, BUFSZ);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { L("  SendObject: transfer aborted at %llu/%u (errno %d)", (unsigned long long)got, total, n < 0 ? errno : 0); break; }
        got += (uint64_t)n;
        if (fd >= 0 && !werr) { if (write(fd, g_rx, n) != n) werr = errno; else wrote += (uint64_t)n; }
    }
    double dt = now_s() - t0;
    if (fd >= 0) close(fd);
    g_pend_valid = 0;
    if (!ok) return RC_NoValidObjectInfo;
    if (fd < 0) return RC_AccessDenied;
    if (got < total) { unlink(p); mark_deleted(g_pend_handle); return RC_IncompleteTransfer; }
    if (werr) { L("  write %s: %s", p, strerror(werr)); unlink(p); mark_deleted(g_pend_handle); return werr == ENOSPC ? RC_StoreFull : RC_GeneralError; }
    L("  received %llu bytes in %.2fs (%.2f MB/s) -> %s", (unsigned long long)wrote, dt, dt > 0 ? wrote / dt / 1048576.0 : 0.0, p);
    return RC_OK;
}

static uint16_t do_GetObjectPropDesc(uint16_t prop) {
    int t = prop_type(prop);
    if (t < 0) return RC_InvalidObjectPropCode;
    data_begin();
    p16(prop); p16((uint16_t)t);
    p8(prop == PROP_ObjectFileName ? 1 : 0);       /* get/set */
    switch (t) {                                   /* default value */
    case DT_U16: p16(0); break;
    case DT_U32: p32(0); break;
    case DT_U64: p64(0); break;
    case DT_U128: p64(0); p64(0); break;
    default: p8(0); break;
    }
    p32(0);                                        /* group code */
    p8((prop == PROP_DateCreated || prop == PROP_DateModified) ? 3 : 0);  /* form flag */
    data_send();
    return RC_OK;
}

static uint16_t do_GetObjectPropValue(uint32_t h, uint16_t prop) {
    struct stat st;
    if (!obj_valid(h)) return RC_InvalidObjectHandle;
    if (prop_type(prop) < 0) return RC_InvalidObjectPropCode;
    if (obj_stat(h, &st) != 0) return RC_InvalidObjectHandle;
    data_begin(); put_prop_value(h, prop, &st); data_send();
    return RC_OK;
}

static uint16_t do_SetObjectPropValue(uint32_t h, uint16_t prop) {
    uint32_t len; char name[600], from[1024], dir[1024], to[1700];
    uint8_t *d = read_data(&len);
    if (!d) return RC_IncompleteTransfer;
    uint16_t code = RC_OK;
    if (!obj_valid(h)) { code = RC_InvalidObjectHandle; goto out; }
    if (prop != PROP_ObjectFileName && prop != PROP_Name) { code = RC_AccessDenied; goto out; }
    if (gstr(d + 12, len - 12, name, sizeof name) < 0) { code = RC_InvalidObjectPropValue; goto out; }
    sanitize_name(name);
    if (obj_path(h, from, sizeof from) < 0 || obj_path(g_obj[h].parent, dir, sizeof dir) < 0) { code = RC_InvalidObjectHandle; goto out; }
    snprintf(to, sizeof to, "%s/%s", dir, name);
    if (rename(from, to) != 0) { L("  rename %s -> %s: %s", from, to, strerror(errno)); code = RC_AccessDenied; goto out; }
    L("  renamed %s -> %s", from, to);
    hash_unlink(h);
    free(g_obj[h].name); g_obj[h].name = strdup(name);
    { uint32_t k = hkey(g_obj[h].parent, name); g_obj[h].hnext = g_hash[k]; g_hash[k] = h; }
out:
    free(d);
    return code;
}

static uint16_t do_GetObjectPropList(uint32_t h, uint32_t fmt, uint32_t prop, uint32_t group, uint32_t depth) {
    (void)fmt;
    if (prop == 0 && group != 0) return RC_GroupUnsupported;
    if (prop != 0xFFFFFFFFu && prop != 0 && prop_type((uint16_t)prop) < 0) return RC_ObjectPropNotSupported;
    uint32_t *v = NULL, n = 0, one = h;
    if (depth == 0) {
        if (h == 0 || h == 0xFFFFFFFFu) { n = 0; }
        else { if (!obj_valid(h)) return RC_InvalidObjectHandle; v = &one; n = 1; }
    } else if (depth == 1) {
        uint32_t par = (h == 0 || h == 0xFFFFFFFFu) ? ROOT : h;
        if (par != ROOT && (!obj_valid(par) || !g_obj[par].isdir)) return RC_InvalidObjectHandle;
        v = list_children(par, &n);
        if (!v) return RC_InvalidObjectHandle;
    } else return RC_DepthUnsupported;

    const uint16_t *pl = g_props; uint32_t np = NELEM(g_props); uint16_t single = (uint16_t)prop;
    if (prop != 0xFFFFFFFFu && prop != 0) { pl = &single; np = 1; }
    data_begin();
    size_t cpos = g_txlen; p32(0);
    uint32_t cnt = 0;
    for (uint32_t i = 0; i < n; i++) {
        struct stat st;
        if (obj_stat(v[i], &st) != 0) continue;
        for (uint32_t j = 0; j < np; j++) {
            p32(v[i]); p16(pl[j]); p16((uint16_t)prop_type(pl[j]));
            put_prop_value(v[i], pl[j], &st);
            cnt++;
        }
    }
    memcpy(g_tx + cpos, &cnt, 4);
    data_send();
    L("  proplist: %u objects, %u elements, %zu bytes", n, cnt, g_txlen);
    if (v != &one) free(v);
    return RC_OK;
}

/* ------------------------------------------------------------------ */
/* remote shell (vendor ops 0x9A00..0x9A04)                            */
/*                                                                     */
/*  TF_Info   ()                     data in : text "tfmtp 1.1 ..."    */
/*  TF_Exec   (flags)                data out: /bin/sh -c command      */
/*                                   resp    : job id                  */
/*            flags bit0 = give the job a stdin pipe (else /dev/null)  */
/*  TF_Read   (job, max, wait_ms)    data in : up to max bytes of      */
/*                                   stdout+stderr (waits <= wait_ms)  */
/*                                   resp    : state, code, buffered   */
/*            state: 0 running, 1 exited, 2 killed by signal;          */
/*                   +0x100 when the output pipe reached EOF           */
/*  TF_Write  (job, flags)           data out: bytes for stdin         */
/*                                   resp    : bytes accepted          */
/*            flags bit0 = close stdin afterwards                      */
/*  TF_Signal (job, sig)             sig 0 = forget the job (SIGKILL   */
/*                                   if it still runs)                 */
/* Output is buffered in RAM (JOBBUF per job); a full buffer simply    */
/* stops reading the pipe, so a fast producer blocks instead of        */
/* eating memory.                                                      */
/* ------------------------------------------------------------------ */
#ifndef TFMTP_TEST
#define MAXJOBS 8
#define JOBBUF  (512u << 10)
typedef struct {
    int used, out, in, state, code;
    pid_t pid;
    uint32_t id, len;
    uint8_t *buf;
} job_t;
static job_t g_jobs[MAXJOBS];
static uint32_t g_jobseq;

static job_t *job_get(uint32_t id) {
    uint32_t s = id & 7;
    if (s >= MAXJOBS || !g_jobs[s].used || g_jobs[s].id != id) return NULL;
    return &g_jobs[s];
}
static void job_pump(job_t *j) {
    while (j->out >= 0 && j->len < JOBBUF) {
        ssize_t r = read(j->out, j->buf + j->len, JOBBUF - j->len);
        if (r > 0) { j->len += (uint32_t)r; continue; }
        if (r < 0 && errno == EINTR) continue;
        if (r < 0 && errno == EAGAIN) break;
        close(j->out); j->out = -1;          /* EOF or error */
    }
    if (j->pid > 0 && j->state == 0) {
        int st;
        pid_t w = waitpid(j->pid, &st, WNOHANG);
        if (w == j->pid) {
            if (WIFEXITED(st)) { j->state = 1; j->code = WEXITSTATUS(st); }
            else { j->state = 2; j->code = WIFSIGNALED(st) ? WTERMSIG(st) : 0; }
        }
    }
}
static void job_free(job_t *j) {
    if (j->state == 0 && j->pid > 0) { kill(-j->pid, SIGKILL); kill(j->pid, SIGKILL); waitpid(j->pid, NULL, 0); }
    if (j->out >= 0) close(j->out);
    if (j->in >= 0) close(j->in);
    free(j->buf);
    memset(j, 0, sizeof *j);
}
static void jobs_kill_all(void) {
    for (int i = 0; i < MAXJOBS; i++)
        if (g_jobs[i].used && g_jobs[i].state == 0 && g_jobs[i].pid > 0) { kill(-g_jobs[i].pid, SIGKILL); kill(g_jobs[i].pid, SIGKILL); }
}
static void on_term(int sig) { (void)sig; jobs_kill_all(); _exit(0); }

static uint16_t do_TF_Exec(uint32_t flags, uint32_t *jid) {
    uint32_t len;
    uint8_t *d = read_data(&len);
    if (!d) return RC_IncompleteTransfer;
    uint16_t rc = RC_OK;
    char *cmd = malloc(len - 12 + 1);
    if (!cmd) { free(d); return RC_GeneralError; }
    memcpy(cmd, d + 12, len - 12); cmd[len - 12] = 0;
    free(d);
    int slot = -1;
    for (int i = 0; i < MAXJOBS; i++) if (!g_jobs[i].used) { slot = i; break; }
    if (slot < 0) {                                   /* reuse the oldest finished, fully read job */
        for (int i = 0; i < MAXJOBS; i++) { job_pump(&g_jobs[i]); if (g_jobs[i].state && !g_jobs[i].len && g_jobs[i].out < 0) { job_free(&g_jobs[i]); slot = i; break; } }
    }
    if (slot < 0) { L("  exec: no free job slot"); free(cmd); return RC_GeneralError; }
    int po[2] = { -1, -1 }, pi[2] = { -1, -1 };
    uint8_t *buf = malloc(JOBBUF);
    if (!buf || pipe(po) != 0 || ((flags & 1) && pipe(pi) != 0)) { L("  exec: pipe/malloc: %s", strerror(errno)); rc = RC_GeneralError; goto fail; }
    pid_t pid = fork();
    if (pid < 0) { L("  exec: fork: %s", strerror(errno)); rc = RC_GeneralError; goto fail; }
    if (pid == 0) {
        setsid();
        /* tfusbd runs us with SCHED_IDLE; remote jobs (button injection,
           recording) need normal scheduling to keep up with a game */
        { struct sched_param sp = { 0 }; syscall(SYS_sched_setscheduler, 0, SCHED_OTHER, &sp); setpriority(PRIO_PROCESS, 0, 0); }
        signal(SIGPIPE, SIG_DFL); signal(SIGTERM, SIG_DFL);
        int in = (flags & 1) ? pi[0] : open("/dev/null", O_RDONLY);
        dup2(in, 0); dup2(po[1], 1); dup2(po[1], 2);
        for (int fd = 3; fd < 256; fd++) close(fd);
        if (chdir("/") != 0) { /* keep going */ }
        setenv("PATH", "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin", 1);
        setenv("HOME", "/tmp", 1); setenv("TERM", "dumb", 1);
        execl("/bin/sh", "sh", "-c", cmd, (char *)NULL);
        _exit(127);
    }
    close(po[1]); if (pi[0] >= 0) close(pi[0]);
    fcntl(po[0], F_SETFL, O_NONBLOCK); fcntl(po[0], F_SETFD, FD_CLOEXEC);
    if (pi[1] >= 0) { fcntl(pi[1], F_SETFL, O_NONBLOCK); fcntl(pi[1], F_SETFD, FD_CLOEXEC); }
    job_t *j = &g_jobs[slot];
    memset(j, 0, sizeof *j);
    j->used = 1; j->pid = pid; j->out = po[0]; j->in = pi[1]; j->buf = buf;
    j->id = ((++g_jobseq) << 3) | (uint32_t)slot;
    *jid = j->id;
    L("  exec job %u pid %d: %.200s", j->id, (int)pid, cmd);
    free(cmd);
    return RC_OK;
fail:
    if (po[0] >= 0) { close(po[0]); close(po[1]); }
    if (pi[0] >= 0) { close(pi[0]); close(pi[1]); }
    free(buf); free(cmd);
    return rc;
}

static uint16_t do_TF_Read(uint32_t id, uint32_t max, uint32_t wait_ms, uint32_t *r0, uint32_t *r1, uint32_t *r2) {
    job_t *j = job_get(id);
    if (!j) return RC_InvalidParameter;
    if (max == 0 || max > JOBBUF) max = JOBBUF;
    if (wait_ms > 2000) wait_ms = 2000;
    job_pump(j);
    if (!j->len && j->out >= 0 && wait_ms) {
        struct pollfd pf = { j->out, POLLIN, 0 };
        poll(&pf, 1, (int)wait_ms);
        job_pump(j);
    }
    uint32_t n = j->len < max ? j->len : max;
    data_begin(); tx_need(n); memcpy(g_tx + g_txlen, j->buf, n); g_txlen += n; data_send();
    memmove(j->buf, j->buf + n, j->len - n); j->len -= n;
    if (n) job_pump(j);                               /* refill what we just made room for */
    *r0 = (uint32_t)j->state | (j->out < 0 ? 0x100u : 0u);
    *r1 = (uint32_t)j->code; *r2 = j->len;
    return RC_OK;
}

static uint16_t do_TF_Write(uint32_t id, uint32_t flags, uint32_t *acc) {
    uint32_t len;
    uint8_t *d = read_data(&len);              /* always drain the data phase */
    if (!d) return RC_IncompleteTransfer;
    job_t *j = job_get(id);
    uint16_t rc = RC_OK;
    uint32_t done = 0, n = len - 12;
    if (!j || j->in < 0) { rc = RC_InvalidParameter; goto out; }
    double t0 = now_s();
    while (done < n && now_s() - t0 < 2.0) {
        ssize_t w = write(j->in, d + 12 + done, n - done);
        if (w > 0) { done += (uint32_t)w; continue; }
        if (w < 0 && errno == EINTR) continue;
        if (w < 0 && errno != EAGAIN) { L("  stdin write: %s", strerror(errno)); break; }
        job_pump(j);                            /* let the child make progress on its output */
        struct pollfd pf[2] = { { j->in, POLLOUT, 0 }, { j->out, POLLIN, 0 } };
        poll(pf, j->out >= 0 ? 2 : 1, 50);
    }
    if ((flags & 1) && done == n) { close(j->in); j->in = -1; }
out:
    *acc = done;
    free(d);
    return rc;
}

static uint16_t do_TF_Signal(uint32_t id, uint32_t sig) {
    job_t *j = job_get(id);
    if (!j) return RC_InvalidParameter;
    if (sig == 0) { job_free(j); return RC_OK; }
    job_pump(j);
    if (j->state == 0 && j->pid > 0) { if (kill(-j->pid, (int)sig) != 0) kill(j->pid, (int)sig); }
    return RC_OK;
}

static uint16_t do_TF_Info(void) {
    char s[256]; int used = 0;
    for (int i = 0; i < MAXJOBS; i++) used += g_jobs[i].used;
    snprintf(s, sizeof s, "tfmtp 1.2 remote=1 pid=%d jobs=%d/%d jobbuf=%u root=%s\n", (int)getpid(), used, MAXJOBS, JOBBUF, g_root);
    size_t n = strlen(s);
    data_begin(); tx_need(n); memcpy(g_tx + g_txlen, s, n); g_txlen += n; data_send();
    return RC_OK;
}
#endif

/* ------------------------------------------------------------------ */
/* dispatcher                                                          */
/* ------------------------------------------------------------------ */
static void handle_command(const uint8_t *c, int n) {
    uint32_t len, p[5] = { 0, 0, 0, 0, 0 };
    uint16_t op; uint32_t tid;
    memcpy(&len, c, 4); memcpy(&op, c + 6, 2); memcpy(&tid, c + 8, 4);
    int np = (n - 12) / 4; if (np > 5) np = 5; if (np < 0) np = 0;
    for (int i = 0; i < np; i++) memcpy(&p[i], c + 12 + 4 * i, 4);
    g_curop = op; g_curtid = tid;
    double t0 = now_s();
    L("REQ  %s (0x%04X) tid=%u params=[%08X %08X %08X %08X %08X]", op_name(op), op, tid, p[0], p[1], p[2], p[3], p[4]);

    uint16_t rc = RC_OK; int nr = 0; uint32_t r0 = 0, r1 = 0, r2 = 0;
    switch (op) {
    case OP_GetDeviceInfo: rc = do_GetDeviceInfo(); break;
    case OP_OpenSession:
        if (g_session) { rc = RC_SessionAlreadyOpen; nr = 1; r0 = (uint32_t)g_session; }
        g_session = p[0] ? (int)p[0] : 1;
        if (rc == RC_SessionAlreadyOpen) rc = RC_OK;   /* be lenient: re-open is fine */
        nr = 0;
        break;
    case OP_CloseSession: g_session = 0; break;
    case OP_GetStorageIDs: data_begin(); p32(1); p32(STORAGE_ID); data_send(); break;
    case OP_GetStorageInfo: rc = do_GetStorageInfo(p[0]); break;
    case OP_GetNumObjects: rc = do_GetObjectHandles(p[0], p[1], p[2], 1, &r0); nr = rc == RC_OK; break;
    case OP_GetObjectHandles: { uint32_t k; rc = do_GetObjectHandles(p[0], p[1], p[2], 0, &k); if (rc == RC_OK) L("  %u handles (table now %u objects)", k, g_nobj - 1); } break;
    case OP_GetObjectInfo: rc = do_GetObjectInfo(p[0]); break;
    case OP_GetObject: { uint32_t s; rc = send_file_range(p[0], 0, 0, 0, &s); } break;
    case OP_GetPartialObject: rc = send_file_range(p[0], p[1], p[2], 1, &r0); nr = rc == RC_OK; break;
    case OP_DeleteObject: rc = do_DeleteObject(p[0]); break;
    case OP_SendObjectInfo: {
        uint32_t oh = 0;
        rc = do_SendObjectInfo(p[0], p[1], &oh);
        if (rc == RC_OK) { nr = 3; r0 = STORAGE_ID; r1 = p[1]; r2 = oh; }
    } break;
    case OP_SendObject: rc = do_SendObject(); break;
    case OP_GetDevicePropDesc:
        if (p[0] != DEVPROP_FriendlyName) { rc = RC_DevicePropNotSupported; break; }
        data_begin(); p16(DEVPROP_FriendlyName); p16(DT_STR); p8(0); pstr("R36S"); pstr("R36S"); p8(0); data_send();
        break;
    case OP_GetDevicePropValue:
        if (p[0] != DEVPROP_FriendlyName) { rc = RC_DevicePropNotSupported; break; }
        data_begin(); pstr("R36S"); data_send();
        break;
    case OP_GetObjectPropsSupported: data_begin(); parr16(g_props, NELEM(g_props)); data_send(); break;
    case OP_GetObjectPropDesc: rc = do_GetObjectPropDesc((uint16_t)p[0]); break;
    case OP_GetObjectPropValue: rc = do_GetObjectPropValue(p[0], (uint16_t)p[1]); break;
    case OP_SetObjectPropValue: rc = do_SetObjectPropValue(p[0], (uint16_t)p[1]); break;
    case OP_GetObjectPropList: rc = do_GetObjectPropList(p[0], p[1], p[2], p[3], p[4]); break;
    case OP_GetObjectReferences:
        if (!obj_valid(p[0])) { rc = RC_InvalidObjectHandle; break; }
        data_begin(); p32(0); data_send();
        break;
#ifndef TFMTP_TEST
    case OP_TF_Info: case OP_TF_Exec: case OP_TF_Read: case OP_TF_Write: case OP_TF_Signal:
        if (!g_remote) {
            if (op == OP_TF_Exec || op == OP_TF_Write) { uint32_t dl; free(read_data(&dl)); }   /* drain */
            rc = RC_OperationNotSupported; break;
        }
        switch (op) {
        case OP_TF_Info: rc = do_TF_Info(); break;
        case OP_TF_Exec: rc = do_TF_Exec(p[0], &r0); nr = rc == RC_OK; break;
        case OP_TF_Read: rc = do_TF_Read(p[0], p[1], p[2], &r0, &r1, &r2); if (rc == RC_OK) nr = 3; break;
        case OP_TF_Write: rc = do_TF_Write(p[0], p[1], &r0); nr = 1; break;
        case OP_TF_Signal: rc = do_TF_Signal(p[0], p[1]); break;
        }
        break;
#endif
    default: rc = RC_OperationNotSupported; break;
    }
    respond(rc, nr, r0, r1, r2);
    L("RESP %s -> 0x%04X%s (%.0f ms)", op_name(op), rc, rc == RC_OK ? " OK" : "", (now_s() - t0) * 1000);
}

#ifndef TFMTP_TEST
int main(int argc, char **argv) {
    if (argc > 1) g_root = argv[1];
    signal(SIGPIPE, SIG_IGN);
    signal(SIGTERM, on_term); signal(SIGINT, on_term); signal(SIGHUP, on_term);
    setvbuf(stderr, NULL, _IOLBF, 0);
    {
        char flag[1024];
        snprintf(flag, sizeof flag, "%s/cubegm/tfmtp.remote", g_root);
        g_remote = access(flag, F_OK) == 0 || getenv("TFMTP_REMOTE") != NULL;
    }
    L("tfmtp 1.2 start root=%s pid=%d (lazy listing, no pre-index) remote=%d", g_root, (int)getpid(), g_remote);
    for (int tries = 0; (g_usb = open("/dev/mtp_usb", O_RDWR | O_CLOEXEC)) < 0; tries++) {
        if (tries == 0 || tries % 10 == 0) L("open /dev/mtp_usb: %s (retrying)", strerror(errno));
        if (tries > 300) return 2;
        usleep(200000);
    }
    L("/dev/mtp_usb open, waiting for commands");
    int errs = 0;
    for (;;) {
        int n = usb_read(g_rx, BUFSZ);
        if (n < 0) {
            if (errno == EINTR) continue;
            if (errno == ECANCELED) { L("read: cancelled by host"); continue; }
            if (errs++ % 50 == 0) L("read error: %s", strerror(errno));
            usleep(100000);
            continue;
        }
        errs = 0;
        if (n < 12) { if (n) L("ignored %d-byte packet", n); continue; }
        if (g_rx[4] != CT_COMMAND) { L("ignored container type %u len %d (expected command)", g_rx[4], n); continue; }
        static uint8_t cmd[32];
        int cl = n > 32 ? 32 : n;
        memcpy(cmd, g_rx, cl);
        handle_command(cmd, cl);
    }
}
#else
/* ---------------- PC self-test: scripted MTP session ---------------- */
static uint32_t t_tid;
static void t_push(const void *b, int n) { t_in[t_intail] = malloc(n); memcpy(t_in[t_intail], b, n); t_inlen[t_intail++] = n; }
static void t_cmd(uint16_t op, int np, uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e) {
    uint8_t buf[32]; uint32_t l = 12 + 4 * np, pr[5] = { a, b, c, d, e };
    memcpy(buf, &l, 4); buf[4] = 1; buf[5] = 0; memcpy(buf + 6, &op, 2); t_tid++; memcpy(buf + 8, &t_tid, 4);
    for (int i = 0; i < np; i++) memcpy(buf + 12 + 4 * i, &pr[i], 4);
    t_push(buf, l);
}
static void t_data(uint16_t op, const uint8_t *payload, uint32_t plen, int chunk) {
    uint32_t total = 12 + plen; uint8_t *b = malloc(total);
    memcpy(b, &total, 4); b[4] = 2; b[5] = 0; memcpy(b + 6, &op, 2); memcpy(b + 8, &t_tid, 4); memcpy(b + 12, payload, plen);
    for (uint32_t o = 0; o < total; o += (uint32_t)chunk) t_push(b + o, (int)((total - o) < (uint32_t)chunk ? total - o : (uint32_t)chunk));
    free(b);
}
/* run queued packets through the dispatcher; return response code, data in t_out */
static uint16_t t_run(uint8_t **data, uint32_t *dlen, uint32_t *rp) {
    t_outlen = 0;
    int n = usb_read(g_rx, BUFSZ); uint8_t cmd[32]; memcpy(cmd, g_rx, n > 32 ? 32 : n);
    handle_command(cmd, n > 32 ? 32 : n);
    size_t o = 0; uint16_t rc = 0; *data = NULL; *dlen = 0;
    while (o + 12 <= t_outlen) {
        uint32_t l; memcpy(&l, t_out + o, 4);
        if (t_out[o + 4] == 2) { *data = t_out + o + 12; *dlen = l - 12; }
        if (t_out[o + 4] == 3) { memcpy(&rc, t_out + o + 6, 2); if (rp) { for (uint32_t i = 0; i < (l - 12) / 4 && i < 3; i++) memcpy(&rp[i], t_out + o + 12 + 4 * i, 4); } }
        o += l;
    }
    if (o != t_outlen) printf("!! trailing bytes in output (%zu vs %zu)\n", o, t_outlen);
    return rc;
}
static int t_fail;
#define CHECK(c, ...) do { if (!(c)) { t_fail++; printf("FAIL %s:%d ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)
static uint32_t u32at(const uint8_t *p) { uint32_t v; memcpy(&v, p, 4); return v; }
static uint16_t u16at(const uint8_t *p) { uint16_t v; memcpy(&v, p, 2); return v; }

int main(int argc, char **argv) {
    g_root = argc > 1 ? argv[1] : "tfmtp_testroot";
    uint8_t *d; uint32_t dl, rp[3];
    char path[600];
    /* fixture */
    mkdir(g_root, 0777);
    snprintf(path, sizeof path, "%s/GBA", g_root); mkdir(path, 0777);
    snprintf(path, sizeof path, "%s/GBA/game one.gba", g_root); { FILE *f = fopen(path, "wb"); for (int i = 0; i < 40000; i++) fputc(i & 0xFF, f); fclose(f); }
    snprintf(path, sizeof path, "%s/readme.txt", g_root); { FILE *f = fopen(path, "wb"); fputs("hello", f); fclose(f); }

    t_cmd(OP_GetDeviceInfo, 0, 0, 0, 0, 0, 0);
    CHECK(t_run(&d, &dl, NULL) == RC_OK && dl > 40, "GetDeviceInfo");
    t_cmd(OP_OpenSession, 1, 1, 0, 0, 0, 0);
    CHECK(t_run(&d, &dl, NULL) == RC_OK, "OpenSession");
    t_cmd(OP_GetStorageIDs, 0, 0, 0, 0, 0, 0);
    CHECK(t_run(&d, &dl, NULL) == RC_OK && dl == 8 && u32at(d + 4) == STORAGE_ID, "GetStorageIDs");
    t_cmd(OP_GetStorageInfo, 1, STORAGE_ID, 0, 0, 0, 0);
    CHECK(t_run(&d, &dl, NULL) == RC_OK && dl >= 26, "GetStorageInfo");
    t_cmd(OP_GetObjectHandles, 3, STORAGE_ID, 0, ROOT, 0, 0);
    CHECK(t_run(&d, &dl, NULL) == RC_OK, "GetObjectHandles root");
    uint32_t nroot = d ? u32at(d) : 0;
    CHECK(nroot == 2, "root count %u", nroot);
    uint32_t hgba = 0, htxt = 0;
    for (uint32_t i = 0; i < nroot; i++) {
        uint32_t h = u32at(d + 4 + 4 * i);
        if (!strcmp(g_obj[h].name, "GBA")) hgba = h; else htxt = h;
    }
    t_cmd(OP_GetObjectInfo, 1, htxt, 0, 0, 0, 0);
    CHECK(t_run(&d, &dl, NULL) == RC_OK && u32at(d + 8) == 5 && u16at(d + 4) == 0x3004, "GetObjectInfo txt");
    t_cmd(OP_GetObjectPropList, 5, ROOT, 0, 0xFFFFFFFFu, 0, 1);
    CHECK(t_run(&d, &dl, NULL) == RC_OK && u32at(d) == 2 * NELEM(g_props), "GetObjectPropList depth1 root: %u", d ? u32at(d) : 0);
    t_cmd(OP_GetObjectHandles, 3, STORAGE_ID, 0, hgba, 0, 0);
    CHECK(t_run(&d, &dl, NULL) == RC_OK && u32at(d) == 1, "list GBA");
    uint32_t hgame = u32at(d + 4);
    t_cmd(OP_GetObject, 1, hgame, 0, 0, 0, 0);
    CHECK(t_run(&d, &dl, NULL) == RC_OK && dl == 40000 && d[39999] == (39999 & 0xFF), "GetObject 40000 (got %u)", dl);
    t_cmd(OP_GetPartialObject, 3, hgame, 100, 50, 0, 0);
    CHECK(t_run(&d, &dl, rp) == RC_OK && dl == 50 && d[0] == 100 && rp[0] == 50, "GetPartialObject");

    /* upload: new folder + a 70000-byte file in 16 KB USB chunks */
    uint8_t oi[200]; memset(oi, 0, sizeof oi);
    uint16_t f = FMT_ASSOCIATION; memcpy(oi + 4, &f, 2);
    g_txlen = 0; pstr("New Folder"); memcpy(oi + 52, g_tx, g_txlen); uint32_t oil = 52 + (uint32_t)g_txlen + 3;
    t_cmd(OP_SendObjectInfo, 2, STORAGE_ID, hgba, 0, 0, 0); t_data(OP_SendObjectInfo, oi, oil, BUFSZ);
    CHECK(t_run(&d, &dl, rp) == RC_OK && rp[2] != 0, "SendObjectInfo folder");
    uint32_t hnew = rp[2];
    memset(oi, 0, sizeof oi); f = FMT_UNDEFINED; memcpy(oi + 4, &f, 2); uint32_t sz = 70000; memcpy(oi + 8, &sz, 4);
    g_txlen = 0; pstr("Игра (RU).gba"); memcpy(oi + 52, g_tx, g_txlen); oil = 52 + (uint32_t)g_txlen + 3;
    t_cmd(OP_SendObjectInfo, 2, STORAGE_ID, hnew, 0, 0, 0); t_data(OP_SendObjectInfo, oi, oil, BUFSZ);
    CHECK(t_run(&d, &dl, rp) == RC_OK, "SendObjectInfo file");
    uint32_t hup = rp[2];
    uint8_t *content = malloc(sz); for (uint32_t i = 0; i < sz; i++) content[i] = (uint8_t)(i * 7);
    t_cmd(OP_SendObject, 0, 0, 0, 0, 0, 0); t_data(OP_SendObject, content, sz, BUFSZ);
    CHECK(t_run(&d, &dl, NULL) == RC_OK, "SendObject");
    t_cmd(OP_GetObject, 1, hup, 0, 0, 0, 0);
    CHECK(t_run(&d, &dl, NULL) == RC_OK && dl == sz && !memcmp(d, content, sz), "read back uploaded file");
    /* rename + delete */
    g_txlen = 0; pstr("renamed.gba"); uint8_t nb[64]; uint32_t nbl = (uint32_t)g_txlen; memcpy(nb, g_tx, nbl);
    t_cmd(OP_SetObjectPropValue, 2, hup, PROP_ObjectFileName, 0, 0, 0); t_data(OP_SetObjectPropValue, nb, nbl, BUFSZ);
    CHECK(t_run(&d, &dl, NULL) == RC_OK, "rename");
    snprintf(path, sizeof path, "%s/GBA/New Folder/renamed.gba", g_root);
    CHECK(access(path, F_OK) == 0, "renamed file exists");
    t_cmd(OP_DeleteObject, 1, hnew, 0, 0, 0, 0);
    CHECK(t_run(&d, &dl, NULL) == RC_OK, "delete folder");
    snprintf(path, sizeof path, "%s/GBA/New Folder", g_root);
    CHECK(access(path, F_OK) != 0, "folder gone");
    t_cmd(OP_GetObjectInfo, 1, hup, 0, 0, 0, 0);
    CHECK(t_run(&d, &dl, NULL) == RC_InvalidObjectHandle, "deleted handle invalid");
    t_cmd(0x9999, 0, 0, 0, 0, 0, 0);
    CHECK(t_run(&d, &dl, NULL) == RC_OperationNotSupported, "unknown op");
    printf(t_fail ? "SELF-TEST: %d FAILURE(S)\n" : "SELF-TEST: all checks passed\n", t_fail);
    return t_fail ? 1 : 0;
}
#endif
