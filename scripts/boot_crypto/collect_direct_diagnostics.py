"""Collect read-only evidence after a failed direct boot, without resetting trace RAM."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/kernel_lab"))
from trace_format import decode


def main():
    runpy.run_path(str(ROOT / "payload/kernel_ready/START.py"), run_name="direct_diagnostics")
    transport = sys.modules["acceptance"].WorkerTransport()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "analysis/boot_crypto" / ("post_restore_" + stamp)
    out.mkdir()
    report = {"captured_utc": stamp, "boot_files_modified": False,
              "trace_may_have_been_lost_to_power_cycle": True, "commands": {}}
    queries = {
        "trace.bin": "/mnt/sdcard/cubegm/mdump 2f91000 3584",
        "runtime.txt": "uname -a; cat /proc/uptime; cat /proc/cmdline; cat /proc/mounts",
        "boot_hashes.txt": "md5sum /mnt/sdcard/cubegm/advapi32.dll /mnt/sdcard/cubegm/Bubbles.scr /mnt/sdcard/cubegm/ApplicationFrame.dll",
        "proof_files.txt": "for f in /mnt/sdcard/cubegm/r36-direct-progress.txt /mnt/sdcard/cubegm/r36-direct-proof.txt /mnt/sdcard/cubegm/r36-direct-cmdline.txt /mnt/sdcard/cubegm/r36-direct-meminfo.txt; do if test -f \"$f\"; then echo \"$f\"; cat \"$f\"; else echo \"ABSENT $f\"; fi; done",
        "dmesg.txt": "dmesg",
    }
    for filename, command in queries.items():
        code, raw = transport.run(command, timeout=15)
        (out / filename).write_bytes(raw)
        report["commands"][filename] = {"exit_code": code, "bytes": len(raw),
                                        "sha256": hashlib.sha256(raw).hexdigest()}
        if filename == "trace.bin":
            try:
                metadata, log = decode(raw)
                expected = json.loads((ROOT / "payload/kernel_direct_advapi_oneshot/manifest.json").read_text())["session_tag"]
                metadata["matches_direct_trial_session"] = metadata["session_tag"] == expected
                report["trace"] = metadata
                (out / "trace.json").write_text(json.dumps(metadata, indent=2) + "\n")
                (out / "trace.log").write_bytes(log)
            except ValueError as error:
                report["trace"] = {"valid": False, "reason": str(error)}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(str(out))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
