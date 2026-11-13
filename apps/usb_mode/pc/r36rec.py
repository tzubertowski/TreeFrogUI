#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Pavel Kotek
"""r36rec - record the R36S screen + sound to an MP4 (via tfshim.so + tfrec).

    python r36rec.py out.mp4 [--seconds 20] [--fps 30] [--scale 1|2] [--no-audio]
                     [--raw stream.tfr] [--av-offset MS] [--crf 18] [--preset veryfast]
    python r36rec.py out.mp4 --from-file stream.tfr      (convert a saved stream)

The console must run the game with TF_DRIVER pointing at tfshim.so. This
script starts /mnt/sdcard/cubegm/tfrec as a remote job (r36.py / tfmtp),
decodes its packet stream (format: capture/tfcap.h), writes constant-frame-rate
video to ffmpeg (H.264) and the audio to a WAV aligned by the capture
timestamps, then muxes both into an MP4 (AAC audio). Ctrl+C stops cleanly.

Video timing: every output frame n (time t0 + n/fps) shows the newest captured
frame whose timestamp is nearest to it; frames are repeated or dropped as
needed. Audio: sample positions are continuous; bytes lost on the console are
replaced by silence, pauses longer than 100 ms (timestamps) are filled with
silence, and the track is placed at its first timestamp relative to the first
video frame (+ --av-offset).
"""
import argparse, ctypes, os, shutil, struct, subprocess, sys, tempfile, time, wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.environ.get('FFMPEG') or shutil.which('ffmpeg') or r'C:\Program Files\ffmpeg-7.1-full_build\bin\ffmpeg.exe'
TFREC = '/mnt/sdcard/cubegm/tfrec'

TFS_VKEY, TFS_VDELTA, TFS_AUDIO, TFS_INFO, TFS_END = 1, 2, 3, 4, 5
PKT = struct.Struct('<2sBBIQHHI')            # 24 bytes
OP_SKIP, OP_UP, OP_RUN, OP_LIT, OP_DLIT = range(5)


# --------------------------------------------------------------------------
# stream parsing
# --------------------------------------------------------------------------
class Packet:
    __slots__ = ('type', 'flags', 'ts', 'w', 'h', 'extra', 'payload')

    def __init__(self, typ, flags, ts, w, h, extra, payload):
        self.type, self.flags, self.ts, self.w, self.h, self.extra, self.payload = typ, flags, ts, w, h, extra, payload


class StreamParser:
    """Incremental parser: feed() bytes, iterate packets()."""

    def __init__(self):
        self.buf = bytearray()
        self.started = False
        self.skipped = 0          # junk bytes before the header / during resync
        self.resyncs = 0

    def feed(self, data):
        self.buf += data

    def packets(self):
        buf = self.buf
        pos = 0
        if not self.started:
            i = buf.find(b'TFRS')
            if i < 0:
                keep = max(0, len(buf) - 3)
                self.skipped += keep
                del buf[:keep]
                return
            if len(buf) < i + 16:
                return
            ver, hlen = struct.unpack_from('<II', buf, i + 4)
            if ver != 1:
                raise ValueError('unsupported stream version %d' % ver)
            self.skipped += i
            pos = i + hlen
            self.started = True
        while len(buf) - pos >= PKT.size:
            sync, typ, flags, ln, ts, w, h, extra = PKT.unpack_from(buf, pos)
            if sync != b'TP' or typ < 1 or typ > 5 or ln > 8 << 20:
                j = buf.find(b'TP', pos + 1)          # lost sync: hunt for the next header
                self.resyncs += 1
                nxt = j if j >= 0 else len(buf) - 1
                self.skipped += nxt - pos
                pos = nxt
                continue
            if len(buf) - pos - PKT.size < ln:
                break
            payload = bytes(buf[pos + PKT.size:pos + PKT.size + ln])
            pos += PKT.size + ln
            yield Packet(typ, flags, ts, w, h, extra, payload)
        del buf[:pos]


def parse_info(payload):
    out = {}
    for tok in payload.decode('ascii', 'replace').split():
        k, _, v = tok.partition('=')
        out[k] = v
    return out


