/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Pavel Kotek
 *
 * tfrec_core - reads the tfcap segment and produces the tfrec packet stream
 * (format: tfcap.h) into an output buffer. Platform independent: used by
 * tfrec (MIPS/Linux) and by the PC test harness.
 */
#ifndef TFREC_CORE_H
#define TFREC_CORE_H

#include <stddef.h>
#include <stdint.h>
#include "tfcap.h"

struct tfrec_opts {
    int fps;           /* 0 = every frame the game shows */
    int scale;         /* 1 or 2 */
    int video, audio;  /* enable flags */
    int keyint_s;      /* force a key frame every N s (0 = only when needed) */
    size_t backlog;    /* skip video while this many output bytes are pending */
};

struct tfrec_stats {
    uint32_t v_sent, v_keys, v_torn, v_lost, v_backlog, v_fps_skip, v_bad, v_overflow;
    uint32_t a_sent, a_lost, a_backlog;
    uint64_t v_bytes, v_raw_bytes, a_bytes, out_bytes;
};

struct tfrec {
    struct tfcap_hdr *h;
    struct tfrec_opts o;
    uint8_t *ob;
    size_t ob_cap, ob_head, ob_tail;
    uint16_t *prev, *scratch;
    int prev_w, prev_h, have_prev, force_key;
    uint32_t last_vseq, a_next;
    uint64_t last_key_us, last_v_us;
    struct tfrec_stats st;
};

/* h must already be laid out (tfcap_layout_init). Returns 0 or -1 (ENOMEM). */
int  tfrec_init(struct tfrec *r, struct tfcap_hdr *h, const struct tfrec_opts *o);
void tfrec_free(struct tfrec *r);
/* Append the stream header. */
void tfrec_stream_header(struct tfrec *r);
/* Consume new audio chunks and the newest video frame. */
void tfrec_poll(struct tfrec *r, uint64_t now_us);
/* Append a TFS_INFO / TFS_END packet with counters plus `extra` text. */
void tfrec_info(struct tfrec *r, unsigned type, uint64_t now_us, const char *extra);

static inline size_t tfrec_pending(const struct tfrec *r) { return r->ob_tail - r->ob_head; }
static inline const uint8_t *tfrec_out(const struct tfrec *r) { return r->ob + r->ob_head; }
static inline void tfrec_consumed(struct tfrec *r, size_t n)
{
    r->ob_head += n;
    r->st.out_bytes += n;
    if (r->ob_head == r->ob_tail) r->ob_head = r->ob_tail = 0;
}

#endif
