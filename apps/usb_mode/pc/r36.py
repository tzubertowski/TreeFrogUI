#!/usr/bin/env python3
"""r36 - control an R36S (TreeFrogUI + tfmtp) over its MTP connection.

Everything goes through the Windows MTP driver (WPD "MTP extension" commands),
so no extra USB driver is needed and Explorer keeps working at the same time.

  r36.py info                      tfmtp version / remote status
  r36.py sh "command"              run a shell command, print output, exit with its code
  r36.py shell                     simple interactive shell (one command per line)
  r36.py ls  /cubegm               list a folder (raw MTP)
  r36.py put local /cubegm/name    upload a file (raw MTP; replaces an existing file)
  r36.py get /cubegm/name local    download a file (raw MTP)
  r36.py rm  /cubegm/name          delete a file or folder (raw MTP)
  r36.py key press START [-t ms]   press console buttons (tfkey)
  r36.py key seq "A 100, 300, B"   button sequence
  r36.py reboot                    reboot the console and wait until it is back
  r36.py shot [file.png]           screenshot (menu and games)

Paths for ls/put/get/rm are relative to the SD card root.
"""
import os, sys, time, ctypes, struct

import comtypes, comtypes.gen, comtypes.client as cc
from comtypes import GUID

_GEN = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'r36', 'comtypes_gen')
os.makedirs(_GEN, exist_ok=True)
cc.gen_dir = _GEN
if _GEN not in comtypes.gen.__path__:
    comtypes.gen.__path__.insert(0, _GEN)
_api = cc.GetModule("portabledeviceapi.dll")
_typ = cc.GetModule("portabledevicetypes.dll")

_CMN = '{F0422A9C-5DC8-4440-B5BD-5DF28835658A}'
_MTPX = '{4D545058-1A2E-4106-A357-771E0819FC56}'

def _key(guid, pid):
    k = _typ._tagpropertykey(); k.fmtid = GUID(guid); k.pid = pid; return k

K_CAT, K_ID, K_HR = _key(_CMN, 1001), _key(_CMN, 1002), _key(_CMN, 1003)
K_OPC, K_OPP, K_RC, K_RP = (_key(_MTPX, i) for i in (1001, 1002, 1003, 1004))
K_CTX, K_TOTAL = _key(_MTPX, 1006), _key(_MTPX, 1007)
K_TOREAD, K_READ, K_TOWRITE, K_WRITTEN, K_DATA = (_key(_MTPX, i) for i in (1008, 1009, 1010, 1011, 1012))
CMD_NODATA, CMD_READ, CMD_WRITE, READ_DATA, WRITE_DATA, END_XFER = 12, 13, 14, 15, 16, 17

OP_TF_Info, OP_TF_Exec, OP_TF_Read, OP_TF_Write, OP_TF_Signal = 0x9A00, 0x9A01, 0x9A02, 0x9A03, 0x9A04
STORAGE = 0x00010001
ROOT = 0xFFFFFFFF


class MtpError(Exception):
    def __init__(self, op, rc, msg=''):
        super().__init__('MTP op 0x%04X -> 0x%04X %s' % (op, rc, msg))
        self.op, self.rc = op, rc


def _values():
    return cc.CreateObject(_typ.PortableDeviceValues, interface=_typ.IPortableDeviceValues)


def _count(c):
    n = ctypes.c_ulong(0); c.GetCount(ctypes.byref(n)); return n.value


def _pv_u4(v):
    pv = (ctypes.c_ubyte * 24)()
    struct.pack_into('<H', pv, 0, 19)          # VT_UI4
    struct.pack_into('<I', pv, 8, v & 0xFFFFFFFF)
    return ctypes.cast(pv, ctypes.POINTER(_typ.tag_inner_PROPVARIANT)), pv


