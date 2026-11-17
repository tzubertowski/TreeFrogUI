import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_display_result import HEADER, FOOTER, KMS, RELEASE
from peripheral_result import input_result


def test_inventory_is_not_physical_mapping():
    raw = KMS.replace(FOOTER, b"R36 INPUT INVENTORY V1\n"
        b"input_device=r36-serial-keys path=/dev/input/event0\n"
        b"input_device=r36-direct-keys path=/dev/input/event1\n"
        b"input_inventory=PASS\nphysical_key_mapping=NOT_VERIFIED\n"
        b"R36 INPUT INVENTORY END\ninput_probe_rc=0\n" + FOOTER)
    result = input_result(raw, "fresh", RELEASE)
    assert result["inventory_verified"]
    assert not result["physical_mapping_verified"] and not result["legacy_ui_navigation_verified"]
    assert not input_result(raw, "stale", RELEASE)["inventory_verified"]
    assert not input_result(raw.replace(b"input_probe_rc=0", b"input_probe_rc=-1"), "fresh", RELEASE)["inventory_verified"]
    assert not input_result(raw.replace(b"input_device=r36-direct-keys", b"input_device=unknown"), "fresh", RELEASE)["inventory_verified"]
