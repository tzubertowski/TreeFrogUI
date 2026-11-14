/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Pavel Kotek
 *
 * tfcap.h - shared definitions for the TreeFrogUI capture pipeline:
 *
 *   game -> driver (dlopen TF_DRIVER) = tfshim.so -> real driver_*.so
 *                                         |
 *                                         | copies frames/audio into a shared
 *                                         v memory segment (only while enabled)
 *                                  /dev/shm/tfcap  <- created by tfrec
 *                                         |
 *                                  tfrec  -> stdout packet stream -> PC (r36rec.py)
 *
 * Everything is little-endian, 32-bit fields, no pointers inside the segment.
 *
 * ------------------------------------------------------------------------
 * 1. Shared memory segment (file TFCAP_PATH on tmpfs, created by the recorder)
 * ------------------------------------------------------------------------
 *   offset 0            struct tfcap_hdr (one page)
 *   v_slot_off          v_nslots x video slot, each v_slot_stride bytes:
 *                         struct tfcap_vslot (64 bytes) + packed RGB565 pixels
 *                         (rows packed: w*2 bytes per row, at most v_max_bytes)
 *   a_desc_off          a_ndesc x struct tfcap_adesc (power of two)
 *   a_ring_off          audio byte ring, a_ring_bytes (power of two)
 *
 * Protocol:
 *   - The recorder creates the file (O_EXCL after unlinking a stale one),
 *     fills the geometry, then publishes magic+state=RUNNING and sets
 *     `enabled` (bit0 video, bit1 audio). It increments `heartbeat` every
 *     poll. On exit: enabled=0, state=CLOSED, unlink.
 *   - The shim polls for the file cheaply (an open() every TFSHIM_POLL_CALLS
 *     hook calls while detached), maps it, validates it and starts copying.
 *     It detaches (munmap) when state != RUNNING or the heartbeat has not
 *     moved for TFCAP_STALE_MS (recorder killed), and never re-attaches to
 *     the same inode after a stale detach.
 *   - Video: single writer. seq = ++vseq; slot = seq % v_nslots.
 *     slot.seq_begin = seq; barrier; fill; barrier; slot.seq_end = seq;
 *     barrier; hdr.vseq = seq.  The reader takes hdr.vseq, checks seq_end,
 *     reads, barrier, re-checks seq_begin: a mismatch means the slot was
 *     overwritten while being read (reader was late) and the frame is dropped.
 *   - Audio: single writer. Bytes go to the ring at a_wpos (mod ring size),
 *     then a descriptor (seqlocked like the video slots) records
 *     {pos, bytes, timestamp}; then a_wpos += bytes and a_cidx += 1.
 *     A descriptor older than a_ndesc chunks, or whose bytes are older than
 *     (a_ring_bytes - TFCAP_AMAX_CHUNK) behind a_wpos, is lost.
 *   - Timestamps: CLOCK_MONOTONIC nanoseconds taken by the shim at the moment
 *     the game called the driver.
 *
 * ------------------------------------------------------------------------
 * 2. Output stream of tfrec (stdout)
 * ------------------------------------------------------------------------
 *   stream header, 16 bytes: "TFRS", u32 version (=1), u32 header_len (=16),
 *                            u32 flags (0)
 *   then packets, each a 24-byte header followed by `len` payload bytes:
 *     u8  sync[2] = "TP"
 *     u8  type          TFS_VKEY / TFS_VDELTA / TFS_AUDIO / TFS_INFO / TFS_END
 *     u8  flags         video: bit0 = 2x2 downscaled by tfrec
 *     u32 len           payload bytes
 *     u64 ts_us         CLOCK_MONOTONIC microseconds (shim time of the call)
 *     u16 w, u16 h      video: frame size; audio: w = channels,
 *                       h = sample rate in Hz (0 = unknown); others 0
 *     u32 extra         video: shim frame seq; audio: shim byte position of
 *                       the chunk (mod 2^32, gaps = lost bytes); others 0
 *   TFS_VKEY/TFS_VDELTA payload: tfcodec bitstream (see tfcodec.h)
 *   TFS_AUDIO payload: interleaved s16le samples as given to the driver
 *   TFS_INFO / TFS_END payload: ASCII "key=value key=value ..."
 *   Anything before the first "TFRS" (e.g. shell noise) must be skipped.
 */
#ifndef TFCAP_H
#define TFCAP_H

#include <stdint.h>
#include <string.h>

#define TFCAP_PATH          "/dev/shm/tfcap"
#define TFCAP_MAGIC         0x31504354u          /* "TCP1" */
#define TFCAP_VERSION       1u
#define TFCAP_STATE_RUNNING 1u
#define TFCAP_STATE_CLOSED  2u
#define TFCAP_EN_VIDEO      1u
#define TFCAP_EN_AUDIO      2u

