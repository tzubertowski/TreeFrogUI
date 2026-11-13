#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Pavel Kotek
"""Offline end-to-end test of the capture pipeline (no console needed).

1. build/tfsynth.exe simulates game + shim writer + tfrec core (same C code as
   on the console) and writes tfrec streams plus reference frames/audio.
2. Every video packet is decoded with r36rec's decoders (tfcodec.dll and the
   pure-Python one) and compared bit-exactly with the reference frame of the
   same shim seq (2x2 box-downscaled reference for --scale 2); every audio
   packet is compared with the reference PCM at its byte position.
3. r36rec converts the streams to MP4 with ffmpeg; ffprobe checks the result
   and the white-flash / click markers measure the A/V offset.
"""
import json, os, struct, subprocess, sys, time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.dirname(HERE)
BUILD = os.path.join(CAP, 'build')
OUT = os.path.join(BUILD, 'test')
sys.path.insert(0, os.path.join(CAP, '..', 'pc'))
import r36rec  # noqa: E402

FFPROBE = os.path.join(os.path.dirname(r36rec.FFMPEG), 'ffprobe.exe')


def load_ref(prefix):
    frames = {}
    with open(prefix + '.vid', 'rb') as f:
        while True:
            hd = f.read(12)
            if len(hd) < 12:
                break
            seq, w, h = struct.unpack('<III', hd)
            frames[seq] = np.frombuffer(f.read(w * h * 2), '<u2').reshape(h, w)
    pcm = open(prefix + '.pcm', 'rb').read()
    return frames, pcm


def check_stream(path, ref_prefix, scale):
    frames, pcm = load_ref(ref_prefix)
    parser = r36rec.StreamParser()
    parser.feed(open(path, 'rb').read())
    pkts = list(parser.packets())
    assert parser.started and parser.skipped == 0 and parser.resyncs == 0, 'stream framing'
    cdec, pydec = r36rec.VideoDecoder(), r36rec.VideoDecoder(force_python=True)
    assert cdec.backend == 'tfcodec.dll'
    nv = nkey = na = 0
    vbytes = 0
    tpy = tc = 0.0
    for p in pkts:
        if p.type in (r36rec.TFS_VKEY, r36rec.TFS_VDELTA):
            t = time.perf_counter(); a = cdec.decode(p); tc += time.perf_counter() - t
            t = time.perf_counter(); b = pydec.decode(p); tpy += time.perf_counter() - t
            assert a is not None and b is not None, 'undecodable frame seq %d' % p.extra
            ref = frames[p.extra]
            if scale == 2:
                ref = r36rec.downscale2(ref)
            assert a.shape == ref.shape and np.array_equal(a, ref), 'C decode mismatch seq %d' % p.extra
            assert np.array_equal(b, ref), 'python decode mismatch seq %d' % p.extra
            nv += 1; nkey += p.type == r36rec.TFS_VKEY; vbytes += len(p.payload)
        elif p.type == r36rec.TFS_AUDIO:
            assert p.payload == pcm[p.extra:p.extra + len(p.payload)], 'audio mismatch at %d' % p.extra
            assert p.w == 2 and p.h == 48000
            na += 1
    end = [p for p in pkts if p.type == r36rec.TFS_END]
    assert len(end) == 1, 'END packet'
    info = r36rec.parse_info(end[0].payload)
    print('  %s: %d video packets (%d key) bit-exact with C and Python decoders, %d audio chunks exact; '
          'v_lost=%s v_backlog=%s a_lost=%s; video payload %.2f MB; decode C %.1f ms/frame, Python %.1f ms/frame'
          % (os.path.basename(path), nv, nkey, na, info['v_lost'], info['v_backlog'], info['a_lost'],
             vbytes / 1e6, tc / nv * 1e3, tpy / nv * 1e3))
    return nv, na, info


def probe(mp4):
    out = subprocess.check_output([FFPROBE, '-v', 'error', '-show_entries',
                                   'stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels,nb_frames:format=duration',
                                   '-of', 'json', mp4])
    return json.loads(out)


def av_sync(mp4, fps):
    """Return list of (marker_second, video_t, audio_t) using flash + click markers."""
    v = subprocess.check_output([r36rec.FFMPEG, '-v', 'error', '-i', mp4, '-vf', 'scale=32:24,format=gray',
                                 '-f', 'rawvideo', '-'])
    lum = np.frombuffer(v, np.uint8).reshape(-1, 32 * 24).mean(axis=1)
    a = subprocess.check_output([r36rec.FFMPEG, '-v', 'error', '-i', mp4, '-ac', '1', '-ar', '48000',
                                 '-f', 's16le', '-'])
    pcm = np.abs(np.frombuffer(a, '<i2').astype(np.int32))
    flashes = [i for i in range(len(lum)) if lum[i] > 235 and (i == 0 or lum[i - 1] <= 235)]
    loud = np.flatnonzero(pcm > 15000)
    clicks = []
    for s in loud:
        if not clicks or s - clicks[-1][-1] > 4800:
            clicks.append([s, s])
        clicks[-1][-1] = s
    vt = [i / fps for i in flashes]
    at = [c[0] / 48000 for c in clicks]
    pairs = []
    for t in vt:
        if at:
            j = int(np.argmin([abs(x - t) for x in at]))
            pairs.append((t, at[j]))
    return pairs


