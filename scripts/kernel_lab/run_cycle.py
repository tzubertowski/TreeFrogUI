"""Run one bounded diagnostic boot and collect the automatic watchdog return."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "release/upstream-TreeFrogUI/apps/usb_mode/pc"))
import r36

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--out", type=Path, default=ROOT / "payload/kernel_lab")
args = parser.parse_args()
manifest = json.loads((args.out / "manifest.json").read_text())
watchdog = manifest["diagnostic_watchdog"]
seconds = watchdog["timeout_seconds"]
if seconds > 120:
    raise SystemExit("Use a <=120 second watchdog for this bounded runner")
for group in ["sha256", "loader_sha256"]:
    for name, expected in manifest[group].items():
        if hashlib.sha256((args.out / name).read_bytes()).hexdigest() != expected:
            raise SystemExit(f"build manifest mismatch: {name}")

logs = ROOT / "analysis/driver_port"
record = {"image_sha256": manifest["sha256"]["vmlinux.bin"], "watchdog_seconds": seconds}
attempt = logs / "attempts" / str(time.time_ns())
attempt.mkdir(parents=True, exist_ok=True)


def checkpoint(state):
    record["state"] = state
    text = json.dumps(record, indent=2) + "\n"
    (attempt / "cycle.json").write_text(text)
    (logs / "last_cycle.json").write_text(text)


device = r36.R36()
try:
    code, raw = device.run("uname -r; cat /proc/uptime; test -e /proc/r36boot && echo LOADED; echo END")
    if b"4.4.186-release" not in raw:
        raise RuntimeError("runner requires the measured stock kernel")
    if b"LOADED" in raw:
        raise RuntimeError("loader already loaded; cancel or watchdog-restart stock before changing it")
    record["preboot"] = raw.decode("utf-8", "replace")
    files = [("r36boot.ko", "r36boot.ko"), ("r36bootctl", "r36bootctl"),
             ("vmlinux.bin", "r36-vmlinux.bin"), ("r36-lab.dtb", "r36-lab.dtb"),
             ("r36hello.ko", "r36hello.ko"), ("r36-wdt-diag", "r36-wdt-diag")]
    for local, remote in files:
        device.put(str(args.out / local), "/cubegm/" + remote)
    command = (
        "insmod /mnt/sdcard/cubegm/r36boot.ko || exit 1; sync; "
        "echo 3 > /proc/sys/vm/drop_caches; "
        "/mnt/sdcard/cubegm/r36bootctl prepare || exit 2; "
        "/mnt/sdcard/cubegm/r36bootctl probe || exit 3; "
        "cat /proc/r36boot; dmesg | tail -4")
    code, raw = device.run(command)
    print(raw.decode("utf-8", "replace"), flush=True)
    record["preparation"] = raw.decode("utf-8", "replace")
    if code:
        raise RuntimeError(f"prepare/probe failed: rc={code}")
    checkpoint("prepared")
    code, raw = device.run(
        "rm -f /mnt/sdcard/cubegm/r36-own-kernel-proof.txt /mnt/sdcard/cubegm/r36-driver-test.txt; "
        "sync; /mnt/sdcard/cubegm/r36bootctl boot-detached")
    if code:
        raise RuntimeError(f"handoff command failed: rc={code}")
    record["handoff"] = raw.decode("utf-8", "replace")
    print(record["handoff"], flush=True)
    started = time.monotonic()
    checkpoint("handoff requested")
finally:
    device.close()

console = subprocess.run([sys.executable, str(ROOT / "scripts/kernel_lab/ports_console.py"),
                          "status", "--wait", str(min(12, seconds // 2))],
                         capture_output=True, text=True, timeout=35)
record["cdc_status"] = {"code": console.returncode, "output": console.stdout + console.stderr}
checkpoint("CDC checked; waiting for watchdog")
print(record["cdc_status"]["output"], flush=True)
remaining = seconds + 27 - (time.monotonic() - started)
if remaining > 0:
    print(f"Waiting {remaining:.1f}s for automatic return to stock...", flush=True)
    time.sleep(remaining)
try:
    device = r36.R36()
except BaseException as error:
    record["automatic_return_verified"] = False
    record["return_error"] = str(error)
    record["elapsed_seconds"] = time.monotonic() - started
    checkpoint("stock USB did not return at expected deadline")
    raise
try:
    code, raw = device.run(
        "uname -a; cat /proc/uptime; "
        "sh /mnt/sdcard/cubegm/r36_keepawake.sh start; "
        "cat /mnt/sdcard/cubegm/r36-own-kernel-proof.txt /mnt/sdcard/cubegm/r36-driver-test.txt 2>/dev/null; "
        "echo END")
    record["postboot"] = raw.decode("utf-8", "replace")
    print(record["postboot"], flush=True)
finally:
    device.close()
subprocess.run([sys.executable, str(ROOT / "scripts/kernel_lab/collect_ramconsole.py")], check=True)
trace = json.loads((logs / "postboot_ramconsole.json").read_text())
record["trace"] = trace
pre_uptime = float(record["preboot"].splitlines()[1].split()[0])
post_uptime = float(record["postboot"].splitlines()[1].split()[0])
reset_observed = post_uptime + 5 < pre_uptime + (time.monotonic() - started)
record["automatic_return_verified"] = ("4.4.186-release" in record["postboot"] and
                                        trace["watchdog_seconds"] == seconds and reset_observed)
(logs / "runs" / trace["session_tag"] / "cycle.json").write_text(json.dumps(record, indent=2) + "\n")
(logs / "last_cycle.json").write_text(json.dumps(record, indent=2) + "\n")
checkpoint("collected")
print("Automatic return:", record["automatic_return_verified"],
      "; boot stage:", trace["stage_description"])