# --------------------------------------------------------------------------
# frame decoding (tfcodec bitstream, see capture/tfcodec.h)
# --------------------------------------------------------------------------
def py_decode(data, prev, w, h):
    """Pure numpy/Python decoder. Returns a new uint16 array of w*h pixels."""
    n = w * h
    out = np.empty(n, np.uint16)
    p, i, ln = 0, 0, len(data)
    mv = memoryview(data)
    while i < n:
        if p >= ln:
            raise ValueError('truncated frame')
        b = data[p]; p += 1
        op, L = b >> 5, b & 31
        cnt = L + 1
        if L == 31:
            v = sh = 0
            while True:
                c = data[p]; p += 1
                v |= (c & 0x7f) << sh; sh += 7
                if not c & 0x80:
                    break
            cnt = 32 + v
        px = cnt * 2 if op == OP_DLIT else cnt
        if px > n - i:
            raise ValueError('op overruns the frame')
        if op == OP_SKIP:
            if prev is None:
                raise ValueError('SKIP without a previous frame')
            out[i:i + cnt] = prev[i:i + cnt]
        elif op == OP_UP:
            if i < w:
                raise ValueError('UP on the first row')
            k = 0
            while k < cnt:                         # sequential semantics: chunks of <= w
                c = min(cnt - k, w)
                out[i + k:i + k + c] = out[i + k - w:i + k - w + c]
                k += c
        elif op == OP_RUN:
            out[i:i + cnt] = data[p] | data[p + 1] << 8; p += 2
        elif op == OP_LIT:
            out[i:i + cnt] = np.frombuffer(mv[p:p + 2 * cnt], '<u2'); p += 2 * cnt
        elif op == OP_DLIT:
            out[i:i + 2 * cnt] = np.repeat(np.frombuffer(mv[p:p + 2 * cnt], '<u2'), 2); p += 2 * cnt
        else:
            raise ValueError('bad op %d' % op)
        i += px
    if p != ln:
        raise ValueError('trailing bytes in frame')
    return out


class CDecoder:
    """ctypes wrapper of tfcodec.dll (built by capture/build.sh), ~100x faster."""

    def __init__(self, path=None):
        cands = [path] if path else [os.path.join(HERE, 'tfcodec.dll'),
                                     os.path.join(HERE, '..', 'capture', 'build', 'tfcodec.dll')]
        for c in cands:
            if c and os.path.exists(c):
                self.lib = ctypes.CDLL(os.path.abspath(c))
                break
        else:
            raise OSError('tfcodec.dll not found')
        self.lib.tfc_decode.restype = ctypes.c_int
        self.lib.tfc_decode.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p,
                                        ctypes.c_int, ctypes.c_int]

    def decode(self, data, prev, w, h):
        out = np.empty(w * h, np.uint16)
        pp = prev.ctypes.data if prev is not None else None
        rc = self.lib.tfc_decode(data, len(data), pp, out.ctypes.data, w, h)
        if rc:
            raise ValueError('tfc_decode error %d' % rc)
        return out


class VideoDecoder:
    def __init__(self, force_python=False):
        self.prev = None
        self.size = None
        self.c = None
        if not force_python:
            try:
                self.c = CDecoder()
            except OSError:
                self.c = None
        self.errors = 0

    @property
    def backend(self):
        return 'tfcodec.dll' if self.c else 'python'

    def decode(self, pkt):
        """Returns a (h, w) uint16 array, or None if the frame can't be decoded."""
        w, h = pkt.w, pkt.h
        key = pkt.type == TFS_VKEY
        prev = None
        if not key:
            if self.prev is None or self.size != (w, h):
                self.errors += 1
                return None
            prev = self.prev
        try:
            img = self.c.decode(pkt.payload, prev, w, h) if self.c else py_decode(pkt.payload, prev, w, h)
        except ValueError:
            self.errors += 1
            self.prev = None
            return None
        self.prev, self.size = img, (w, h)
        return img.reshape(h, w)


