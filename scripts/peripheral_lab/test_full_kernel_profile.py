"""Verify unified PROFILE=full DTS and build orchestration without breaking isolated profiles."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_r36_full_dts_contains_all_subsystems():
    dts = (ROOT / "scripts/kernel_lab/r36-full.dts").read_text()
    for token in (
        '#include "r36-display-input.dts"',
        "KEY_VOLUMEUP",
        "KEY_VOLUMEDOWN",
        "KEY_POWER",
        "r36lab,hc16xx-restart",
        "r36lab,hc16xx-adc-ro",
        '&r36_audio { status = "okay"; };',
        '&usb0 { status = "okay"; dr_mode = "otg"; };',
        '&usb1 { status = "okay"; dr_mode = "host"; };',
    ):
        assert token in dts, token


def test_vm_build_kernel_and_starter_support_full_profile():
    build = (ROOT / "scripts/peripheral_lab/vm_build_kernel.sh").read_text()
    assert "avp|display|usb|full" in build
    assert 'if [ "$PROFILE" = full ]; then' in build
    assert "r36-full.dts" in build
    assert "--enable PWM --enable PWM_HC16XX" in build
    assert "--enable BACKLIGHT_CLASS_DEVICE --enable BACKLIGHT_PWM" in build

    starter = (ROOT / "scripts/peripheral_lab/start_vm_kernel_build.py").read_text()
    assert "--full" in starter
    assert '"full" if args.full' in starter
