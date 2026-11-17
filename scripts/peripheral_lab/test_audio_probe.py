from pathlib import Path
import struct

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_silent_probe_has_no_tone_or_amp_writes():
    text = (ROOT / "scripts/peripheral_lab/audio_probe.h").read_text()
    assert "static short silence[512 * 2];" in text
    assert '"allow_takeover=1"' in text
    assert 'gain || !mute' in text
    assert "after <= before" in text
    assert "SNDRV_PCM_IOCTL_DROP" in text
    assert "audible_output=NOT_TESTED" in text
    assert "GPIO" not in text and "/dev/mem" not in text
    assert "SNDRV_PCM_FORMAT_S16_LE" in text
    assert "SNDRV_PCM_HW_PARAM_RATE, 48000" in text


def test_audio_source_refuses_running_dma_before_reset():
    text = (ROOT / "payload/audio_driver_source_v3/r36_hc16xx_i2s.c").read_text()
    probe = text[text.index("static int hc16xx_i2s_probe"):]
    assert probe.index("if (!allow_takeover)") < probe.index("devm_platform_ioremap_resource")
    assert probe.index("old audio DMA is active") < probe.index("hc16xx_i2s_hw_init(a);")
    assert "static DEVICE_ATTR_RO(health)" in text
    assert '.r36audio' in text
    assert "a->mute = true" in text


def test_probe_pcm_abi_present():
    from audio_validation import read_audio_abi
    words = read_audio_abi(ROOT / "analysis/driver_port/r36-display-audio-silent-probe-v2")
    assert words[:2] == (0x52334142, 1)
    assert words[2] > 128 and words[4] == 12
    assert len(words) == 12


def test_abi_mismatch_refused(monkeypatch):
    import audio_validation
    monkeypatch.setattr(audio_validation, "read_audio_abi", lambda p: (1, 2) if p == "user" else (1, 3))
    with pytest.raises(ValueError, match="UAPI differs"):
        audio_validation.validate_audio_abi("user", "kernel")
