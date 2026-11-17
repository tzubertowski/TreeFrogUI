import json
import os
from pathlib import Path
import shutil
import sys

import pytest
from elftools.elf.elffile import ELFFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preflight import validate


@pytest.fixture
def real_candidate():
    path = os.environ.get("R36_TEST_CANDIDATE")
    if not path: pytest.skip("prepare_bundle supplies a fully built candidate")
    return Path(path)


def test_real_candidate_passes(real_candidate):
    assert validate(real_candidate)["passed"]


def test_modified_upload_artifact_rejected(real_candidate, tmp_path):
    candidate = tmp_path / "changed"
    shutil.copytree(real_candidate, candidate)
    path = candidate / "r36-lab.dtb"
    raw = bytearray(path.read_bytes()); raw[-1] ^= 1; path.write_bytes(raw)
    with pytest.raises(ValueError, match="hash mismatch"):
        validate(candidate)


def test_binary_binding_rejected_even_if_file_digest_updated(real_candidate, tmp_path):
    import hashlib
    candidate = tmp_path / "changed"
    shutil.copytree(real_candidate, candidate)
    path = candidate / "r36boot.ko"
    with path.open("rb") as handle:
        offset = ELFFile(handle).get_section_by_name(".r36.binding")["sh_offset"]
    raw = bytearray(path.read_bytes()); raw[offset + 12] ^= 4; path.write_bytes(raw)
    manifest = json.loads((candidate / "manifest.json").read_text())
    manifest["loader_sha256"]["r36boot.ko"] = hashlib.sha256(raw).hexdigest()
    (candidate / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="bound to another"):
        validate(candidate)


def test_old_emulation_report_rejected(real_candidate, tmp_path):
    candidate = tmp_path / "changed"
    shutil.copytree(real_candidate, candidate)
    path = candidate / "emulation.json"
    report = json.loads(path.read_text()); report["loader_sha256"] = "0" * 64
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="emulation"):
        validate(candidate)