#define TFCAP_HDR_BYTES     4096u
#define TFCAP_VSLOTS        3u
#define TFCAP_VMAX_W        640u
#define TFCAP_VMAX_H        480u
#define TFCAP_VMAX_BYTES    (TFCAP_VMAX_W * TFCAP_VMAX_H * 2u)
#define TFCAP_ADESC         256u                 /* power of two */
#define TFCAP_ARING_BYTES   (512u * 1024u)       /* power of two, ~2.7 s @ 48k stereo */
#define TFCAP_AMAX_CHUNK    (64u * 1024u)        /* largest accepted playframe chunk */
#define TFCAP_STALE_MS      5000u                /* heartbeat silence => recorder gone */

struct tfcap_hdr {
    uint32_t magic;            /*  0 TFCAP_MAGIC, written last by the recorder */
    uint32_t version;          /*  4 */
    uint32_t hdr_bytes;        /*  8 */
    uint32_t total_bytes;      /* 12 */
    volatile uint32_t enabled; /* 16 recorder: TFCAP_EN_* */
    volatile uint32_t heartbeat;/*20 recorder: ++ every poll */
    volatile uint32_t v_min_interval_us; /* 24 recorder: shim-side fps cap (0 = every frame) */
    volatile uint32_t state;   /* 28 recorder: TFCAP_STATE_* */
    volatile uint32_t shim_pid;/* 32 shim: pid of the last attached process */
    volatile uint32_t shim_attaches; /* 36 shim: ++ per attach */
    volatile uint32_t vseq;    /* 40 shim: last published video seq (0 = none) */
    uint32_t v_nslots;         /* 44 */
    uint32_t v_slot_off;       /* 48 */
    uint32_t v_slot_stride;    /* 52 */
    uint32_t v_max_bytes;      /* 56 */
    volatile uint32_t v_too_big;  /* 60 shim: frames that did not fit a slot */
    volatile uint32_t a_cidx;  /* 64 shim: chunks published */
    volatile uint32_t a_wpos;  /* 68 shim: bytes published (mod 2^32) */
    uint32_t a_ring_off;       /* 72 */
    uint32_t a_ring_bytes;     /* 76 power of two */
    uint32_t a_desc_off;       /* 80 */
    uint32_t a_ndesc;          /* 84 power of two */
    volatile uint32_t a_rate;  /* 88 shim: rate passed to sound_driver_init (0 = unknown) */
    volatile uint32_t a_channels; /* 92 shim: channels passed to sound_driver_init (0 = unknown) */
    volatile uint32_t a_bad_len;  /* 96 shim: playframe calls with an implausible length */
    volatile uint32_t v_calls; /* 100 shim: disp_frame calls while attached+enabled */
    volatile uint32_t a_calls; /* 104 shim: playframe calls while attached+enabled */
    volatile uint32_t v_last_w, v_last_h, v_last_pitch; /* 108..116 shim: last seen frame geometry */
    uint32_t rec_pid;          /* 120 recorder pid (a new recorder stops an old one) */
    uint32_t reserved[(256 - 124) / 4];
};

struct tfcap_vslot {            /* 64 bytes, pixels follow */
    volatile uint32_t seq_begin;
    volatile uint32_t seq_end;
    uint32_t w, h;              /* pixels */
    uint32_t bytes;             /* w*h*2, rows packed */
    uint32_t src_pitch;         /* pitch the game passed (informational) */
    uint32_t ts_lo, ts_hi;      /* CLOCK_MONOTONIC ns */
    uint32_t reserved[8];
};

struct tfcap_adesc {            /* 32 bytes */
    volatile uint32_t seq_begin;/* chunk index */
    volatile uint32_t seq_end;
    uint32_t pos;               /* byte position (mod 2^32) of the chunk in the ring */
    uint32_t bytes;
    uint32_t ts_lo, ts_hi;
    uint32_t reserved[2];
};

/* stream format */
#define TFS_MAGIC     "TFRS"
#define TFS_VERSION   1u
#define TFS_HDR_BYTES 16u
#define TFS_PKT_BYTES 24u
#define TFS_VKEY      1u
#define TFS_VDELTA    2u
#define TFS_AUDIO     3u
#define TFS_INFO      4u
#define TFS_END       5u
#define TFS_F_SCALE2  1u

/* ---- barriers (sync on MIPS; compiler barrier on x86) ---- */
#define TFCAP_WMB() __atomic_thread_fence(__ATOMIC_RELEASE)
#define TFCAP_RMB() __atomic_thread_fence(__ATOMIC_ACQUIRE)
#define TFCAP_MB()  __atomic_thread_fence(__ATOMIC_SEQ_CST)

