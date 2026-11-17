import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "boot_crypto"))
from peripheral_result import display_result

RELEASE = "7.2.0-rc5-r36disp"
HEADER = f"run_id=fresh\nR36 DISPLAY PROBE V1\nkernel={RELEASE} #7 test\n".encode()
FOOTER = b"probe_rc=0 errno=0\nR36 DISPLAY PROBE END\n"
PASSIVE = HEADER + b"display_inspection=PASS\n" + FOOTER
KMS = HEADER + (b"display_module_load_rc=0 errno=0\nmodeset_requested=1\n"
                b"pixel_hash_cpu=8d21d5c5 pixel_hash_dma=8d21d5c5 irq_before=4 irq_after=8 raster_progress=1\n"
                b"display_scanout=PASS\nphysical_panel_visual_confirmation=NOT_TESTED\n") + FOOTER


def test_passive_and_kms_are_distinct():
    assert display_result(PASSIVE, "fresh", RELEASE)["passive_verified"]
    assert not display_result(PASSIVE, "fresh", RELEASE, kms=True)["scanout_verified"]
    result = display_result(KMS, "fresh", RELEASE, kms=True)
    assert result["scanout_verified"] and not result["physical_panel_visual_verified"]
    assert not display_result(KMS, "fresh", RELEASE)["scanout_verified"]


@pytest.mark.parametrize("raw", [
    KMS.replace(b"run_id=fresh", b"run_id=stale"), KMS + b"trailing data\n",
    KMS.replace(b"R36 DISPLAY PROBE END\n", b""),
    KMS.replace(b"probe_rc=0 errno=0", b"probe_rc=-1 errno=5"),
    KMS.replace(b"pixel_hash_dma=8d21d5c5", b"pixel_hash_dma=00000000"),
    KMS.replace(b"irq_after=8", b"irq_after=4"),
    KMS.replace(b"raster_progress=1", b"raster_progress=0"),
    KMS.replace(b"display_scanout=PASS", b"display_scanout=PASS\ndisplay_inspection=PASS"),
    KMS.replace(b"modeset_requested=1", b"activation_refused=1"),
    KMS.replace(b"kernel=7.2.0-rc5-r36disp", b"kernel=7.2.0-rc5-r36port"),
    KMS.replace(b"run_id=fresh\n", b"run_id=fresh\nrun_id=fresh\n"),
    KMS.replace(b"display_module_load_rc=0 errno=0", b"display_module_load_rc=-1 errno=5"),
    KMS.replace(b"physical_panel_visual_confirmation=NOT_TESTED\n", b""),
])
def test_stale_incomplete_or_contradictory_kms_never_passes(raw):
    assert not display_result(raw, "fresh", RELEASE, kms=True)["scanout_verified"]


def test_hardware_modeset_without_final_evidence_does_not_pass():
    raw = HEADER + (b"display_module_load_rc=0 errno=0\n"
                    b"kms_ioctl=setcrtc rc=0 errno=0\n"
                    b"kms_ioctl=wait_vblank rc=0 errno=0\n"
                    b"probe_rc=-1 errno=0\nR36 DISPLAY PROBE END\n")
    result = display_result(raw, "fresh", RELEASE, kms=True)
    assert result["fresh"] and not result["scanout_verified"]
    assert not result["physical_panel_visual_verified"]
