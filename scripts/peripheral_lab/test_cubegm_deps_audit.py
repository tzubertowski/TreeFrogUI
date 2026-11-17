"""Verify /cubegm ELF dependency audit report and helper on synthetic + backed-up binaries."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/peripheral_lab"))
from audit_cubegm_elf_deps import DEFAULT_BACKUP, DEFAULT_ROOTFS, audit_cubegm


def test_cubegm_elf_deps_report_exists_and_is_valid():
    report_path = ROOT / "analysis/driver_port/CUBEGM_ELF_DEPS_v1.json"
    if not report_path.exists():
        pytest.skip("local /cubegm audit json not generated")
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["elf_count"] >= 100
    assert data["missing_from_local_snapshots"] == []
    assert "picoarch" in data["binaries"]
    assert "cores/frogui_libretro.so" in data["binaries"]
    assert data["binaries"]["picoarch"]["interp"] == "/lib/ld.so.1"
    assert "libpthread.so.0" in data["binaries"]["picoarch"]["needed"]


def test_cubegm_audit_matches_live_backup_when_present():
    if not DEFAULT_BACKUP.is_dir():
        pytest.skip("local /cubegm backup not present")
    live = audit_cubegm(DEFAULT_BACKUP, DEFAULT_ROOTFS)
    assert live["missing_from_local_snapshots"] == []
    assert live["elf_count"] == 155
    assert "libSDL-1.2.so.0" in live["unique_needed"] or any("SDL" in x for x in live["unique_needed"])
