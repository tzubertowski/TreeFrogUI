"""Verify 12-button gameplay map validation and C bridge -> SysV -> libretro translation."""
from pathlib import Path
import copy
import json
import subprocess

import pytest
from prepare_ui_gameplay_input import (
    EXTRA_DIRECT_BUTTONS,
    GAMEPLAY_BITS,
    LIBRETRO_JOYPAD_ORDER,
    gameplay_map,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
ZIG = Path(r"C:\Users\palpa\Tools\zig-x86_64-windows-0.17.0\zig.exe")


def synthetic_records():
    names = list(GAMEPLAY_BITS.keys())
    phys_rows = [
        {'physical': name, 'code': 704 + i, 'device': 'r36-serial-keys'}
        for i, name in enumerate(names)
    ] + [
        {'physical': extra, 'code': 100 + i, 'device': 'r36-direct-keys'}
        for i, extra in enumerate(sorted(EXTRA_DIRECT_BUTTONS))
    ]
    physical = {
        'physical_labels_verified': True,
        'human_order_confirmed': True,
        'capture_sha256': 'hash12',
        'run_id': 'fresh12',
        'mapping': phys_rows,
    }
    calibration = {
        'capture_sha256': 'hash12',
        'run_id': 'fresh12',
        'mapping': [
            {'name': name, 'code': 704 + i, 'bit': GAMEPLAY_BITS[name], 'device': 'r36-serial-keys'}
            for i, name in enumerate(names)
        ],
    }
    return physical, calibration


def test_gameplay_map_validates_synthetic_and_actual_measured_capture():
    p, c = synthetic_records()
    text = gameplay_map(p, c)
    assert len(text.splitlines()) == 12

    phys_path = ROOT / 'analysis/driver_port/INPUT_PHYSICAL_v3_RESULT.json'
    cal_path = ROOT / 'analysis/driver_port/physical_legacy_map_v3/calibration.json'
    map_path = ROOT / 'analysis/driver_port/physical_legacy_map_v3/evdev-to-legacy.map'
    if phys_path.exists() and cal_path.exists() and map_path.exists():
        actual = gameplay_map(json.loads(phys_path.read_text()), json.loads(cal_path.read_text()))
        assert actual == map_path.read_text()


@pytest.mark.parametrize(
    'case',
    ['stale', 'unconfirmed', 'wrong_bit', 'wrong_code', 'duplicate', 'extra_collision', 'short_list'],
)
def test_gameplay_map_rejects_invalid_records(case):
    p, c = synthetic_records()
    if case == 'stale':
        c['run_id'] = 'old'
    elif case == 'unconfirmed':
        p['human_order_confirmed'] = False
    elif case == 'wrong_bit':
        c['mapping'][0]['bit'] = 2
    elif case == 'wrong_code':
        c['mapping'][0]['code'] = 750
    elif case == 'duplicate':
        c['mapping'][1]['code'] = c['mapping'][0]['code']
    elif case == 'extra_collision':
        p['mapping'][0]['code'] = 100
        c['mapping'][0]['code'] = 100
    elif case == 'short_list':
        c['mapping'] = c['mapping'][:4]
    with pytest.raises(ValueError):
        gameplay_map(p, c)


def test_c_bridge_and_libretro_translation_on_measured_12_buttons(tmp_path):
    phys = json.loads((ROOT / 'analysis/driver_port/INPUT_PHYSICAL_v3_RESULT.json').read_text())
    cal = json.loads((ROOT / 'analysis/driver_port/physical_legacy_map_v3/calibration.json').read_text())
    map_text = gameplay_map(phys, cal)
    map_file = tmp_path / 'gameplay12.map'
    map_file.write_text(map_text)

    bad_file = tmp_path / 'dup.map'
    bad_file.write_text('704 10\n704 11\n')

    by_name = {row['name']: (int(row['code']), int(row['bit'])) for row in cal['mapping']}
    checks = []
    for retro_idx, name in enumerate(LIBRETRO_JOYPAD_ORDER):
        code, bit = by_name[name]
        checks.append(f'''
        assert(r36_key_event(&state, 0, {code}u, 1) == 0);
        assert(r36_key_word(&state) == (UINT32_C(1) << {bit}));
        assert(r36_legacy_to_libretro(r36_key_word(&state)) == (uint16_t)(1u << {retro_idx}));
        assert(r36_key_event(&state, 0, {code}u, 0) == 0);
        assert(r36_key_word(&state) == 0u);
        ''')

    # Extract load_mapping from legacy_keys.c and test full 12-button mode (without R36_KEYS_NAVIGATION_ONLY)
    legacy_c = (HERE / 'legacy_keys.c').read_text()
    start = legacy_c.index('static int load_mapping(const char *path)')
    end = legacy_c.index('int main(int argc, char **argv)')
    load_mapping_fn = legacy_c[start:end]

    harness = tmp_path / 'gameplay_harness.c'
    harness.write_text(f'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "{(HERE / 'legacy_keys.h').as_posix()}"
#include "{(HERE / 'legacy_joypad.h').as_posix()}"

static struct r36_key_bridge state;
{load_mapping_fn}

int main(void) {{
    /* Duplicate evdev code must be rejected */
    memset(&state, 0, sizeof(state));
    assert(load_mapping("{bad_file.as_posix()}") == -1);
    memset(&state, 0, sizeof(state));
    assert(load_mapping("{map_file.as_posix()}") == 0);
    {''.join(checks)}
    /* Multi-button chord: UP + RIGHT + A + B */
    assert(r36_key_event(&state, 0, {by_name["UP"][0]}u, 1) == 0);
    assert(r36_key_event(&state, 0, {by_name["RIGHT"][0]}u, 1) == 0);
    assert(r36_key_event(&state, 0, {by_name["A"][0]}u, 1) == 0);
    assert(r36_key_event(&state, 0, {by_name["B"][0]}u, 1) == 0);
    assert(r36_legacy_to_libretro(r36_key_word(&state)) == ((1u << 0) | (1u << 4) | (1u << 7) | (1u << 8)));
    return 0;
}}
''')
    exe = tmp_path / 'gameplay_harness.exe'
    subprocess.run(['gcc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', str(harness), '-o', str(exe)],
                   check=True, capture_output=True, timeout=20)
    subprocess.run([str(exe)], check=True, timeout=5)

    if ZIG.exists():
        # Verify full 12-button MIPS32r2 static publisher binary builds cleanly from legacy_keys.c
        mips_pub = tmp_path / 'r36-gameplay-keys-mips.elf'
        subprocess.run([
            str(ZIG), 'cc', '-target', 'mipsel-linux.4.4-musleabi',
            '-march=mips32r2', '-msoft-float', '-static', '-Os',
            '-Wall', '-Wextra', '-Werror', '-DR36_KEYS_DIAGNOSTIC',
            str(HERE / 'legacy_keys.c'), '-o', str(mips_pub),
        ], check=True, capture_output=True, timeout=30)
        assert mips_pub.stat().st_size > 0
