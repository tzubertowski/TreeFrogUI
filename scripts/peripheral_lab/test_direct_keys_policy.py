"""Verify measured r36-direct-keys policy, power hold timing, and GPIO19 amp / GPIO15 HP rules."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ZIG = Path(r"C:\Users\palpa\Tools\zig-x86_64-windows-0.17.0\zig.exe")


def test_direct_key_codes_match_physical_measurement():
    measured = json.loads((ROOT / "analysis/driver_port/INPUT_PHYSICAL_v3_RESULT.json").read_text())
    by_physical = {
        entry["physical"]: entry["code"]
        for entry in measured["mapping"]
        if entry["device"] == "r36-direct-keys"
    }
    header = (ROOT / "scripts/peripheral_lab/direct_keys_policy.h").read_text()

    expected = {
        "R36_DIRECT_CODE_L2": by_physical["L2"],
        "R36_DIRECT_CODE_R2": by_physical["R2"],
        "R36_DIRECT_CODE_FN": by_physical["FN"],
        "R36_DIRECT_CODE_VOL_UP": by_physical["VOLUME_UP"],
        "R36_DIRECT_CODE_VOL_DOWN": by_physical["VOLUME_DOWN"],
        "R36_DIRECT_CODE_POWER": by_physical["POWER"],
    }
    for macro, code in expected.items():
        m = re.search(rf"#define\s+{macro}\s+(\d+)u", header)
        assert m is not None, f"missing {macro}"
        assert int(m.group(1)) == code, f"{macro}: expected {code}, got {m.group(1)}"


def test_direct_keys_volume_brightness_power_and_speaker_pa(tmp_path):
    header = ROOT / "scripts/peripheral_lab/direct_keys_policy.h"
    harness = tmp_path / "direct_keys_policy_test.c"
    harness.write_text(
        f'''
#include <assert.h>
#include <stdio.h>
#include "{header.as_posix()}"

int main(void) {{
    struct r36_direct_keys_policy pol;
    r36_direct_keys_policy_init(&pol, 50, 50);
    assert(pol.volume_pct == 50 && pol.brightness_pct == 50);

    /* Volume +/- without FN, including clamping 0..100 */
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_VOL_UP, 1, 100) == R36_DIRECT_ACTION_VOLUME_CHANGED);
    assert(pol.volume_pct == 55);
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_VOL_UP, 2, 120) == R36_DIRECT_ACTION_VOLUME_CHANGED);
    assert(pol.volume_pct == 60);
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_VOL_UP, 0, 140) == R36_DIRECT_ACTION_NONE);
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_VOL_DOWN, 1, 150) == R36_DIRECT_ACTION_VOLUME_CHANGED);
    assert(pol.volume_pct == 55);
    for (int i = 0; i < 20; i++)
        r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_VOL_DOWN, 1, 200 + (uint64_t)i);
    assert(pol.volume_pct == 0);
    for (int i = 0; i < 30; i++)
        r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_VOL_UP, 1, 300 + (uint64_t)i);
    assert(pol.volume_pct == 100);

    /* FN + VOL+/VOL- controls brightness clamped 5..100 without changing volume */
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_FN, 1, 400) == R36_DIRECT_ACTION_NONE);
    assert(pol.fn_held == 1);
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_VOL_DOWN, 1, 410) == R36_DIRECT_ACTION_BRIGHTNESS_CHANGED);
    assert(pol.brightness_pct == 40 && pol.volume_pct == 100);
    for (int i = 0; i < 10; i++)
        r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_VOL_DOWN, 1, 420 + (uint64_t)i);
    assert(pol.brightness_pct == 5);
    for (int i = 0; i < 15; i++)
        r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_VOL_UP, 1, 450 + (uint64_t)i);
    assert(pol.brightness_pct == 100);
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_FN, 0, 500) == R36_DIRECT_ACTION_NONE);
    assert(pol.fn_held == 0);

    /* L2 / R2 held tracking */
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_L2, 1, 510) == R36_DIRECT_ACTION_NONE);
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_R2, 1, 520) == R36_DIRECT_ACTION_NONE);
    assert(pol.l2_held == 1 && pol.r2_held == 1);
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_L2, 0, 530) == R36_DIRECT_ACTION_NONE);
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_R2, 0, 540) == R36_DIRECT_ACTION_NONE);
    assert(pol.l2_held == 0 && pol.r2_held == 0);

    /* POWER short press (< 1500 ms) -> sleep toggle */
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_POWER, 1, 1000) == R36_DIRECT_ACTION_NONE);
    assert(r36_direct_keys_tick(&pol, 2499) == R36_DIRECT_ACTION_NONE);
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_POWER, 0, 2499) == R36_DIRECT_ACTION_SLEEP_TOGGLE);

    /* POWER long hold (>= 1500 ms) with repeat events: tick emits POWEROFF once, release returns NONE */
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_POWER, 1, 3000) == R36_DIRECT_ACTION_NONE);
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_POWER, 2, 3600) == R36_DIRECT_ACTION_NONE);
    assert(pol.power_press_ms == 3000);
    assert(r36_direct_keys_tick(&pol, 4499) == R36_DIRECT_ACTION_NONE);
    assert(r36_direct_keys_tick(&pol, 4500) == R36_DIRECT_ACTION_POWEROFF);
    assert(r36_direct_keys_tick(&pol, 4700) == R36_DIRECT_ACTION_NONE);
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_POWER, 0, 4800) == R36_DIRECT_ACTION_NONE);

    /* POWER release at >= 1500 ms without prior tick still emits POWEROFF */
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_POWER, 1, 5000) == R36_DIRECT_ACTION_NONE);
    assert(r36_direct_keys_handle_event(&pol, R36_DIRECT_CODE_POWER, 0, 6500) == R36_DIRECT_ACTION_POWEROFF);

    /* GPIO19 speaker PA / GPIO15 HP-det truth table */
    assert(r36_speaker_amp_should_enable(1, 1, 0, 50, 0) == 1); /* active-low HP unplugged */
    assert(r36_speaker_amp_should_enable(0, 1, 0, 50, 0) == 0); /* active-low HP plugged */
    assert(r36_speaker_amp_should_enable(1, 0, 0, 50, 0) == 0); /* active-high HP plugged */
    assert(r36_speaker_amp_should_enable(0, 0, 0, 50, 0) == 1); /* active-high HP unplugged */
    assert(r36_speaker_amp_should_enable(1, 1, 1, 50, 0) == 0); /* muted */
    assert(r36_speaker_amp_should_enable(1, 1, 0, 0, 0)  == 0); /* zero volume */
    assert(r36_speaker_amp_should_enable(1, 1, 0, 50, 1) == 0); /* sleeping */

    puts("DIRECT_KEYS_POLICY=PASS");
    return 0;
}}
'''
    )

    exe = tmp_path / "direct_keys_policy_test.exe"
    subprocess.run(
        ["gcc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", str(harness), "-o", str(exe)],
        check=True,
        capture_output=True,
        timeout=20,
    )
    res = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=5)
    assert "DIRECT_KEYS_POLICY=PASS" in res.stdout

    if ZIG.exists():
        mips_probe = tmp_path / "direct_keys_policy_mips.c"
        mips_probe.write_text(
            f'#include "{header.as_posix()}"\n'
            'int probe_keys(struct r36_direct_keys_policy *p) {\n'
            '    r36_direct_keys_policy_init(p, 50, 50);\n'
            '    return (int)r36_direct_keys_handle_event(p, R36_DIRECT_CODE_VOL_UP, 1, 10) +\n'
            '           r36_speaker_amp_should_enable(1, 1, 0, p->volume_pct, 0);\n'
            '}\n'
        )
        mips_obj = tmp_path / "direct_keys_policy_mips.o"
        subprocess.run(
            [
                str(ZIG),
                "cc",
                "-target",
                "mipsel-linux.4.4-musleabi",
                "-march=mips32r2",
                "-msoft-float",
                "-Os",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-c",
                str(mips_probe),
                "-o",
                str(mips_obj),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        assert mips_obj.stat().st_size > 0
