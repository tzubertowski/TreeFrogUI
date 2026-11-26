"""Owned Linux VM only: actual direction-only publisher/uinput/SysV test.

Reuses device helpers; refuses preexisting publisher state. No console access.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import legacy_keys_integration as lab


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publisher', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    token, lock = Path('/tmp/joy_key'), Path('/tmp/r36-legacy-keys.lock')
    if token.exists() or lock.exists():
        raise RuntimeError('existing publisher state: refusing test')
    args.out.mkdir()
    device = None
    child = None
    shared = None
    try:
        device = lab.make_device('r36-navigation-direction-test')
        mapping = args.out / 'directions.map'
        mapping.write_text('30 4\n48 5\n31 6\n32 7\n')
        log = (args.out / 'publisher.log').open('w+')
        child = subprocess.Popen([str(args.publisher), str(mapping), str(device[1])], stdout=log, stderr=log)
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError('publisher startup failed')
            if token.exists() and 'keys_diagnostic_ready=1' in (args.out / 'publisher.log').read_text():
                key = lab.libc.ftok(os.fsencode(token), ord('a'))
                segment = lab.libc.shmget(key, 4, 0o600)
                if segment >= 0:
                    shared = lab.libc.shmat(segment, None, 0)
                    if shared != ctypes.c_void_p(-1).value:
                        break
                    shared = None
            time.sleep(.02)
        if shared is None:
            raise RuntimeError('ready segment missing')
        word = ctypes.c_uint32.from_address(shared)
        def expect(value):
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if word.value == value:
                    return
                time.sleep(.005)
            raise AssertionError((word.value, value))
        expect(0)
        lab.emit(device[0], lab.KEY_A, 1); expect(1 << 4)
        lab.emit(device[0], lab.KEY_A, 0); expect(0)
        lab.emit(device[0], lab.KEY_B, 1); expect(1 << 5)
        lab.emit(device[0], lab.KEY_B, 0); expect(0)
        child.send_signal(signal.SIGTERM); child.wait(timeout=3)
        expect(0)
        assert child.returncode == 0 and lab.libc.shmget(key, 4, 0o600) < 0
        log.close()
        text = (args.out / 'publisher.log').read_text()
        assert 'keys_diagnostic_end requested_stop=1 final_word=00000000' in text
        # Bad map rejected before opening devices/creating any segment.
        mapping.write_text('30 13\n48 5\n31 6\n32 7\n')
        wrong = subprocess.run([str(args.publisher), str(mapping), str(device[1])], capture_output=True, timeout=3)
        assert wrong.returncode == 2 and lab.libc.shmget(key, 4, 0o600) < 0
        report = {'passed': True, 'scope': 'Native Linux publisher in owned VM with real uinput/evdev/SysV, not MIPS hardware',
                  'ready_marker_verified': True, 'direction_press_release_verified': True,
                  'graceful_zero_and_segment_removal_verified': True,
                  'confirm_bit_map_rejected': True, 'publisher_log': text}
        (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    finally:
        if child and child.poll() is None:
            child.terminate(); child.wait(timeout=3)
        if shared is not None:
            lab.libc.shmdt(shared)
        if device:
            import fcntl
            fcntl.ioctl(device[0], lab.UI_DEV_DESTROY); os.close(device[0])
        for node, dev in lab.created_nodes:
            if node.exists() and node.stat().st_rdev == dev:
                node.unlink()
        for path in (token, lock):
            if path.is_file():
                path.unlink()


if __name__ == '__main__':
    main()
