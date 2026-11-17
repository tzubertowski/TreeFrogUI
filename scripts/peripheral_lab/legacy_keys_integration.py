"""Real uinput->evdev->legacy publisher->SysV test in the owned Linux VM only.

Creates two named virtual input devices and a new temporary working directory.
The production publisher remains unmodified: its real fixed /tmp paths are used.
Refuses an existing joy_key token/lock rather than touching someone else's state.
"""
import argparse
import ctypes
import fcntl
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import time

EV_SYN, EV_KEY, SYN_REPORT = 0, 1, 0
KEY_A, KEY_B = 30, 48
UI_SET_EVBIT, UI_SET_KEYBIT = 0x40045564, 0x40045565
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
created_nodes = []
libc = ctypes.CDLL(None, use_errno=True)
libc.ftok.argtypes = [ctypes.c_char_p, ctypes.c_int]; libc.ftok.restype = ctypes.c_int
libc.shmget.argtypes = [ctypes.c_int, ctypes.c_size_t, ctypes.c_int]; libc.shmget.restype = ctypes.c_int
libc.shmat.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]; libc.shmat.restype = ctypes.c_void_p
libc.shmdt.argtypes = [ctypes.c_void_p]; libc.shmdt.restype = ctypes.c_int


def make_device(name):
    fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
    try:
        fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
        for code in (KEY_A, KEY_B): fcntl.ioctl(fd, UI_SET_KEYBIT, code)
        # struct uinput_user_dev: name80 + input_id8 + ff_effects_max4 + 4*64 ints
        descriptor = struct.pack('80sHHHHI', name.encode(), 3, 0x1234, 0x5678, 1, 0) + bytes(4 * 64 * 4)
        os.write(fd, descriptor); fcntl.ioctl(fd, UI_DEV_CREATE)
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            for p in Path('/sys/class/input').glob('event*/device/name'):
                if p.read_text().strip() == name:
                    node = Path('/dev/input') / p.parts[-3]
                    if not node.exists():
                        numbers = p.parent.parent / 'dev'
                        major, minor = map(int, numbers.read_text().strip().split(':'))
                        node.parent.mkdir(exist_ok=True)
                        # Minimal VM has no udev; create only the event node for
                        # the virtual device whose exact name we just matched.
                        import stat
                        os.mknod(node, stat.S_IFCHR | 0o600, os.makedev(major, minor))
                        created_nodes.append((node, node.stat().st_rdev))
                    if node.exists(): return fd, node
            time.sleep(.02)
        raise RuntimeError('virtual input event device did not appear')
    except BaseException:
        try: fcntl.ioctl(fd, UI_DEV_DESTROY)
        except OSError: pass
        os.close(fd); raise


