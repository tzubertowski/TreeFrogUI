"""Verify OTG Wi-Fi/BT firmware inventory against vm_build_kernel.sh and mock /lib/firmware trees."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/peripheral_lab"))
from prepare_otg_firmware import OTG_ADAPTER_FIRMWARE, inspect_firmware_dir


def test_firmware_kconfigs_match_vm_build_kernel():
    build = (ROOT / "scripts/peripheral_lab/vm_build_kernel.sh").read_text()
    for key, spec in OTG_ADAPTER_FIRMWARE.items():
        assert spec["kconfig"] in build, f"{key} kconfig {spec['kconfig']} missing in vm_build_kernel.sh"


def test_inspect_firmware_dir_reports_ready_and_missing(tmp_path):
    fw = tmp_path / "firmware"
    (fw / "rtw88").mkdir(parents=True)
    (fw / "rtw88/rtw8821c_fw.bin").write_bytes(b"FW8821C")
    (fw / "rtl_bt").mkdir(parents=True)
    (fw / "rtl_bt/rtl8761bu_fw.bin").write_bytes(b"FWBT")
    (fw / "rtl_bt/rtl8761bu_config.bin").write_bytes(b"CFGBT")

    report = inspect_firmware_dir(fw)
    assert report["adapters"]["wifi_rtl8xxxu_8188eu_8192cu"]["ready"] is True
    assert report["adapters"]["bt_csr_generic"]["ready"] is True
    assert report["adapters"]["wifi_rtw88_8821cu"]["ready"] is True
    assert report["adapters"]["bt_rtl8761bu"]["ready"] is True
    assert report["adapters"]["wifi_mt7601u"]["ready"] is False
    assert report["adapters"]["wifi_mt7601u"]["missing_files"] == ["mt7601u.bin"]

    out_json = tmp_path / "fw_report.json"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/peripheral_lab/prepare_otg_firmware.py"),
         "--firmware-dir", str(fw), "--out", str(out_json)],
        check=True,
        capture_output=True,
        timeout=10,
    )
    loaded = json.loads(out_json.read_text(encoding="utf-8"))
    assert loaded["ready_profiles"] == 4
