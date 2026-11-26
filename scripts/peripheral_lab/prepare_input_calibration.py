"""Add only polled volume/power inputs to a NEW diagnostic DTB/profile.

Reuse existing kernel code and input drivers. No power-action policy or output
GPIO nodes. A physical long power hold may still cut power independently.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/kernel_lab'))
from preflight import properties
from patch_diagnostic_init import patch

ADDITIONS = {'volume-down': (12, 114), 'volume-up': (13, 115), 'power-button': (14, 116)}


def validate(before, after):
    base = '/r36-direct-keys'
    reference = before[base + '/function-key']['gpios']
    phandle, _, flags = struct.unpack('>III', reference)
    if flags != 1:
        raise ValueError('requires measured active-low GPIO profile')
    expected = dict(before)
    for name, (pin, code) in ADDITIONS.items():
        node = base + '/' + name
        if node in before:
            raise ValueError('input node already exists')
        expected[node] = {'linux,code': struct.pack('>I', code),
                          'gpios': struct.pack('>III', phandle, pin, flags)}
    if expected != after:
        raise ValueError('DTB changed outside three explicit polled inputs')
    return phandle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--init', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    patch(args.source, args.init, args.out)
    dtb = args.out / 'r36-lab.dtb'
    before = properties(dtb.read_bytes())
    phandle, _, flags = struct.unpack('>III', before['/r36-direct-keys/function-key']['gpios'])
    def invoke(*arguments):
        path = '/mnt/' + dtb.resolve().as_posix()[0].lower() + dtb.resolve().as_posix()[2:]
        options = 2 if arguments[0] == '-t' else 1
        subprocess.run(['wsl', '-d', 'ubmips', '--', 'fdtput', *arguments[:options], path, *arguments[options:]], check=True, timeout=10)
    for name, (pin, code) in ADDITIONS.items():
        node = '/r36-direct-keys/' + name
        invoke('-c', node)
        invoke('-t', 'i', node, 'linux,code', str(code))
        invoke('-t', 'i', node, 'gpios', str(phandle), str(pin), str(flags))
    validate(before, properties(dtb.read_bytes()))
    manifest = json.loads((args.out / 'manifest.json').read_text())
    manifest['sha256']['r36-lab.dtb'] = hashlib.sha256(dtb.read_bytes()).hexdigest()
    manifest.update(profile='display-kms-probe', input_calibration_capture_seconds=60,
                    input_only_volume_power=True, power_action_handler=False)
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    record = {'passed': True, 'kernel_code_changed': False, 'added_polled_GPIO_inputs': ADDITIONS,
              'no_output_GPIO_added': True, 'no_power_or_volume_actions': True,
              'hardware_verified': False, 'camera_used': False}
    (args.out / 'input_profile_receipt.json').write_text(json.dumps(record, indent=2) + '\n')
    print('INPUT_CALIBRATION_PROFILE=PASS')


if __name__ == '__main__':
    main()
