"""Verify existing MIPS trace artifacts in the owned VM, without rebuilding.

Runs the same synthetic forwarding harness with and without the preload. Never
contacts the console. Requires byte-identical local/remote saved console runtime.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'analysis/kernel_build_vm_v1'
RUNTIME_FILES = ('ld.so.1', 'libc.so.6', 'libdl.so.2', 'libpthread.so.0')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def forwarding_result(control, traced):
    """A harness PASS alone cannot prove the observer was actually loaded."""
    expected = (
        'ui-core: video_callback_installed=1',
        'ui-core: run_enter=1 videos=0',
        'ui-core: video=1 RGB565_hash=b0429dc4 nonzero_bytes=1',
        'ui-core: run_leave=1 videos=1',
        'ui-core: run_enter=2 videos=1',
        'ui-core: video=2 RGB565_hash=d0271dc7 nonzero_bytes=1',
        'ui-core: run_leave=2 videos=2',
        'ui-core: video_callback_installed=0',
    )
    return (
        control['exit'] == traced['exit'] == 0
        and control['stdout'].splitlines() == ['CORE_TRACE_FORWARDING=PASS']
        and not control['stderr']
        and traced['stdout'].splitlines() == ['CORE_TRACE_FORWARDING=PASS']
        and traced['stderr'].splitlines() == list(expected)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, default=ROOT / 'analysis/driver_port/ui_core_trace_test_v1')
    parser.add_argument('--trace', type=Path, default=ROOT / 'analysis/driver_port/r36-ui-core-trace-v1.so')
    parser.add_argument('--runtime', type=Path, default=ROOT / 'analysis/driver_port/console_runtime_20261115_v1')
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error('output must be new with existing parent')
    artifacts = {'harness': args.artifacts / 'harness',
                 'frogui_libretro.so': args.artifacts / 'frogui_libretro.so',
                 'trace.so': args.trace}
    runtime_hashes = {name: sha(args.runtime / name) for name in RUNTIME_FILES}
    artifact_hashes = {name: sha(path) for name, path in artifacts.items()}
    options = ['-i', str(WORK / 'id_ed25519'), '-o', 'BatchMode=yes',
               '-o', 'ConnectTimeout=5', '-o', 'UserKnownHostsFile=' + str(WORK / 'known_hosts')]
    ssh = ['ssh', '-p', '22222', *options, 'root@127.0.0.1']
    scp = ['scp', '-P', '22222', *options]
    directory = '/work/ui-core-trace-verify-' + str(time.time_ns())
    runtime = '/work/console_runtime_20261115_v1'
    args.out.mkdir()
    subprocess.run(ssh + ['mkdir ' + shlex.quote(directory)], check=True, timeout=10)
    for name, path in artifacts.items():
        subprocess.run(scp + [str(path), 'root@127.0.0.1:' + directory + '/' + name], check=True, timeout=20)
    paths = {directory + '/' + name: digest for name, digest in artifact_hashes.items()}
    paths.update({runtime + '/' + name: digest for name, digest in runtime_hashes.items()})
    check = subprocess.run(ssh + ['sha256sum ' + ' '.join(shlex.quote(p) for p in paths)],
                           capture_output=True, text=True, check=True, timeout=10)
    actual = {line.split()[1]: line.split()[0] for line in check.stdout.splitlines()}
    if actual != paths:
        raise RuntimeError('VM artifacts/runtime do not match local hashes; refusing execution')
    command = ('chmod +x ' + shlex.quote(directory + '/harness') + '; timeout 15 qemu-mipsel -cpu 74Kf ')
    loader = (runtime + '/ld.so.1 --library-path ' + runtime + ' ' +
              directory + '/harness ' + directory + '/frogui_libretro.so')
    cases = []
    for preload in (False, True):
        env = '-E LD_PRELOAD=' + directory + '/trace.so ' if preload else '-U LD_PRELOAD '
        result = subprocess.run(ssh + [command + env + loader], capture_output=True, text=True, timeout=25)
        cases.append({'preload': preload, 'exit': result.returncode,
                      'stdout': result.stdout, 'stderr': result.stderr})
    passed = forwarding_result(*cases)
    report = {'passed': passed, 'scope': 'Synthetic MIPS core under QEMU-user with saved console glibc; not actual FrogUI or hardware acceptance',
              'hardware_verified': False, 'camera_used': False, 'rebuilt': False,
              'artifact_sha256': artifact_hashes, 'runtime_sha256': runtime_hashes,
              'runtime_and_artifacts_hash_matched_in_VM': True,
              'binary_build_provenance_verified': False,
              'vm_directory': directory, 'cases': cases}
    (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print('CORE_TRACE_FORWARDING=' + ('PASS' if passed else 'FAIL'))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
