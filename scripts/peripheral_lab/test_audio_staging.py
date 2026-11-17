from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]


def test_audio_staged_source_is_disabled_and_no_foreign_syscore():
    source = ROOT / "payload/audio_driver_source_v1"
    text = (source / "r36_hc16xx_i2s.c").read_text()
    receipt = json.loads((source / "port_source.json").read_text())
    assert "gb350_syscore_send" not in text and "gb350-syscore.h" not in text
    assert '"Speaker Mode"' not in text
    assert "if (!allow_takeover)" in text
    assert "a->mute = true;" in text
    assert "#define GAIN_DEFAULT\t\t0" in text
    assert ".shutdown = r36_audio_quiesce" in text
    assert 'status = "disabled";' in (source / "r36-audio.dts").read_text()
    assert not receipt["hardware_verified"] and not receipt["deployed"]
    assert receipt["explicit_takeover_required"] and not receipt["foreign_firmware_required"]
