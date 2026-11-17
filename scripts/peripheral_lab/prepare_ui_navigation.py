"""Bind measured four-direction map and verified runtime components to a NEW profile.

No executable reverse-engineering tables or third-party code are generated.
Candidate must already contain the newly built navigation PID1.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_BITS = {'UP': 4, 'RIGHT': 5, 'DOWN': 6, 'LEFT': 7}


def direction_map(physical, calibration):
    if not physical['physical_labels_verified'] or not physical['human_order_confirmed']:
        raise ValueError('human confirmed physical capture required')
    if physical['capture_sha256'] != calibration['capture_sha256'] or physical['run_id'] != calibration['run_id']:
        raise ValueError('capture identity mismatch')
    rows = []
    for name, bit in EXPECTED_BITS.items():
        raw = [row for row in physical['mapping'] if row['physical'] == name]
        legacy = [row for row in calibration['mapping'] if row['name'] == name]
        if len(raw) != 1 or len(legacy) != 1 or raw[0]['code'] != legacy[0]['code'] or legacy[0]['bit'] != bit:
            raise ValueError('unverified direction: ' + name)
        rows.append((raw[0]['code'], bit))
    if len({code for code, _ in rows}) != 4:
        raise ValueError('aliased directions')
    return ''.join(f'{code} {bit}\n' for code, bit in sorted(rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', type=Path)
    args = parser.parse_args()
    p = args.profile
    m = json.loads((p / 'manifest.json').read_text())
    if m.get('navigation_profile_prepared'):
        parser.error('profile already prepared')
    if not all(hashlib.sha256((p / n).read_bytes()).hexdigest() == h for n, h in m['sha256'].items()):
        raise ValueError('profile hash mismatch')
    physical = json.loads((ROOT / 'analysis/driver_port/INPUT_PHYSICAL_v3_RESULT.json').read_text())
    calibration = json.loads((ROOT / 'analysis/driver_port/physical_legacy_map_v3/calibration.json').read_text())
    text = direction_map(physical, calibration)
    previous = ROOT / 'payload/kernel_ui_live_scanout_v11'
    pm = json.loads((previous / 'manifest.json').read_text())
    components = {
        'driver_r36_drm_ui_test.so': previous / 'driver_r36_drm_ui_test.so',
        'r36-ui-core-trace.so': previous / 'r36-ui-core-trace.so',
        'r36-navigation-keys': ROOT / 'analysis/driver_port/r36-navigation-keys-v1',
    }
    for name in ('driver_r36_drm_ui_test.so', 'r36-ui-core-trace.so'):
        if hashlib.sha256(components[name].read_bytes()).hexdigest() != pm['sha256'][name]:
            raise ValueError('verified component mismatch: ' + name)
    if any((p / n).exists() for n in (*components, 'r36-navigation.map')):
        raise ValueError('destination component already exists')
    for name, source in components.items():
        shutil.copy2(source, p / name)
    (p / 'r36-navigation.map').write_text(text)
    m['sha256'].update({name: hashlib.sha256((p / name).read_bytes()).hexdigest()
                        for name in (*components, 'r36-navigation.map')})
    m.update(profile='unchanged-ui-directions-only', navigation_profile_prepared=True,
             navigation_directions_only=True, UI_window_seconds=60,
             extra_device_files=['r36_hc16xx_drm.ko', *components, 'r36-navigation.map'])
    (p / 'manifest.json').write_text(json.dumps(m, indent=2) + '\n')
    print('UI_DIRECTIONS_PROFILE=PASS')


if __name__ == '__main__':
    main()