def downscale2(img):
    """Reference 2x2 box filter on RGB565 (same rounding as tfc_downscale2)."""
    h, w = img.shape
    a = img[:h // 2 * 2, :w // 2 * 2].astype(np.uint32)
    r, g, b = a >> 11, (a >> 5) & 63, a & 31

    def pool(c):
        return (c[0::2, 0::2] + c[0::2, 1::2] + c[1::2, 0::2] + c[1::2, 1::2] + 2) >> 2
    return ((pool(r) << 11) | (pool(g) << 5) | pool(b)).astype(np.uint16)


# --------------------------------------------------------------------------
# A/V assembly
# --------------------------------------------------------------------------
class Recorder:
    def __init__(self, out, fps=30, av_offset_ms=0, crf=18, preset='veryfast', keep_temp=False, log=print,
                 force_python=False):
        self.out, self.fps, self.av_offset = out, fps, av_offset_ms * 1000
        self.crf, self.preset, self.keep, self.log = crf, preset, keep_temp, log
        self.tmp = tempfile.mkdtemp(prefix='r36rec_', dir=os.path.dirname(os.path.abspath(out)) or None)
        self.vdec = VideoDecoder(force_python)
        self.ff = None
        self.t0 = None           # us, first video frame
        self.size = None
        self.cur = None
        self.n_out = 0
        self.last_vts = None
        self.dup = self.drop = self.frames_in = 0
        self.pending_slot = None
        # audio
        self.apath = os.path.join(self.tmp, 'audio.raw')
        self.af = open(self.apath, 'wb')
        self.achunks = []        # (ts_us, pos, nbytes)
        self.rate = 0
        self.channels = 0
        self.info = {}
        self.end_info = None

    # ---- video ----
    def _start_ffmpeg(self, w, h):
        self.size = (w, h)
        self.vpath = os.path.join(self.tmp, 'video.mkv')
        cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'rawvideo', '-pix_fmt', 'rgb565le', '-s', '%dx%d' % (w, h), '-r', str(self.fps), '-i', '-',
               '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-preset', self.preset,
               '-crf', str(self.crf), '-pix_fmt', 'yuv420p', self.vpath]
        self.ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def _fit(self, img):
        w, h = self.size
        if img.shape == (h, w):
            return img
        ys = (np.arange(h) * img.shape[0] // h)[:, None]
        xs = (np.arange(w) * img.shape[1] // w)[None, :]
        return img[ys, xs]

    def _emit(self):
        self.ff.stdin.write(np.ascontiguousarray(self.cur, '<u2').tobytes())
        self.n_out += 1

    def video(self, pkt):
        img = self.vdec.decode(pkt)
        if img is None:
            return
        self.frames_in += 1
        if self.t0 is None:
            self.t0 = pkt.ts
            self._start_ffmpeg(pkt.w, pkt.h)
        period = 1e6 / self.fps
        if self.cur is not None:
            emitted = 0
            while self.t0 + self.n_out * period + period / 2 <= pkt.ts:
                self._emit(); emitted += 1
            if emitted == 0:
                self.drop += 1                     # replaced before it got a slot
            elif emitted > 1:
                self.dup += emitted - 1
        self.cur = self._fit(img)
        self.last_vts = pkt.ts

    # ---- audio ----
    def audio(self, pkt):
        if pkt.h:
            self.rate = pkt.h
        if pkt.w:
            self.channels = pkt.w
        self.achunks.append((pkt.ts, pkt.extra, len(pkt.payload)))
        self.af.write(pkt.payload)

    def packet(self, pkt):
        if pkt.type in (TFS_VKEY, TFS_VDELTA):
            self.video(pkt)
        elif pkt.type == TFS_AUDIO:
            self.audio(pkt)
        elif pkt.type in (TFS_INFO, TFS_END):
            d = parse_info(pkt.payload)
            self.info = d
            if pkt.type == TFS_END:
                self.end_info = d
            return d
        return None

    def _audio_rate(self):
        if self.rate:
            return self.rate
        if len(self.achunks) > 10:
            total = sum(c[2] for c in self.achunks[:-1]) / 4
            span = (self.achunks[-1][0] - self.achunks[0][0]) / 1e6
            if span > 0.5:
                est = total / span
                std = min((8000, 11025, 16000, 22050, 32000, 44100, 48000), key=lambda r: abs(r - est))
                self.log('audio rate unknown (driver init args not seen); estimated %.0f Hz -> %d' % (est, std))
                return std
        self.log('audio rate unknown; assuming 48000 Hz')
        return 48000

    def _write_wav(self):
        """Lay the captured chunks on a sample timeline. Returns (path, seconds) or None."""
        self.af.close()
        if not self.achunks or self.t0 is None:
            return None
        rate = self._audio_rate()
        ch = self.channels if self.channels in (1, 2) else 2
        fbytes = 2 * ch
        wpath = os.path.join(self.tmp, 'audio.wav')
        lost = gaps = 0
        with open(self.apath, 'rb') as src, wave.open(wpath, 'wb') as wv:
            wv.setnchannels(ch); wv.setsampwidth(2); wv.setframerate(rate)
            written = 0                     # frames written to the wav
            start_us = self.achunks[0][0] + self.av_offset
            lead = int(round((start_us - self.t0) * rate / 1e6))
            trim = 0
            if lead > 0:
                wv.writeframes(b'\0' * lead * fbytes); written = lead
            else:
                trim = -lead * fbytes       # audio started before the first video frame
            exp_pos = None
            for ts, pos, nb in self.achunks:
                data = src.read(nb)
                if exp_pos is not None:
                    gap = (pos - exp_pos) & 0xFFFFFFFF
                    if 0 < gap < 0x80000000:                 # bytes lost on the console
                        lost += gap
                        fill = gap - gap % fbytes
                        if trim:
                            t = min(trim, fill); trim -= t; fill -= t
                        wv.writeframes(b'\0' * fill); written += fill // fbytes
                exp_pos = (pos + nb) & 0xFFFFFFFF
                # pause (no playframe calls) longer than 100 ms -> silence to stay in sync.
                # wav frame k plays at capture time t0 + k/rate.
                late_us = ts + self.av_offset - (self.t0 + written * 1e6 / rate)
                if late_us > 100000 and not trim:
                    fill = int(late_us * rate / 1e6)
                    gaps += 1
                    wv.writeframes(b'\0' * fill * fbytes); written += fill
                if trim:
                    t = min(trim, len(data)); data = data[t:]; trim -= t
                data = data[:len(data) - len(data) % fbytes]
                wv.writeframes(data); written += len(data) // fbytes
        secs = written / rate
        self.log('audio: %d Hz %d ch, %.2f s, %d chunks, %d bytes lost, %d pauses filled'
                 % (rate, ch, secs, len(self.achunks), lost, gaps))
        return wpath, secs

    def finish(self):
        wav = self._write_wav()
        if self.ff is None:
            self.log('no video frames received')
            self.cleanup()
            return False
        # last frame: hold it for at least one slot, and as long as the audio runs
        period = 1e6 / self.fps
        end_us = self.last_vts + period
        if wav:
            end_us = max(end_us, min(self.t0 + wav[1] * 1e6, self.last_vts + 2e6))
        while self.t0 + self.n_out * period < end_us - period / 2:
            self._emit()
        self.ff.stdin.close()
        if self.ff.wait() != 0:
            self.log('ffmpeg (video) failed'); return False
        cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-i', self.vpath]
        if wav:
            cmd += ['-i', wav[0], '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '160k']
        cmd += ['-c:v', 'copy', '-movflags', '+faststart', self.out]
        rc = subprocess.call(cmd)
        self.log('video: %d frames in, %d out at %d fps (%.2f s), %d repeated, %d dropped, decoder %s, %d decode errors'
                 % (self.frames_in, self.n_out, self.fps, self.n_out / self.fps, self.dup, self.drop,
                    self.vdec.backend, self.vdec.errors))
        self.cleanup()
        if rc == 0:
            self.log('wrote %s' % self.out)
        return rc == 0

    def cleanup(self):
        if not self.af.closed:
            self.af.close()
        if not self.keep:
            shutil.rmtree(self.tmp, ignore_errors=True)
        else:
            self.log('temp files kept in %s' % self.tmp)


def status_line(info, rx_bytes, t_start):
    el = max(time.time() - t_start, 1e-3)
    s = '%5.1fs rx %.1f MB (%.2f MB/s)' % (el, rx_bytes / 1e6, rx_bytes / 1e6 / el)
    if info:
        s += ' | video sent %s lost %s backlog %s | audio %s lost %s | shim pid %s' % (
            info.get('v_sent'), info.get('v_lost'), info.get('v_backlog'), info.get('a_sent'),
            info.get('a_lost'), info.get('shim_pid'))
        if 'waiting' in info:
            s += ' | WAITING FOR SHIM (is TF_DRIVER = tfshim.so and a game running?)'
    return s


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def run_file(args, rec):
    parser = StreamParser()
    with open(args.from_file, 'rb') as f:
        parser.feed(f.read())
    for pkt in parser.packets():
        rec.packet(pkt)
    if parser.skipped:
        rec.log('skipped %d junk bytes (%d resyncs)' % (parser.skipped, parser.resyncs))
    return rec.finish()


def run_device(args, rec):
    sys.path.insert(0, HERE)
    from r36 import R36
    r = R36()
    cmd = 'exec %s --fps %d --scale %d --nice %d --keyint %d%s%s 2>/dev/shm/tfrec.err' % (
        args.tfrec, args.fps, args.scale, args.nice, args.keyint, ' --no-audio' if args.no_audio else '',
        ' --seconds %d' % args.seconds if args.seconds else '')
    rec.log('remote: ' + cmd)
    raw = open(args.raw, 'wb') if args.raw else None
    parser = StreamParser()
    job = r.exec_start(cmd)
    t_start, last_status, rx = time.time(), 0, 0
    stopping = None
    try:
        while True:
            try:
                data, state, code, eof, pending = r.job_read(job, 512 * 1024, 100)
                if data:
                    rx += len(data)
                    if raw:
                        raw.write(data)
                    parser.feed(data)
                    for pkt in parser.packets():
                        rec.packet(pkt)
                if state and eof and not pending and not data:
                    break
                if time.time() - last_status > 2:
                    last_status = time.time()
                    print('\r' + status_line(rec.info, rx, t_start), end='', flush=True)
                if stopping and time.time() - stopping > 5:
                    rec.log('\ntfrec did not exit after SIGTERM; killing it')
                    break
                if args.seconds and not stopping and time.time() - t_start > args.seconds + 15:
                    rec.log('\nno end of stream; stopping')
                    r.job_signal(job, 15); stopping = time.time()
            except KeyboardInterrupt:
                if stopping:
                    break
                print('\nstopping (Ctrl+C again to abort)...', flush=True)
                r.job_signal(job, 15)
                stopping = time.time()
    finally:
        try:
            r.job_signal(job, 0)
        except Exception:
            pass
    print()
    if not parser.started:
        code, err = r.run('cat /dev/shm/tfrec.err 2>/dev/null; rm -f /dev/shm/tfrec.err')
        rec.log('no tfrec stream received. tfrec said: %s' % err.decode('utf-8', 'replace').strip())
    r.run('rm -f /dev/shm/tfrec.err')
    r.close()
    if raw:
        raw.close()
    if rec.end_info is None:
        rec.log('note: stream ended without an END packet (tfrec killed?)')
    return rec.finish()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('out', help='output .mp4')
    ap.add_argument('--seconds', type=int, default=0, help='stop after N seconds (0 = until Ctrl+C)')
    ap.add_argument('--fps', type=int, default=30, help='capture and output frame rate (default 30)')
    ap.add_argument('--scale', type=int, default=1, choices=(1, 2), help='2 = half resolution on the console')
    ap.add_argument('--no-audio', action='store_true')
    ap.add_argument('--keyint', type=int, default=10, help='key frame interval in seconds (console side)')
    ap.add_argument('--nice', type=int, default=10, help='nice level of tfrec on the console')
    ap.add_argument('--tfrec', default=TFREC, help='path of tfrec on the console')
    ap.add_argument('--raw', help='also save the raw tfrec stream to this file')
    ap.add_argument('--from-file', help='convert a saved raw stream instead of recording')
    ap.add_argument('--av-offset', type=float, default=0, help='shift audio by MS milliseconds (+ = later)')
    ap.add_argument('--crf', type=int, default=18)
    ap.add_argument('--preset', default='veryfast')
    ap.add_argument('--keep-temp', action='store_true')
    ap.add_argument('--python-decoder', action='store_true', help='do not use tfcodec.dll')
    args = ap.parse_args(argv)
    if not os.path.exists(FFMPEG):
        raise SystemExit('ffmpeg not found (set FFMPEG=...)')
    rec = Recorder(args.out, fps=args.fps, av_offset_ms=args.av_offset, crf=args.crf, preset=args.preset,
                   keep_temp=args.keep_temp, force_python=args.python_decoder)
    ok = run_file(args, rec) if args.from_file else run_device(args, rec)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