static inline uint32_t tfcap_align_up(uint32_t v, uint32_t a) { return (v + a - 1) & ~(a - 1); }

/* Geometry used by tfrec (and the PC test harness). Returns total size. */
static inline uint32_t tfcap_layout_size(void)
{
    uint32_t stride = tfcap_align_up((uint32_t)sizeof(struct tfcap_vslot) + TFCAP_VMAX_BYTES, 4096u);
    return TFCAP_HDR_BYTES + TFCAP_VSLOTS * stride
         + tfcap_align_up(TFCAP_ADESC * (uint32_t)sizeof(struct tfcap_adesc), 4096u)
         + TFCAP_ARING_BYTES;
}

/* Fill geometry (memory must be zeroed). magic/state/enabled are published
 * separately by the caller with tfcap_publish(). */
static inline void tfcap_layout_init(struct tfcap_hdr *h)
{
    uint32_t stride = tfcap_align_up((uint32_t)sizeof(struct tfcap_vslot) + TFCAP_VMAX_BYTES, 4096u);
    h->version = TFCAP_VERSION;
    h->hdr_bytes = TFCAP_HDR_BYTES;
    h->total_bytes = tfcap_layout_size();
    h->v_nslots = TFCAP_VSLOTS;
    h->v_slot_off = TFCAP_HDR_BYTES;
    h->v_slot_stride = stride;
    h->v_max_bytes = TFCAP_VMAX_BYTES;
    h->a_desc_off = TFCAP_HDR_BYTES + TFCAP_VSLOTS * stride;
    h->a_ndesc = TFCAP_ADESC;
    h->a_ring_off = h->a_desc_off + tfcap_align_up(TFCAP_ADESC * (uint32_t)sizeof(struct tfcap_adesc), 4096u);
    h->a_ring_bytes = TFCAP_ARING_BYTES;
}

static inline void tfcap_publish(struct tfcap_hdr *h, uint32_t enabled, uint32_t min_interval_us)
{
    h->v_min_interval_us = min_interval_us;
    h->state = TFCAP_STATE_RUNNING;
    TFCAP_WMB();
    h->magic = TFCAP_MAGIC;
    TFCAP_WMB();
    h->enabled = enabled;
    TFCAP_MB();
}

/* Validate a mapped segment of `size` bytes (shim side). 0 = ok. */
static inline int tfcap_validate(const struct tfcap_hdr *h, uint32_t size)
{
    if (size < TFCAP_HDR_BYTES || h->magic != TFCAP_MAGIC || h->version != TFCAP_VERSION)
        return -1;
    TFCAP_RMB();
    if (h->total_bytes > size || h->v_nslots == 0 || h->v_nslots > 16) return -2;
    if ((uint64_t)h->v_slot_off + (uint64_t)h->v_nslots * h->v_slot_stride > size) return -3;
    if (h->v_slot_stride < sizeof(struct tfcap_vslot) + h->v_max_bytes) return -4;
    if (!h->a_ndesc || (h->a_ndesc & (h->a_ndesc - 1))) return -5;
    if (!h->a_ring_bytes || (h->a_ring_bytes & (h->a_ring_bytes - 1)) ||
        h->a_ring_bytes <= TFCAP_AMAX_CHUNK) return -6;
    if ((uint64_t)h->a_desc_off + (uint64_t)h->a_ndesc * sizeof(struct tfcap_adesc) > size) return -7;
    if ((uint64_t)h->a_ring_off + h->a_ring_bytes > size) return -8;
    return 0;
}

static inline struct tfcap_vslot *tfcap_vslot(struct tfcap_hdr *h, uint32_t seq)
{
    return (struct tfcap_vslot *)((uint8_t *)h + h->v_slot_off + (seq % h->v_nslots) * h->v_slot_stride);
}
static inline struct tfcap_adesc *tfcap_adesc(struct tfcap_hdr *h, uint32_t idx)
{
    return (struct tfcap_adesc *)((uint8_t *)h + h->a_desc_off) + (idx & (h->a_ndesc - 1));
}
static inline uint8_t *tfcap_aring(struct tfcap_hdr *h) { return (uint8_t *)h + h->a_ring_off; }

/* ------------------------------------------------------------------------
 * Writer side (shim). Per-attachment state lives in tfcap_wstate.
 * ---------------------------------------------------------------------- */
struct tfcap_wstate {
    uint64_t next_due_ns;      /* fps cap */
};

