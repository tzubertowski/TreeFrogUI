"""Exercise a synthetic MIPS state observer and a wrong-profile negative control.

Uses existing artifacts, saved console runtime and owned QEMU VM only. No console.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from verify_ui_core_trace import ROOT, WORK, RUNTIME_FILES, forwarding_result


def state_result(control, valid, rejected):
    state_lines = [line for line in valid['stderr'].splitlines() if line.startswith('ui-state:')]
    plain = dict(valid, stderr='\n'.join(line for line in valid['stderr'].splitlines()
                                        if not line.startswith('ui-state:')) + '\n')
    negative = dict(rejected, stderr='\n'.join(line for line in rejected['stderr'].splitlines()
                                             if not line.startswith('ui-state:')) + '\n')
    return (forwarding_result(control, plain) and forwarding_result(control, negative)
            and len(state_lines) == 5 and state_lines[0].startswith('ui-state: profile_bound ')
            and state_lines[1:] == [
                'ui-state: run=1 phase=enter counter=0 flag=0',
                'ui-state: run=1 phase=leave counter=1 flag=1',
                'ui-state: run=2 phase=enter counter=1 flag=1',
                'ui-state: run=2 phase=leave counter=2 flag=1']
            and [line for line in rejected['stderr'].splitlines() if line.startswith('ui-state:')]
            == ['ui-state: profile_rejected observation_disabled=1'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error('output must be new with existing parent')
    base = ROOT / 'analysis/driver_port'
    sources = {'harness': base / 'ui_core_trace_test_v1/harness',
               'frogui_libretro.so': base / 'ui_state_synthetic_v1/frogui_libretro.so',
               'valid.so': base / 'ui_state_synthetic_v1/trace-v2.so',
               'rejected.so': base / 'r36-ui-state-trace-v3.so'}
    options = ['-i', str(WORK / 'id_ed25519'), '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
               '-o', 'UserKnownHostsFile=' + str(WORK / 'known_hosts')]
    ssh = ['ssh', '-p', '22222', *options, 'root@127.0.0.1']
    scp = ['scp', '-P', '22222', *options]
    remote = '/work/ui-state-test-' + str(time.time_ns())
    runtime = '/work/console_runtime_20261115_v1'
    args.out.mkdir()
    subprocess.run(ssh + ['mkdir ' + remote], check=True, timeout=10)
    hashes = {}
    for name, path in sources.items():
        hashes[remote + '/' + name] = hashlib.sha256(path.read_bytes()).hexdigest()
        subprocess.run(scp + [str(path), 'root@127.0.0.1:' + remote + '/' + name], check=True, timeout=15)
    for name in RUNTIME_FILES:
        hashes[runtime + '/' + name] = hashlib.sha256((base / 'console_runtime_20261115_v1' / name).read_bytes()).hexdigest()
    checked = subprocess.run(ssh + ['sha256sum ' + ' '.join(hashes)], capture_output=True, text=True, check=True, timeout=10)
    assert {line.split()[1]: line.split()[0] for line in checked.stdout.splitlines()} == hashes
    results = []
    for name in (None, 'valid.so', 'rejected.so'):
        env = '-E LD_PRELOAD=' + remote + '/' + name if name else '-U LD_PRELOAD'
        command = ('chmod +x ' + remote + '/harness; timeout 15 qemu-mipsel -cpu 74Kf ' + env + ' ' +
                   runtime + '/ld.so.1 --library-path ' + runtime + ' ' + remote + '/harness ' + remote + '/frogui_libretro.so')
        p = subprocess.run(ssh + [command], capture_output=True, text=True, timeout=25)
        results.append({'preload': name, 'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})
    passed = state_result(*results)
    report = {'passed': passed, 'hardware_verified': False, 'camera_used': False,
              'scope': 'Synthetic MIPS core state observations and wrong-profile rejection with saved console glibc/QEMU-user',
              'sha256_by_VM_path': hashes, 'cases': results}
    (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print('UI_STATE_FORWARDING=' + ('PASS' if passed else 'FAIL'))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
