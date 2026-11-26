"""Audit launch scripts, /tmp/tfdevice.env, PICOARCH_DRIVER, and core inventory in /cubegm backup."""
import argparse
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BACKUP = ROOT / "analysis/boot_crypto/backups/20261116T161658Z_cubegm"


def parse_tfdevice_env(zhijack_text: str) -> dict[str, str]:
    m = re.search(r"cat\s*>\s*/tmp/tfdevice\.env\s*<<EOF\r?\n(.*?)\r?\nEOF", zhijack_text, re.S)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def audit_cubegm_runtime(backup_dir: Path) -> dict[str, Any]:
    zhijack = backup_dir / "zhijack.sh"
    zhijack_text = zhijack.read_text(encoding="utf-8", errors="replace") if zhijack.is_file() else ""

    tfdevice_env = parse_tfdevice_env(zhijack_text)
    ld_paths = re.findall(r"export\s+LD_LIBRARY_PATH=([^\s\r\n]+)", zhijack_text)
    sh_scripts = sorted(p.relative_to(backup_dir).as_posix() for p in backup_dir.rglob("*.sh") if p.is_file())
    cores = sorted(p.name for p in (backup_dir / "cores").glob("*.so") if p.is_file()) if (backup_dir / "cores").is_dir() else []

    required_entries = {
        "picoarch": (backup_dir / "picoarch").is_file(),
        "frogui_core": (backup_dir / "cores/frogui_libretro.so").is_file(),
        "zhijack.sh": zhijack.is_file(),
        "shutdown.sh": (backup_dir / "shutdown.sh").is_file(),
        "usb_mode.sh": (backup_dir / "usb_mode.sh").is_file(),
        "tfusbd.sh": (backup_dir / "tfusbd.sh").is_file(),
        "dsperate/run_sf3000.sh": (backup_dir / "dsperate/run_sf3000.sh").is_file(),
    }

    return {
        "backup_dir": backup_dir.relative_to(ROOT).as_posix() if backup_dir.is_relative_to(ROOT) else str(backup_dir),
        "required_entries": required_entries,
        "all_required_present": all(required_entries.values()),
        "tfdevice_env": tfdevice_env,
        "ld_library_path_lines": ld_paths,
        "launch_handoff_file": "/mnt/sdcard/cubegm/frogui_launch.txt",
        "supports_picoarch_driver_env": "PICOARCH_DRIVER" in zhijack_text,
        "shell_script_count": len(sh_scripts),
        "shell_scripts": sh_scripts,
        "core_count": len(cores),
        "cores": cores,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, default=DEFAULT_BACKUP)
    parser.add_argument("--out", type=Path, default=ROOT / "analysis/driver_port/CUBEGM_RUNTIME_AUDIT_v1.json")
    args = parser.parse_args()
    report = audit_cubegm_runtime(args.backup)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Runtime audit: scripts={report['shell_script_count']} cores={report['core_count']} ready={report['all_required_present']}")


if __name__ == "__main__":
    main()
