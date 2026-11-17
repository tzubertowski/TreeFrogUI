"""Static capability check: the DRM driver supports double buffering and a
synchronous page flip, so the black-square defect is a userspace backend gap
and not a missing driver feature. No hardware is contacted."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "payload/display_driver_source_v4/r36_hc16xx_drm.c"
KO = ROOT / "payload/kernel_display_input_kms_vm_v1/r36_hc16xx_drm.ko"


@pytest.mark.skipif(not SOURCE.exists(), reason="payload driver source not present")
def test_driver_registers_atomic_page_flip_and_commit():
    text = SOURCE.read_text(errors="replace")
    for token in (
        ".page_flip\t\t= drm_atomic_helper_page_flip",
        ".atomic_commit\t= drm_atomic_helper_commit",
        ".set_config\t\t= drm_atomic_helper_set_config",
        ".fb_create\t= drm_gem_fb_create_with_dirty",
        ".driver_features\t= DRIVER_MODESET | DRIVER_GEM | DRIVER_ATOMIC",
        "drm_vblank_init(drm, 1)",
        "drm_crtc_send_vblank_event",
    ):
        assert token in text, token


@pytest.mark.skipif(not SOURCE.exists(), reason="payload driver source not present")
def test_driver_has_flip_completion_and_vblank_sync_paths():
    text = SOURCE.read_text(errors="replace")
    # Flip completion: latched descriptor or a bounded 4-vblank timeout.
    assert "hc16xx_latched" in text
    assert "flip not latched after 4 frames" in text
    assert "++hc->event_age > 4" in text
    assert "flip_timeouts" in text
    # Ping-pong layer descriptor: two slots per layer.
    assert "next_desc ^= 1" in text


@pytest.mark.skipif(not KO.exists(), reason="deployed kernel module not present")
def test_deployed_module_contains_flip_support():
    blob = KO.read_bytes()
    for token in (
        b"drm_atomic_helper_page_flip",
        b"flip not latched after 4 frames",
        b"flip_timeouts",
        b"boot_descriptor",
    ):
        assert token in blob, token.decode()