def fake_device_run(stream, mp4):
    import random, types
    data = open(stream, 'rb').read()
    log = []

    class FakeR36:
        def __init__(self):
            self.pos, self.rnd, self.jobs = 0, random.Random(7), {}

        def exec_start(self, cmd, stdin=False):
            log.append(cmd)
            return 8

        def job_read(self, job, maxlen=512 * 1024, wait_ms=500):
            n = min(self.rnd.choice((0, 1, 23, 4096, 65536, 300000)), maxlen, len(data) - self.pos)
            chunk = data[self.pos:self.pos + n]; self.pos += n
            done = self.pos >= len(data)
            return chunk, (1 if done else 0), 0, done, 0

        def job_signal(self, job, sig):
            log.append('signal %d' % sig)

        def run(self, cmd, **kw):
            log.append(cmd); return 0, b''

        def close(self):
            pass

    sys.modules['r36'] = types.SimpleNamespace(R36=FakeR36)
    rc = r36rec.main([mp4, '--seconds', '8', '--fps', '30', '--scale', '1'])
    pr = probe(mp4)
    dur = float(pr['format']['duration'])
    good = (rc == 0 and log[0].startswith('exec /mnt/sdcard/cubegm/tfrec --fps 30 --scale 1') and 'signal 0' in log
            and 7.5 < dur < 8.6 and max(abs((a - v) * 1000) for v, a in av_sync(mp4, 30)) <= 1000 / 30 + 10)
    print('  remote command: %s' % log[0])
    print('  %s: %.2f s, job released with signal 0: %s' % ('ok' if good else 'FAIL', dur, 'signal 0' in log))
    return good


def main():
    os.makedirs(OUT, exist_ok=True)
    synth = os.path.join(BUILD, 'tfsynth.exe')
    cases = [
        ('s1', ['--scale', '1', '--fps', '30', '--seconds', '8'], 1),
        ('s2', ['--scale', '2', '--fps', '30', '--seconds', '8'], 2),
        ('s1stall', ['--scale', '1', '--fps', '30', '--seconds', '8', '--stall', '--bw', '2500000'], 1),
        ('s1all', ['--scale', '1', '--fps', '0', '--seconds', '4'], 1),
        ('s1hard', ['--scale', '1', '--fps', '30', '--seconds', '8', '--hard', '--bw', '6000000'], 1),
        ('s2hard', ['--scale', '2', '--fps', '30', '--seconds', '8', '--hard', '--bw', '6000000'], 2),
    ]
    ok = True
    for name, opts, scale in cases:
        stream, ref = os.path.join(OUT, name + '.tfr'), os.path.join(OUT, name + '_ref')
        print('[%s] tfsynth %s' % (name, ' '.join(opts)))
        r = subprocess.run([synth, 'stream', stream, ref] + opts, capture_output=True, text=True)
        print('  ' + r.stdout.strip())
        assert r.returncode == 0, r.stderr
        check_stream(stream, ref, scale)

    for name, fps in (('s1', 30), ('s2', 30), ('s1stall', 30), ('s1hard', 30)):
        mp4 = os.path.join(OUT, name + '.mp4')
        print('[%s] r36rec --from-file -> %s' % (name, os.path.basename(mp4)))
        t = time.perf_counter()
        rc = r36rec.main([mp4, '--from-file', os.path.join(OUT, name + '.tfr'), '--fps', str(fps)])
        el = time.perf_counter() - t
        assert rc == 0 and os.path.exists(mp4)
        pr = probe(mp4)
        st = {s['codec_type']: s for s in pr['streams']}
        dur = float(pr['format']['duration'])
        print('  mp4: %s %sx%s %s fps, %s %s Hz %s ch, %.2f s, %d KB (conversion %.1f s)'
              % (st['video']['codec_name'], st['video']['width'], st['video']['height'], st['video']['r_frame_rate'],
                 st['audio']['codec_name'], st['audio']['sample_rate'], st['audio']['channels'], dur,
                 os.path.getsize(mp4) // 1024, el))
        assert st['video']['codec_name'] == 'h264' and st['audio']['codec_name'] == 'aac'
        assert 7.5 < dur < 8.6, 'duration %.2f' % dur
        pairs = av_sync(mp4, fps)
        offs = [(a - v) * 1000 for v, a in pairs]
        print('  A/V markers: %d; audio-minus-video offsets ms: %s' % (len(pairs), ' '.join('%+.0f' % o for o in offs)))
        if len(pairs) < 6 or max(abs(o) for o in offs) > 1000 / fps + 10:
            print('  A/V SYNC OUT OF TOLERANCE'); ok = False
    # live path of r36rec with a fake console (same R36 job API, random chunking)
    print('[device loop] r36rec live path against a fake R36 serving s1.tfr')
    ok &= fake_device_run(os.path.join(OUT, 's1.tfr'), os.path.join(OUT, 'live.mp4'))
    print('ALL OK' if ok else 'FAILURES')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
