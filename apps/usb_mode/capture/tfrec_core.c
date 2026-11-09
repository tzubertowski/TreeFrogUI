/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Pavel Kotek
 */
#include "tfrec_core.h"
#include "tfcodec.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_NPIX (TFCAP_VMAX_W * TFCAP_VMAX_H)
#define OB_CAP   (TFC_MAX_BYTES(MAX_NPIX) + TFS_PKT_BYTES + 512u * 1024u)

int tfrec_init(struct tfrec *r, struct tfcap_hdr *h, const struct tfrec_opts *o)
{
    memset(r, 0, sizeof *r);
    r->h = h;
    r->o = *o;
    if (r->o.scale != 2) r->o.scale = 1;
    if (!r->o.backlog) r->o.backlog = 256u * 1024u;
    r->ob_cap = OB_CAP;
    r->ob = malloc(r->ob_cap);
    r->prev = malloc(MAX_NPIX * 2u);
    r->scratch = r->o.scale == 2 ? malloc(MAX_NPIX / 2u) : NULL;
    if (!r->ob || !r->prev || (r->o.scale == 2 && !r->scratch)) { tfrec_free(r); return -1; }
    r->last_vseq = h->vseq;          /* ignore anything written before we started */
    r->a_next = h->a_cidx;
    return 0;
}

void tfrec_free(struct tfrec *r)
{
    free(r->ob); free(r->prev); free(r->scratch);
    r->ob = NULL; r->prev = r->scratch = NULL;
}

/* Make room for `need` bytes at the tail; NULL if impossible right now. */
static uint8_t *ob_reserve(struct tfrec *r, size_t need)
{
    if (r->ob_cap - r->ob_tail < need && r->ob_head) {
        memmove(r->ob, r->ob + r->ob_head, r->ob_tail - r->ob_head);
        r->ob_tail -= r->ob_head;
        r->ob_head = 0;
    }
    return r->ob_cap - r->ob_tail >= need ? r->ob + r->ob_tail : NULL;
}

void tfrec_stream_header(struct tfrec *r)
{
    uint8_t *p = ob_reserve(r, TFS_HDR_BYTES);
    if (!p) return;
    tfs_stream_header(p);
    r->ob_tail += TFS_HDR_BYTES;
}

static void poll_audio(struct tfrec *r)
{
    struct tfcap_hdr *h = r->h;
    uint32_t c = __atomic_load_n(&h->a_cidx, __ATOMIC_ACQUIRE);
    if (!r->o.audio) { r->a_next = c; return; }
    if (c - r->a_next > h->a_ndesc - 1u) {          /* descriptors overwritten */
        uint32_t keep = h->a_ndesc - 1u;
        r->st.a_lost += c - r->a_next - keep;
        r->a_next = c - keep;
    }
    while (r->a_next != c) {
        uint32_t i = r->a_next++;
        struct tfcap_adesc *d = tfcap_adesc(h, i);
        uint32_t e = d->seq_end;
        TFCAP_RMB();
        uint32_t pos = d->pos, bytes = d->bytes;
        uint64_t ts = ((uint64_t)d->ts_hi << 32) | d->ts_lo;
        TFCAP_RMB();
        if (e != i || d->seq_begin != i || !bytes || bytes > TFCAP_AMAX_CHUNK) { r->st.a_lost++; continue; }
        uint8_t *p = ob_reserve(r, TFS_PKT_BYTES + bytes);
        if (!p) { r->st.a_backlog++; continue; }
        uint32_t mask = h->a_ring_bytes - 1u, off = pos & mask, first = h->a_ring_bytes - off;
        const uint8_t *ring = tfcap_aring(h);
        uint8_t *dst = p + TFS_PKT_BYTES;
        if (first >= bytes) memcpy(dst, ring + off, bytes);
        else { memcpy(dst, ring + off, first); memcpy(dst + first, ring, bytes - first); }
        TFCAP_RMB();
        uint32_t wpos = h->a_wpos;
        if (wpos - pos > h->a_ring_bytes - TFCAP_AMAX_CHUNK) { r->st.a_lost++; continue; }  /* overwritten */
        uint32_t rate = h->a_rate, ch = h->a_channels;
        tfs_packet_header(p, TFS_AUDIO, 0, bytes, ts / 1000u, ch, rate <= 65535u ? rate : 0u, pos);
        r->ob_tail += TFS_PKT_BYTES + bytes;
        r->st.a_sent++;
        r->st.a_bytes += bytes;
    }
}

