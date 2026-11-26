"""Pin-safety and build isolation for the new polled input diagnostic."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def test_only_known_input_pins_claimed():
    text = (ROOT / "scripts/kernel_lab/r36-display-input.dts").read_text()
    pins = set(map(int, re.findall(r"<&gpio\s+(\d+)\s", text)))
    assert pins == {2, 7, 8, 9, 11}
    assert "KEY_POWER" not in text and "KEY_VOLUME" not in text
    assert "gpio-keys-polled" in text and "GPIO_OPEN_DRAIN" in text
    assert "status = \"okay\"" not in text  # no extra display/USB/audio takeover


def test_input_build_opt_in_not_existing_profile_change():
    script = (ROOT / "scripts/peripheral_lab/vm_build_kernel.sh").read_text()
    assert '${R36_INPUT_PROBE:-0}' in script
    assert "--enable KEYBOARD_GPIO_POLLED --enable KEYBOARD_GPIO_SERIALIZER" in script
    assert 'r36-display-input.dts' in script
    probe = (ROOT / "scripts/peripheral_lab/input_probe.h").read_text()
    assert 'physical_key_mapping=NOT_VERIFIED' in probe
    assert '12000' in probe and 'total++ >= 1024' in probe