class R36:
    def __init__(self, match='vid_18d1&pid_4e22'):
        mgr = cc.CreateObject(_api.PortableDeviceManager, interface=_api.IPortableDeviceManager)
        n = ctypes.c_ulong(0)
        mgr._IPortableDeviceManager__com_GetDevices(None, ctypes.byref(n))
        arr = (ctypes.c_wchar_p * max(n.value, 1))()
        mgr._IPortableDeviceManager__com_GetDevices(arr, ctypes.byref(n))
        ids = [arr[i] for i in range(n.value) if arr[i] and match in arr[i].lower()]
        if not ids:
            raise SystemExit('R36S not found: put the console in USB (MTP) mode and connect the cable.')
        self.dev = cc.CreateObject(_api.PortableDevice, interface=_api.IPortableDevice)
        self.dev.Open(ids[0], _values())

    def close(self):
        self.dev.Close()

    # ---- raw WPD plumbing ----
    def _cmd(self, cid, **kv):
        p = _values()
        p.SetGuidValue(K_CAT, GUID(_MTPX)); p.SetUnsignedIntegerValue(K_ID, cid)
        keep = []
        for k, v in kv.items():
            key = globals()['K_' + k]
            if k == 'OPP':
                c = cc.CreateObject(_typ.PortableDevicePropVariantCollection, interface=_typ.IPortableDevicePropVariantCollection)
                for x in v:
                    ptr, buf = _pv_u4(x); keep.append(buf); c.Add(ptr)
                p.SetIPortableDevicePropVariantCollectionValue(key, c)
            elif k == 'CTX':
                p.SetStringValue(key, v)
            elif k == 'DATA':
                b = (ctypes.c_ubyte * max(len(v), 1)).from_buffer_copy(v if v else b'\0')
                keep.append(b); p.SetBufferValue(key, b, len(v))
            elif k == 'TOTAL':
                p.SetUnsignedLargeIntegerValue(key, v)
            else:
                p.SetUnsignedIntegerValue(key, v)
        r = self.dev.SendCommand(0, p).QueryInterface(_typ.IPortableDeviceValues)
        hr = (r.GetErrorValue(K_HR) or 0) & 0xFFFFFFFF
        if hr:
            raise OSError('WPD command %d failed: HRESULT 0x%08X' % (cid, hr))
        return r

    @staticmethod
    def _resp(r):
        rc = r.GetUnsignedIntegerValue(K_RC)
        out = []
        try:
            c = r.GetIPortableDevicePropVariantCollectionValue(K_RP).QueryInterface(_typ.IPortableDevicePropVariantCollection)
            for i in range(_count(c)):
                pv = (ctypes.c_ubyte * 24)()
                c.GetAt(i, ctypes.cast(pv, ctypes.POINTER(_typ.tag_inner_PROPVARIANT)))
                out.append(struct.unpack_from('<I', pv, 8)[0])
        except Exception:
            pass
        return rc, out

    def op(self, code, params=(), data_out=None, read=False, check=True):
        """Run one MTP operation. Returns (response_code, response_params, data_in)."""
        params = list(params)
        data = b''
        if data_out is not None:
            r = self._cmd(CMD_WRITE, OPC=code, OPP=params, TOTAL=len(data_out))
            ctx = r.GetStringValue(K_CTX)
            off, chunk = 0, 256 * 1024
            while off < len(data_out):
                part = data_out[off:off + chunk]
                self._cmd(WRITE_DATA, CTX=ctx, TOWRITE=len(part), DATA=part)
                off += len(part)
            r = self._cmd(END_XFER, CTX=ctx)
        elif read:
            r = self._cmd(CMD_READ, OPC=code, OPP=params)
            ctx = r.GetStringValue(K_CTX)
            total = int(r.GetUnsignedLargeIntegerValue(K_TOTAL))
            parts, got = [], 0
            while got < total:
                want = min(total - got, 1024 * 1024)
                rr = self._cmd(READ_DATA, CTX=ctx, TOREAD=want, DATA=bytes(want))
                buf, n = rr.GetBufferValue(K_DATA)
                if n == 0:
                    break
                parts.append(ctypes.string_at(buf, n)); got += n
                ctypes.windll.ole32.CoTaskMemFree(buf)
            data = b''.join(parts)
            r = self._cmd(END_XFER, CTX=ctx)
        else:
            r = self._cmd(CMD_NODATA, OPC=code, OPP=params)
        rc, rp = self._resp(r)
        if check and rc != 0x2001:
            raise MtpError(code, rc)
        return rc, rp, data

    # ---- remote shell ----
    def info(self):
        return self.op(OP_TF_Info, read=True)[2].decode('utf-8', 'replace')

    def exec_start(self, command, stdin=False):
        return self.op(OP_TF_Exec, [1 if stdin else 0], data_out=command.encode('utf-8'))[1][0]

    def job_read(self, job, maxlen=512 * 1024, wait_ms=500):
        _, rp, data = self.op(OP_TF_Read, [job, maxlen, wait_ms], read=True)
        state, code, pending = rp
        return data, state & 0xFF, code, bool(state & 0x100), pending

    def job_write(self, job, data, close=False):
        off = 0
        while True:
            part = data[off:off + 256 * 1024]
            last = off + len(part) >= len(data)
            acc = self.op(OP_TF_Write, [job, 1 if (close and last) else 0], data_out=part)[1][0]
            off += acc
            if off >= len(data):
                return
            if acc == 0:
                time.sleep(0.05)

    def job_signal(self, job, sig):
        self.op(OP_TF_Signal, [job, sig], check=False)

    def run(self, command, stdin_data=None, out=None, timeout=None):
        """Run a command; stream output to `out` (file-like, binary) or collect it. Returns (code, bytes)."""
        job = self.exec_start(command, stdin=stdin_data is not None)
        if stdin_data is not None:
            self.job_write(job, stdin_data, close=True)
        chunks, t0 = [], time.time()
        try:
            while True:
                data, state, code, eof, pending = self.job_read(job)
                if data:
                    if out is not None:
                        out.write(data); out.flush()
                    else:
                        chunks.append(data)
                if state and eof and not pending and not data:
                    return (code if state == 1 else 128 + code), b''.join(chunks)
                if timeout and time.time() - t0 > timeout:
                    self.job_signal(job, 9)
                    raise TimeoutError(command)
        finally:
            self.job_signal(job, 0)

    # ---- raw file access (independent of Explorer) ----
    def children(self, parent):
        _, _, d = self.op(0x9805, [parent, 0, 0xDC07, 0, 1], read=True)   # GetObjectPropList FileName depth 1
        n = struct.unpack_from('<I', d, 0)[0]; o = 4; res = {}
        for _ in range(n):
            h, prop, dt = struct.unpack_from('<IHH', d, o); o += 8
            cnt = d[o]; o += 1
            name = d[o:o + cnt * 2].decode('utf-16-le').rstrip('\0'); o += cnt * 2
            res[name] = h
        return res

    def lookup(self, path):
        h = ROOT
        for part in [p for p in path.replace('\\', '/').split('/') if p]:
            ch = self.children(h)
            if part not in ch:
                return None
            h = ch[part]
        return h

    def put(self, local, remote):
        remote = remote.replace('\\', '/')
        folder, name = remote.rsplit('/', 1) if '/' in remote.strip('/') else ('', remote.strip('/'))
        parent = self.lookup(folder)
        if parent is None:
            raise FileNotFoundError(folder)
        old = self.children(parent).get(name)
        if old:
            self.op(0x100B, [old])
        data = open(local, 'rb').read()
        oi = bytearray(52)
        struct.pack_into('<IHHI', oi, 0, STORAGE, 0x3000, 0, len(data))
        u = name.encode('utf-16-le') + b'\0\0'
        oi += bytes([len(u) // 2]) + u + b'\0\0\0'
        self.op(0x100C, [STORAGE, 0 if parent == ROOT else parent], data_out=bytes(oi))
        self.op(0x100D, [], data_out=data)
        return len(data)

    def get(self, remote, local):
        h = self.lookup(remote)
        if h is None:
            raise FileNotFoundError(remote)
        data = self.op(0x1009, [h], read=True)[2]
        open(local, 'wb').write(data)
        return len(data)

    def rm(self, remote):
        h = self.lookup(remote)
        if h is None:
            raise FileNotFoundError(remote)
        self.op(0x100B, [h])


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    cmd, args = argv[1], argv[2:]
    r = R36()
    try:
        if cmd == 'info':
            print(r.info(), end='')
        elif cmd == 'sh':
            code, _ = r.run(' '.join(args), out=sys.stdout.buffer)
            return code
        elif cmd == 'shell':
            print(r.info(), end='')
            while True:
                try:
                    line = input('r36# ')
                except EOFError:
                    break
                if line.strip() in ('exit', 'quit'):
                    break
                if line.strip():
                    code, _ = r.run(line, out=sys.stdout.buffer)
                    if code:
                        print('[exit %d]' % code)
        elif cmd == 'ls':
            h = r.lookup(args[0] if args else '/')
            for name in sorted(r.children(h)):
                print(name)
        elif cmd == 'put':
            print('uploaded %d bytes' % r.put(args[0], args[1]))
        elif cmd == 'get':
            print('downloaded %d bytes' % r.get(args[0], args[1]))
        elif cmd == 'rm':
            r.rm(args[0]); print('deleted')
        elif cmd == 'reboot':
            r.run('sync; (sleep 1; sync; reboot) </dev/null >/dev/null 2>&1 &')
            r.close(); r = None
            t0 = time.time()
            print('rebooting...', flush=True)
            time.sleep(15)
            while time.time() - t0 < 180:
                try:
                    r = R36()
                    print('back after %.0f s: %s' % (time.time() - t0, r.info().strip()))
                    break
                except BaseException:
                    r = None
                    time.sleep(3)
            else:
                print('console did not come back within 180 s'); return 1
        elif cmd == 'shot':
            import fbshot
            path = args[0] if args else 'r36_%s.png' % time.strftime('%Y%m%d_%H%M%S')
            w, h, rgb = fbshot.grab(r)
            fbshot.png(path, w, h, rgb)
            print(path)
        elif cmd == 'key':
            code, _ = r.run('/mnt/sdcard/cubegm/tfkey ' + ' '.join(args), out=sys.stdout.buffer)
            return code
        else:
            print(__doc__); return 2
    finally:
        if r is not None:
            r.close()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