static void poll_video(struct tfrec *r)
{
    struct tfcap_hdr *h = r->h;
    uint32_t seq = __atomic_load_n(&h->vseq, __ATOMIC_ACQUIRE);
    if (seq == r->last_vseq) return;
    if (r->last_vseq && seq - r->last_vseq > 1u) r->st.v_lost += seq - r->last_vseq - 1u;
    r->last_vseq = seq;
    if (!r->o.video) return;

    struct tfcap_vslot *s = tfcap_vslot(h, seq);
    if (s->seq_end != seq) { r->st.v_torn++; return; }
    TFCAP_RMB();
    uint32_t w = s->w, hh = s->h, bytes = s->bytes;
    uint64_t ts_us = (((uint64_t)s->ts_hi << 32) | s->ts_lo) / 1000u;
    if (!w || !hh || w > TFCAP_VMAX_W * 2u || bytes != w * hh * 2u || bytes > h->v_max_bytes ||
        w * hh > MAX_NPIX) { r->st.v_bad++; return; }
    if (r->o.fps > 0 && r->st.v_sent && ts_us < r->last_v_us + (uint64_t)(750000 / r->o.fps)) {
        r->st.v_fps_skip++;                       /* shim did not cap (older shim / fps changed) */
        return;
    }
    if (tfrec_pending(r) > r->o.backlog) { r->st.v_backlog++; return; }

    const uint16_t *cur = (const uint16_t *)(s + 1);
    int ew = (int)w, eh = (int)hh;
    if (r->o.scale == 2) {
        ew = (int)w / 2; eh = (int)hh / 2;
        if (ew <= 0 || eh <= 0) { r->st.v_bad++; return; }
        tfc_downscale2(cur, (int)w, (int)hh, r->scratch);
        TFCAP_RMB();
        if (s->seq_begin != seq) { r->st.v_torn++; return; }
        cur = r->scratch;
    }
    size_t npix = (size_t)ew * (size_t)eh;
    int key = r->force_key || !r->have_prev || ew != r->prev_w || eh != r->prev_h ||
              (r->o.keyint_s > 0 && ts_us - r->last_key_us >= (uint64_t)r->o.keyint_s * 1000000u);
    uint8_t *p = ob_reserve(r, TFS_PKT_BYTES + TFC_MAX_BYTES(npix));
    if (!p) { r->st.v_backlog++; return; }
    size_t n = tfc_encode(cur, key ? NULL : r->prev, ew, eh, p + TFS_PKT_BYTES, TFC_MAX_BYTES(npix));
    if (key && n) memcpy(r->prev, cur, npix * 2u);
    if (r->o.scale == 1) {                        /* encoded straight from shared memory */
        TFCAP_RMB();
        if (s->seq_begin != seq) {               /* overwritten meanwhile: prev is suspect */
            r->st.v_torn++; r->force_key = 1; r->have_prev = 0;
            return;
        }
    }
    if (!n) { r->st.v_overflow++; r->force_key = 1; r->have_prev = 0; return; }
    tfs_packet_header(p, key ? TFS_VKEY : TFS_VDELTA, r->o.scale == 2 ? TFS_F_SCALE2 : 0, (uint32_t)n,
                      ts_us, (uint32_t)ew, (uint32_t)eh, seq);
    r->ob_tail += TFS_PKT_BYTES + n;
    r->have_prev = 1; r->force_key = 0;
    r->prev_w = ew; r->prev_h = eh;
    r->last_v_us = ts_us;
    if (key) { r->last_key_us = ts_us; r->st.v_keys++; }
    r->st.v_sent++;
    r->st.v_bytes += n;
    r->st.v_raw_bytes += npix * 2u;
}

void tfrec_poll(struct tfrec *r, uint64_t now_us)
{
    (void)now_us;
    poll_audio(r);       /* audio first: it has the shorter deadline */
    poll_video(r);
    poll_audio(r);
}

void tfrec_info(struct tfrec *r, unsigned type, uint64_t now_us, const char *extra)
{
    char t[640];
    struct tfcap_hdr *h = r->h;
    const struct tfrec_stats *s = &r->st;
    int n = snprintf(t, sizeof t,
        "t_us=%llu shim_pid=%u attaches=%u vseq=%u v_sent=%u v_keys=%u v_torn=%u v_lost=%u "
        "v_backlog=%u v_fps_skip=%u v_bad=%u v_overflow=%u v_bytes=%llu v_raw=%llu "
        "a_sent=%u a_lost=%u a_backlog=%u a_bytes=%llu out_bytes=%llu pending=%u "
        "rate=%u ch=%u v_calls=%u a_calls=%u v_too_big=%u a_bad_len=%u last=%ux%u/%u%s%s",
        (unsigned long long)now_us, h->shim_pid, h->shim_attaches, h->vseq, s->v_sent, s->v_keys,
        s->v_torn, s->v_lost, s->v_backlog, s->v_fps_skip, s->v_bad, s->v_overflow,
        (unsigned long long)s->v_bytes, (unsigned long long)s->v_raw_bytes, s->a_sent, s->a_lost,
        s->a_backlog, (unsigned long long)s->a_bytes, (unsigned long long)s->out_bytes,
        (unsigned)tfrec_pending(r), h->a_rate, h->a_channels, h->v_calls, h->a_calls, h->v_too_big,
        h->a_bad_len, h->v_last_w, h->v_last_h, h->v_last_pitch, extra && *extra ? " " : "", extra ? extra : "");
    if (n < 0) return;
    if ((size_t)n >= sizeof t) n = (int)sizeof t - 1;
    uint8_t *p = ob_reserve(r, TFS_PKT_BYTES + (size_t)n);
    if (!p) return;
    tfs_packet_header(p, type, 0, (uint32_t)n, now_us, 0, 0, 0);
    memcpy(p + TFS_PKT_BYTES, t, (size_t)n);
    r->ob_tail += TFS_PKT_BYTES + (size_t)n;
}
