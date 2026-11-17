"""Optional regression checks against a fetched real display build."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_display_build import ROOT, abi, validate_display


@pytest.fixture
def candidate():
    value = os.environ.get("R36_DISPLAY_CANDIDATE")
    if not value:
        pytest.skip("set R36_DISPLAY_CANDIDATE to a completed display build")
    return Path(value)


def check(path):
    return validate_display(path, Path(os.environ.get("R36_DISPLAY_PROBE", ROOT / "analysis/driver_port/r36-display-probe")),
                            Path(os.environ.get("R36_DISPLAY_SOURCE", ROOT / "payload/display_driver_source_v3")))


def update_digest(path, name):
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["sha256"][name] = hashlib.sha256((path / name).read_bytes()).hexdigest()
    (path / "manifest.json").write_text(json.dumps(manifest))


def test_real_build_passes(candidate):
    result = check(candidate)
    assert result["build_passed"] and not result["hardware_verified"]
    assert result["modules"]["r36_hc16xx_drm.ko"]["imports_verified"] > 100


def test_stale_empty_module_rejected_even_if_digest_matches(candidate, tmp_path):
    target = tmp_path / "broken"
    shutil.copytree(candidate, target)
    module = target / "r36_hc16xx_drm.ko"
    with module.open("rb") as handle:
        from elftools.elf.elffile import ELFFile
        section = ELFFile(handle).get_section_by_name(".r36abi")
        offset = section["sh_offset"]
    raw = bytearray(module.read_bytes())
    raw[offset:offset + 4] = bytes(4)
    module.write_bytes(raw)
    update_digest(target, module.name)
    with pytest.raises(ValueError, match="ABI header"):
        check(target)


def test_disabled_sysvipc_rejected_even_if_digest_matches(candidate, tmp_path):
    target = tmp_path / "broken"
    shutil.copytree(candidate, target)
    config = target / "kernel.config"
    config.write_text(config.read_text().replace("CONFIG_SYSVIPC=y", "# CONFIG_SYSVIPC is not set"))
    update_digest(target, config.name)
    with pytest.raises(ValueError, match="SYSVIPC"):
        check(target)


def test_wrong_probe_rejected(candidate, tmp_path):
    wrong = tmp_path / "wrong.elf"
    wrong.write_bytes(b"stale probe")
    with pytest.raises(ValueError, match="current display probe"):
        validate_display(candidate, wrong, ROOT / "payload/display_driver_source_v3")


def test_kms_variant_is_not_passive(candidate, tmp_path):
    # Derive the variant from this exact fixture, not an unrelated old build.
    from fetch_display_build import make_kms_variant
    target = tmp_path / "kms"
    make_kms_variant(candidate, target)
    with pytest.raises(ValueError, match="disabled"):
        check(target)
