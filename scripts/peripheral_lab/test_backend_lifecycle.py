from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_dummy_sound_or_ge_exports_and_retains_failed_dma_cleanup():
    text = (ROOT / "scripts/peripheral_lab/video_drm_backend.c").read_text()
    assert "int video_drivers_init(void)" in text
    assert "int video_driver_disp_frame(void *source, int width, int height, int pitch_bytes)" in text
    assert "void video_driver_deinit(void)" in text
    assert "sound_driver_init(" not in text and "sound_driver_playframe(" not in text
    assert "void *g_render" not in text
    assert "restore failed; retaining scanout buffer until reset" in text
    assert "disable failed; retaining scanout buffer until reset" in text
    assert "#define _FILE_OFFSET_BITS 64" in text


def test_renders_offscreen_and_waits_for_synchronous_page_flip():
    text = (ROOT / "scripts/peripheral_lab/video_drm_backend.c").read_text()
    # Two dumb buffers: the scaler target is never the scanned-out buffer.
    assert "static void *buffers[2]" in text
    assert "static void *pixels;" in text and "static void *render_pixels;" in text
    assert "r36_scale565(render_pixels" in text
    assert "swap_buffers();" in text
    # Synchronous flip: PAGE_FLIP with event, bounded wait, token match.
    assert "DRM_IOCTL_MODE_PAGE_FLIP" in text
    assert "DRM_MODE_PAGE_FLIP_EVENT" in text
    assert "DRM_EVENT_FLIP_COMPLETE" in text
    assert "event.user_data == token" in text
    assert "R36_FLIP_TIMEOUT_MS" in text
    # Unknown scanout state after a failed flip is recovered by modeset
    # before the next render, never by writing a possibly active buffer.
    assert "needs_modeset" in text
    assert text.index("if (needs_modeset && r36_modeset())") < text.index(
        "r36_scale565(render_pixels")
    # First frame and resynchronisation keep the proven SETCRTC path.
    assert "DRM_IOCTL_MODE_SETCRTC" in text and "DRM_IOCTL_WAIT_VBLANK" in text


def test_mock_model_rejects_writes_to_the_active_scanout_buffer():
    text = (ROOT / "scripts/peripheral_lab/video_backend_test.c").read_text()
    assert "CPU rewrote the active scanout buffer" in text
    assert "DRM_IOCTL_MODE_PAGE_FLIP" in text
    assert "fail_flip_wait" in text and "fail_flip_ioctl" in text
    assert "r36_test_backend_frames" in text


def test_publisher_does_not_steal_existing_shm_or_report_disconnect_as_success():
    text = (ROOT / "scripts/peripheral_lab/legacy_keys.c").read_text()
    assert "IPC_CREAT | IPC_EXCL | 0600" in text
    assert "LOCK_EX | LOCK_NB" in text
    assert "result = requested_stop ? 0 : 1;" in text
    assert "SYN_DROPPED" in text
    assert "*shared = stopped ? 0 : r36_key_word(&state);" in text