def emit(fd, code, value):
    os.write(fd, struct.pack('@llHHi', 0, 0, EV_KEY, code, value) +
                 struct.pack('@llHHi', 0, 0, EV_SYN, SYN_REPORT, 0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publisher', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--emulator-wrapper', type=Path, help='optional bounded MIPS libretro process reading the actual publisher segment')
    args = parser.parse_args()
    token, lock = Path('/tmp/joy_key'), Path('/tmp/r36-legacy-keys.lock')
    if token.exists() or lock.exists(): raise RuntimeError('existing publisher state: refusing test')
    args.out.mkdir(exist_ok=False)
    devices, child, shared = [], None, None
    report = {'scope': 'real Linux uinput/evdev/SysV integration in owned VM, not console hardware', 'hardware_verified': False, 'cases': []}
    mapping = args.out / 'mapping.txt'; mapping.write_text('30 13\n48 13\n' if args.emulator_wrapper else '30 14\n48 14\n')
    mask = 1 << (13 if args.emulator_wrapper else 14)
    try:
        for i in range(2): devices.append(make_device('r36-bridge-test-' + str(i)))
        # Initial held-key state must be visible via EVIOCGKEY at startup.
        emit(devices[0][0], KEY_A, 1)
        child = subprocess.Popen([str(args.publisher), str(mapping), *[str(n) for _, n in devices]], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if token.exists():
                key = libc.ftok(os.fsencode(token), ord('a'))
                segment = libc.shmget(key, 4, 0o600)
                if segment >= 0:
                    shared = libc.shmat(segment, None, 0)
                    if shared != ctypes.c_void_p(-1).value: break
                    shared = None
            if child.poll() is not None: raise RuntimeError('publisher exited during startup: ' + str(child.communicate()))
            time.sleep(.02)
        if shared is None: raise RuntimeError('publisher shared memory missing')
        word = ctypes.c_uint32.from_address(shared)
        def expect(value, title):
            until = time.monotonic() + 2
            while time.monotonic() < until:
                if word.value == value: report['cases'].append(title); return
                time.sleep(.005)
            raise AssertionError((title, hex(word.value), hex(value)))
        expect(mask, 'held_at_start')
        emit(devices[1][0], KEY_A, 1); expect(mask, 'second_source_pressed')
        emit(devices[0][0], KEY_A, 0); expect(mask, 'one_source_release_keeps_other')
        emit(devices[1][0], KEY_B, 1); emit(devices[1][0], KEY_A, 0)
        expect(mask, 'alias_release_keeps_other_code')
        emit(devices[1][0], KEY_B, 0); expect(0, 'all_released')
        if args.emulator_wrapper:
            import select
            with (args.out / 'emulator.log').open('w+') as log:
                emulator = subprocess.Popen([str(args.emulator_wrapper)], stdout=log, stderr=log, text=True)
                try:
                    until = time.monotonic() + 8
                    ready = False
                    while time.monotonic() < until:
                        log.flush()
                        if 'SHARED_INPUT_READY' in (args.out / 'emulator.log').read_text():
                            ready = True; break
                        if emulator.poll() is not None: break
                        time.sleep(.02)
                    if not ready: raise RuntimeError('MIPS emulator did not attach to real SysV input')
                    time.sleep(.25)
                    emit(devices[0][0], KEY_A, 1); expect(mask, 'emulator_real_press')
                    time.sleep(.55)
                    emit(devices[0][0], KEY_A, 0); expect(0, 'emulator_real_release')
                    emulator.wait(timeout=12)
                    output = (args.out / 'emulator.log').read_text()
                    if emulator.returncode or 'LIBRETRO_SYNTHETIC_EXECUTION=PASS' not in output:
                        raise AssertionError(output)
                    report['emulator_stdout'] = output
                    report['cases'].append('real_evdev_SysV_MIPS_core_ROM_input_roundtrip')
                finally:
                    if emulator.poll() is None:
                        emulator.terminate(); emulator.wait(timeout=3)
        emit(devices[0][0], KEY_A, 1); expect(mask, 'held_before_disconnect')
        fcntl.ioctl(devices[0][0], UI_DEV_DESTROY); os.close(devices[0][0]); devices[0] = (-1, devices[0][1])
        child.wait(timeout=3); expect(0, 'disconnect_clears_shared_word')
        assert child.returncode != 0, 'unexpected successful exit on input loss'
        assert libc.shmget(key, 4, 0o600) < 0, 'segment not removed'
        report['cases'].append('segment_removed_after_fault')
        report['passed'] = True
        (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    finally:
        if child and child.poll() is None:
            child.send_signal(signal.SIGTERM); child.wait(timeout=3)
        if shared is not None: libc.shmdt(shared)
        for fd, _ in devices:
            if fd >= 0:
                try: fcntl.ioctl(fd, UI_DEV_DESTROY)
                finally: os.close(fd)
        for node, device_number in created_nodes:
            if node.exists() and node.stat().st_rdev == device_number:
                node.unlink()
        # These paths did not exist before this test. No arbitrary cleanup.
        for p in (token, lock):
            if p.is_file(): p.unlink()


if __name__ == '__main__':
    main()
