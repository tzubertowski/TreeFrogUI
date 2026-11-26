"""Verify /cubegm launcher scripts, /tmp/tfdevice.env, PICOARCH_DRIVER, and cores audit."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/peripheral_lab"))
from audit_cubegm_runtime import DEFAULT_BACKUP, audit_cubegm_runtime, parse_tfdevice_env


def test_parse_tfdevice_env_extracts_gb350_panel():
    sample = (
        "cat > /tmp/tfdevice.env <<EOF\n"
        "TF_DEVICE=GB350\n"
        "TF_PANEL_W=640\n"
        "TF_PANEL_H=480\n"
        "EOF\n"
    )
    parsed = parse_tfdevice_env(sample)
    assert parsed == {"TF_DEVICE": "GB350", "TF_PANEL_W": "640", "TF_PANEL_H": "480"}


def test_cubegm_runtime_audit_on_backup_when_present():
    if not DEFAULT_BACKUP.is_dir():
        pytest.skip("local /cubegm backup not present")
    report = audit_cubegm_runtime(DEFAULT_BACKUP)
    assert report["all_required_present"] is True
    assert report["supports_picoarch_driver_env"] is True
    assert report["tfdevice_env"].get("TF_DEVICE") == "GB350"
    assert report["tfdevice_env"].get("TF_PANEL_W") == "640"
    assert report["tfdevice_env"].get("TF_PANEL_H") == "480"
    assert report["core_count"] >= 10
    assert "frogui_libretro.so" in report["cores"]