/* Copy one RGB565 frame. Returns 1 if stored, 0 if skipped. */
static inline int tfcap_write_video(struct tfcap_hdr *h, struct tfcap_wstate *ws,
                                    const void *src, int w, int hh, int pitch, uint64_t ts_ns)
{
    if (!src || w <= 0 || hh <= 0 || pitch < w * 2) return 0;
    h->v_last_w = (uint32_t)w; h->v_last_h = (uint32_t)hh; h->v_last_pitch = (uint32_t)pitch;
    uint32_t bytes = (uint32_t)w * (uint32_t)hh * 2u;
    if ((uint32_t)w > 4096u || (uint32_t)hh > 4096u || bytes > h->v_max_bytes) { h->v_too_big++; return 0; }
    uint64_t iv = (uint64_t)h->v_min_interval_us * 1000u;
    if (iv) {                                  /* cap the rate, tolerate 1/4 interval of jitter */
        if (ts_ns + (iv >> 2) < ws->next_due_ns) return 0;
        ws->next_due_ns = (ts_ns > ws->next_due_ns + iv) ? ts_ns + iv : ws->next_due_ns + iv;
    }
    uint32_t seq = h->vseq + 1u;
    if (!seq) seq = 1;
    struct tfcap_vslot *s = tfcap_vslot(h, seq);
    s->seq_begin = seq;
    TFCAP_WMB();
    s->w = (uint32_t)w; s->h = (uint32_t)hh; s->bytes = bytes; s->src_pitch = (uint32_t)pitch;
    s->ts_lo = (uint32_t)ts_ns; s->ts_hi = (uint32_t)(ts_ns >> 32);
    uint8_t *dst = (uint8_t *)(s + 1);
    const uint8_t *sp = (const uint8_t *)src;
    uint32_t row = (uint32_t)w * 2u;
    if ((uint32_t)pitch == row) memcpy(dst, sp, bytes);
    else for (int y = 0; y < hh; y++) memcpy(dst + (uint32_t)y * row, sp + (size_t)y * (size_t)pitch, row);
    TFCAP_WMB();
    s->seq_end = seq;
    TFCAP_WMB();
    h->vseq = seq;
    return 1;
}

/* Copy one audio chunk of `bytes` bytes. Returns 1 if stored. */
static inline int tfcap_write_audio(struct tfcap_hdr *h, const void *buf, uint32_t bytes, uint64_t ts_ns)
{
    if (!buf || !bytes || bytes > TFCAP_AMAX_CHUNK) { h->a_bad_len++; return 0; }
    uint32_t pos = h->a_wpos, mask = h->a_ring_bytes - 1u, off = pos & mask;
    uint8_t *ring = tfcap_aring(h);
    uint32_t first = h->a_ring_bytes - off;
    if (first >= bytes) memcpy(ring + off, buf, bytes);
    else { memcpy(ring + off, buf, first); memcpy(ring, (const uint8_t *)buf + first, bytes - first); }
    uint32_t idx = h->a_cidx;
    struct tfcap_adesc *d = tfcap_adesc(h, idx);
    d->seq_begin = idx;
    TFCAP_WMB();
    d->pos = pos; d->bytes = bytes;
    d->ts_lo = (uint32_t)ts_ns; d->ts_hi = (uint32_t)(ts_ns >> 32);
    TFCAP_WMB();
    d->seq_end = idx;
    TFCAP_WMB();
    h->a_wpos = pos + bytes;
    TFCAP_WMB();
    h->a_cidx = idx + 1u;
    return 1;
}

/* ---- little-endian packing helpers for the stream ---- */
static inline void tfs_put16(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static inline void tfs_put32(uint8_t *p, uint32_t v) { tfs_put16(p, v); tfs_put16(p + 2, v >> 16); }
static inline void tfs_put64(uint8_t *p, uint64_t v) { tfs_put32(p, (uint32_t)v); tfs_put32(p + 4, (uint32_t)(v >> 32)); }

static inline void tfs_stream_header(uint8_t out[TFS_HDR_BYTES])
{
    memcpy(out, TFS_MAGIC, 4);
    tfs_put32(out + 4, TFS_VERSION);
    tfs_put32(out + 8, TFS_HDR_BYTES);
    tfs_put32(out + 12, 0);
}

static inline void tfs_packet_header(uint8_t out[TFS_PKT_BYTES], uint32_t type, uint32_t flags,
                                     uint32_t len, uint64_t ts_us, uint32_t w, uint32_t h, uint32_t extra)
{
    out[0] = 'T'; out[1] = 'P'; out[2] = (uint8_t)type; out[3] = (uint8_t)flags;
    tfs_put32(out + 4, len);
    tfs_put64(out + 8, ts_us);
    tfs_put16(out + 16, w); tfs_put16(out + 18, h);
    tfs_put32(out + 20, extra);
}

#endif
