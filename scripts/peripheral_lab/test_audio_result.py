import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "boot_crypto"))
from peripheral_result import audio_result

RELEASE = "7.2.0-rc5-r36disp"
REPORT = (b"run_id=fresh\nkernel=7.2.0-rc5-r36disp #15\nR36 DISPLAY PROBE V1\n"
          b"R36 AUDIO SILENT PROBE V1\naudio_module_load_rc=0 errno=0\n"
          b"audio_frames=24576 dma_moved=1 irq_before=2 irq_after=30 drop_rc=0 stopped=1\n"
          b"audio_silent_dma=PASS\naudible_output=NOT_TESTED\n"
          b"audio_probe_rc=0 errno=0\nR36 AUDIO SILENT PROBE END\n"
          b"probe_rc=0 errno=0\nR36 DISPLAY PROBE END\n")


def test_silent_dma_never_claims_audible_output():
    result = audio_result(REPORT, "fresh", RELEASE)
    assert result["silent_dma_verified"]
    assert not result["audible_output_verified"] and not result["speaker_or_headphone_verified"]


@pytest.mark.parametrize("raw", [
    REPORT.replace(b"run_id=fresh", b"run_id=stale"),
    REPORT.replace(b"irq_after=30", b"irq_after=2"),
    REPORT.replace(b"dma_moved=1", b"dma_moved=0"),
    REPORT.replace(b"stopped=1", b"stopped=0"),
    REPORT.replace(b"drop_rc=0", b"drop_rc=-1"),
    REPORT.replace(b"audio_probe_rc=0", b"audio_probe_rc=-1"),
    REPORT.replace(b"R36 AUDIO SILENT PROBE END\n", b""),
    REPORT + b"partial next run\n",
    REPORT.replace(b"audio_module_load_rc=0 errno=0", b"audio_module_load_rc=-1 errno=16"),
])
def test_incomplete_faulted_or_stale_audio_fails(raw):
    assert not audio_result(raw, "fresh", RELEASE)["silent_dma_verified"]
