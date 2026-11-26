from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_hidden_pcm_selected_by_explicit_dependency_option():
    script = (ROOT / "scripts/peripheral_lab/vm_build_kernel.sh").read_text()
    assert 'config SND_R36_EXTERNAL_DEPS' in script
    assert 'select SND_PCM' in script
    assert '--enable SND_R36_EXTERNAL_DEPS' in script
    assert "grep -qxF 'CONFIG_SND_PCM=y'" in script
    assert script.index("grep -qxF 'CONFIG_SND_PCM=y'") < script.index('make -C "$SRC" -j1')
    assert 'status = "disabled";' in (ROOT / "payload/audio_driver_source_v1/r36-audio.dts").read_text()


def test_guest_clock_corrected_before_archive_extract():
    script = (ROOT / "scripts/peripheral_lab/start_vm_kernel_build.py").read_text()
    assert script.index("date -u -s '@") < script.index('mkdir -p /work/project; tar -xzf')
