"""Collect memory/module test reports after the console returns to stock."""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

from collect_proof import validate_proof

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "release/upstream-TreeFrogUI/apps/usb_mode/pc"))
import r36


def main():
    device = r36.R36()
    missing = []
    saved = {}
    try:
        code, status = device.run(
            "uname -a; cat /proc/uptime; "
            "sh /mnt/sdcard/cubegm/r36_keepawake.sh start; "
            "rm -f /mnt/sdcard/cubegm/r36-test-autoreboot; "
            "md5sum /mnt/sdcard/cubegm/vmlinux.uImage /mnt/sdcard/cubegm/avp.uImage "
            "/mnt/sdcard/cubegm/dtb.bin; "
            "sh /mnt/sdcard/cubegm/r36_keepawake.sh status")
        if code:
            raise RuntimeError(f"status command failed: {code}")
        (ROOT / "analysis/kernel_lab_memory_postboot.txt").write_bytes(status)
        for remote, name in [
            ("r36-own-kernel-proof.txt", "kernel_lab_memory_boot_proof.txt"),
            ("r36-memory-test.txt", "kernel_lab_memory_test.txt"),
            ("r36-memory-kmsg.txt", "kernel_lab_memory_kmsg.txt"),
        ]:
            path = ROOT / "analysis" / name
            try:
                device.get("/cubegm/" + remote, str(path))
                saved[name] = path.read_bytes()
            except Exception as error:
                missing.append({"file": remote, "error": str(error)})
    finally:
        device.close()
    image = (ROOT / "payload/kernel_lab/vmlinux.bin").read_bytes()
    proof = saved.get("kernel_lab_memory_boot_proof.txt", b"")
    valid_boot = False
    try:
        fields = validate_proof(proof, image)
        valid_boot = True
    except ValueError as error:
        fields = {"error": str(error)}
    report = saved.get("kernel_lab_memory_test.txt", b"").decode("utf-8", "replace")
    numbers = {key: int(value) for key, value in re.findall(r"^([a-z_]+)=([0-9]+)$", report, re.M)}
    plan = (ROOT / "analysis/kernel_lab_reclaim_plan.bin").read_bytes()
    live_pages = sum(bool(usable) for _, usable in struct.iter_unpack("<II", plan))
    expected_stock = ["f994b5e32dc90c5eec7e4bd965bff8fe", "36cf812151712a8a1ec01911ac03ab74",
                      "9492f590fc2db86694d3fdc52a25c3e4"]
    report_matches_image = (valid_boot and ("version=" + fields["version"] + "\n") in report)
    passed = (report_matches_image and "overall=PASS\n" in report and
              numbers.get("stage_total") == live_pages and
              numbers.get("stage_valid") == live_pages and
              numbers.get("former_loader_pages_reused", 0) > 0 and
              numbers.get("ram_test_errors") == 0)
    result = {
        "hardware_boot_verified": valid_boot,
        "userspace_proof": fields,
        "memory_and_modules_passed": passed,
        "report_matches_image": report_matches_image,
        "preboot_plan_live_pages": live_pages,
        "measurements": numbers,
        "missing_files": missing,
        "stock_boot_files_unchanged": all(d.encode() in status for d in expected_stock),
        "automatic_return_verified": False,
        "image_sha256": hashlib.sha256(image).hexdigest(),
        "report_sha256": {name: hashlib.sha256(raw).hexdigest() for name, raw in saved.items()},
    }
    (ROOT / "analysis/kernel_lab_memory_result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not passed:
        print("Tests did not all pass; inspect the saved report and kernel log.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
