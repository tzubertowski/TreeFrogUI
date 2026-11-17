"""Run an explicit four-core synthetic smoke suite in the owned MIPS QEMU VM.

Only uploads known test artifacts; never contacts the console or reads real ROMs.
Each core has its own new directory and a bounded process deadline. Results are
recorded as actual output, not inferred from ELF symbols or a successful build.
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
CORES = {'gambatte': 'gb', 'gearboy': 'gb', 'fceumm': 'nes', 'quicknes': 'nes'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--harness', type=Path, default=ROOT / 'analysis/driver_port/libretro-smoke-mips-v3')
    parser.add_argument('--mock-drm-backend', type=Path, help='test-only real backend code with synthetic ioctl device')
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir(): parser.error('output must be new with existing parent')
    args.out.mkdir()
    options = ['-i', str(WORK / 'id_ed25519'), '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
               '-o', 'UserKnownHostsFile=' + str(WORK / 'known_hosts')]
    ssh = ['ssh', '-p', '22222', *options, 'root@127.0.0.1']
    scp = ['scp', '-P', '22222', *options]
    root = '/work/emulator-smoke-' + str(time.time_ns())
    subprocess.run(ssh + ['mkdir ' + shlex.quote(root)], check=True, timeout=10)
    harness = args.harness
    subprocess.run(scp + [str(harness), 'root@127.0.0.1:' + root + '/harness'], check=True, timeout=20)
    if args.mock_drm_backend:
        subprocess.run(scp + [str(args.mock_drm_backend), 'root@127.0.0.1:' + root + '/backend.so'], check=True, timeout=20)
    records = []
    for core, extension in CORES.items():
        source = ROOT / 'treefrog/extracted/release/cubegm/cores' / (core + '_libretro.so')
        rom = ROOT / 'analysis/driver_port/synthetic_roms_v1' / ('input_test.' + extension)
        directory = root + '/' + core
        subprocess.run(ssh + ['mkdir ' + shlex.quote(directory)], check=True, timeout=10)
        subprocess.run(scp + [str(source), str(rom), 'root@127.0.0.1:' + directory + '/'], check=True, timeout=20)
        command = ('cd ' + shlex.quote(directory) + '; chmod +x ' + shlex.quote(root + '/harness') +
                   '; exec ' + ('env R36_TEST_VIDEO_BACKEND=' + shlex.quote(root + '/backend.so') + ' ' if args.mock_drm_backend else '') +
                   'timeout 45 qemu-mipsel -cpu 74Kf /work/mips_emulator_libs_v1/ld.so.1 '
                   '--library-path /work/mips_emulator_libs_v1 ' + shlex.quote(root + '/harness') + ' ' +
                   shlex.quote(directory + '/' + source.name) + ' ' + shlex.quote(directory + '/' + rom.name))
        for mode in ('press_release', 'neutral'):
            actual = command + (' --neutral' if mode == 'neutral' else '')
            p = subprocess.run(ssh + [actual], capture_output=True, text=True, timeout=55)
            passed = (p.returncode == 0 and 'LIBRETRO_SYNTHETIC_EXECUTION=PASS' in p.stdout and
                      'savestate_roundtrip=PASS' in p.stdout and
                      (not args.mock_drm_backend or 'actual_backend_frames=' in p.stdout))
            record = {'core': core, 'input_mode': mode, 'passed': passed, 'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr,
                      'core_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                      'synthetic_rom_sha256': hashlib.sha256(rom.read_bytes()).hexdigest()}
            records.append(record)
            (args.out / (core + '_' + mode + '.json')).write_text(json.dumps(record, indent=2) + '\n')
            print(core, mode, 'PASS' if passed else 'FAIL', flush=True)
    report = {'passed': all(r['passed'] for r in records), 'cases': records,
              'harness_sha256': hashlib.sha256(harness.read_bytes()).hexdigest(),
              'scope': 'real unchanged MIPS cores, synthetic GB/NES CPU/input/video/audio under QEMU-user; no physical console',
              'hardware_verified': False, 'real_games_verified': False,
              'actual_video_backend_with_mock_DRM': bool(args.mock_drm_backend),
              'mock_backend_sha256': hashlib.sha256(args.mock_drm_backend.read_bytes()).hexdigest() if args.mock_drm_backend else None,
              'legacy_input_translation_exercised': True, 'runtime': 'isolated Debian MIPS glibc/libstdc++ libraries, not verified console libraries'}
    (args.out / 'suite.json').write_text(json.dumps(report, indent=2) + '\n')
    if not report['passed']: raise SystemExit(1)


if __name__ == '__main__':
    main()
