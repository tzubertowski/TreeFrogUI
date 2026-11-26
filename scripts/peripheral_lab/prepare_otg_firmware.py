"""Inventory and verify /lib/firmware blobs needed by OTG USB Wi-Fi and Bluetooth adapters."""
import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

# Maps each enabled Linux 7.2 OTG driver/chipset from vm_build_kernel.sh to its
# required /lib/firmware relative paths (empty list = no external firmware file needed).
OTG_ADAPTER_FIRMWARE: dict[str, dict[str, Any]] = {
    "wifi_rtl8xxxu_8188eu_8192cu": {
        "kconfig": "RTL8XXXU",
        "kind": "wifi",
        "module": "rtl8xxxu",
        "firmware_files": [],
        "notes": "rtl8xxxu includes built-in or optional fw for RTL8188EU/8192CU/8188FTV",
    },
    "wifi_rtw88_8821cu": {
        "kconfig": "RTW88_8821CU",
        "kind": "wifi",
        "module": "rtw88_8821cu",
        "firmware_files": ["rtw88/rtw8821c_fw.bin"],
    },
    "wifi_rtw88_8822bu": {
        "kconfig": "RTW88_8822BU",
        "kind": "wifi",
        "module": "rtw88_8822bu",
        "firmware_files": ["rtw88/rtw8822b_fw.bin"],
    },
    "wifi_rtw88_8723du": {
        "kconfig": "RTW88_8723DU",
        "kind": "wifi",
        "module": "rtw88_8723du",
        "firmware_files": ["rtw88/rtw8723d_fw.bin"],
    },
    "wifi_mt7601u": {
        "kconfig": "MT7601U",
        "kind": "wifi",
        "module": "mt7601u",
        "firmware_files": ["mt7601u.bin"],
    },
    "wifi_rt2800usb": {
        "kconfig": "RT2800USB",
        "kind": "wifi",
        "module": "rt2800usb",
        "firmware_files": ["rt2870.bin"],
    },
    "wifi_ath9k_htc": {
        "kconfig": "ATH9K_HTC",
        "kind": "wifi",
        "module": "ath9k_htc",
        "firmware_files": ["ath9k_htc/htc_9271-1.4.0.fw"],
    },
    "bt_csr_generic": {
        "kconfig": "BT_HCIBTUSB",
        "kind": "bluetooth",
        "module": "btusb",
        "firmware_files": [],
        "notes": "Standard USB HCI dongles (e.g. CSR 0a12:0001) work without external firmware",
    },
    "bt_rtl8761bu": {
        "kconfig": "BT_HCIBTUSB_RTL",
        "kind": "bluetooth",
        "module": "btusb",
        "firmware_files": ["rtl_bt/rtl8761bu_fw.bin", "rtl_bt/rtl8761bu_config.bin"],
    },
    "bt_rtl8821cu": {
        "kconfig": "BT_HCIBTUSB_RTL",
        "kind": "bluetooth",
        "module": "btusb",
        "firmware_files": ["rtl_bt/rtl8821c_fw.bin", "rtl_bt/rtl8821c_config.bin"],
    },
    "bt_bcm20702a1": {
        "kconfig": "BT_HCIBTUSB_BCM",
        "kind": "bluetooth",
        "module": "btusb",
        "firmware_files": ["brcm/BCM20702A1-0a5c-21e8.hcd"],
    },
}


def inspect_firmware_dir(fw_dir: Path) -> dict[str, Any]:
    adapters: dict[str, Any] = {}
    ready_count = 0
    for key, spec in OTG_ADAPTER_FIRMWARE.items():
        required = spec["firmware_files"]
        missing = [rel for rel in required if not (fw_dir / rel).is_file()]
        ready = len(missing) == 0
        if ready:
            ready_count += 1
        adapters[key] = {
            "kind": spec["kind"],
            "module": spec["module"],
            "kconfig": spec["kconfig"],
            "required_files": required,
            "missing_files": missing,
            "ready": ready,
        }
    return {
        "firmware_dir": str(fw_dir),
        "total_profiles": len(adapters),
        "ready_profiles": ready_count,
        "adapters": adapters,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = inspect_firmware_dir(args.firmware_dir)
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
