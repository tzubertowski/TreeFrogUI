"""One cold NOR boot of the restored Linux 7 candidate; collect, never retry boot."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import sys
import time
import uuid

from loader_fs_probe import RESTORE_MAGIC
from peripheral_result import avp_result, display_result, input_result, audio_result, usb_cdc_result, core_result, frontend_backend_result

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/kernel_lab"))
from trace_format import decode

STOCK = {
    "advapi32.dll": "3510ffdfd039f850345ace1489572659",
    "Bubbles.scr": "b73a4a1bf1703e240c229cd34aa8f3f8",
    "ApplicationFrame.dll": "d2921c305d35ffdc59b73040c0ebbc73",
    "vmlinux.uImage": "f994b5e32dc90c5eec7e4bd965bff8fe",
    "dtb.bin": "9492f590fc2db86694d3fdc52a25c3e4",
    "avp.uImage": "36cf812151712a8a1ec01911ac03ab74",
}
SD = "/mnt/sdcard/cubegm/"


def poweroff_console(transport, record, started, after_minutes):
    """Tests only: power the console off; never part of accepted profiles."""
    if after_minutes > 0:
        remaining = started + after_minutes * 60 - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
    record["poweroff_requested"] = True
    try:
        code, _ = transport.run("command -v poweroff", timeout=10)
        method = "poweroff" if code == 0 else "reboot -p"
    except Exception as error:
        record.update(poweroff_method=None, poweroff_verified=False, poweroff_error=str(error))
        return
    record["poweroff_method"] = method
    try:
        transport.run(method, timeout=15)
    except Exception:
        pass
    deadline = time.monotonic() + 60
    verified = False
    while time.monotonic() < deadline:
        time.sleep(5)
        try:
            transport.run("true", timeout=8)
        except Exception:
            verified = True
            break
    record["poweroff_verified"] = verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deploy", action="store_true", required=True)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--poweroff-on-completion", action="store_true",
                        help="power the console off as soon as the trial finishes (tests only)")
    parser.add_argument("--poweroff-after", type=int, default=0, metavar="MIN",
                        help="power the console off MIN minutes after trial start (0=disabled, tests only)")
    args = parser.parse_args()
    assert args.poweroff_after >= 0, "poweroff delay must not be negative"
    folder = args.folder
    started = time.monotonic()
    manifest = json.loads((folder / "manifest.json").read_text())
    watchdog_seconds = manifest.get('watchdog_seconds', 30)
    assert type(watchdog_seconds) is int and 30 <= watchdog_seconds <= 120
    assert manifest["custom_kernel"] and manifest["copy_spec"]["restore_stock"]
    for name in ("cold_restore_emulation.json", "cold_restore_native_fallback.json"):
        assert json.loads((folder / name).read_text())["passed"]
    image = folder / "advapi32.dll.encrypted.NOT_DEPLOYED"
    assert hashlib.sha256(image.read_bytes()).hexdigest() == manifest["sha256"]
    assert image.stat().st_size == manifest["copy_spec"]["bytes"]
    receipt = ROOT / "analysis/boot_crypto" / (folder.name + "_trial.json")
    assert not receipt.exists(), "never overwrite an earlier cold trial; use a new candidate"
    record = {"active": False, "stock_restored": False, "cold_boot_verified": False,
              "power_cycle_verified": False, "reset_method": "hardware watchdog reset through NOR; no RAM handoff",
              "native_restore_verified": False, "candidate_folder": str(folder),
              "image_sha256": manifest["sha256"], "session_tag": manifest["session_tag"],
              "run_id": uuid.uuid4().hex, "boot_requests": 0, "state": "preflight",
              "poweroff_requested": args.poweroff_on_completion or args.poweroff_after > 0,
              "poweroff_method": None, "poweroff_verified": None}

    def save():
        receipt.write_text(json.dumps(record, indent=2) + "\n")

    runpy.run_path(str(ROOT / "payload/kernel_ready/START.py"), run_name="restored_cold_trial")
    acceptance = sys.modules["acceptance"]
    transport = acceptance.WorkerTransport()

    def run(command, timeout=15):
        code, raw = transport.run(command, timeout=timeout)
        if code:
            raise RuntimeError(f"rc={code}: {raw.decode('utf-8', 'replace')}")
        return raw

    def hashes():
        raw = run("md5sum " + " ".join(SD + name for name in STOCK))
        return {path.rsplit("/", 1)[1]: digest for path, digest in acceptance.parse_hashes(raw).items()}

    raw = run("uname -a; cat /proc/uptime; test ! -e /proc/r36boot")
    assert b"4.4.186-release" in raw
    assert hashes() == STOCK
    record["stock_before"] = raw.decode().strip()
    save()
    for local, remote in [(ROOT / "analysis/boot_crypto/original_advapi32.dll", "R36STOCK.ENC"),
                          (folder / "R36PROBE.BIN", "R36PROBE.BIN"),
                          (Path(manifest.get("source_profile", ROOT / "payload/kernel_ready/boot")) / "r36hello.ko", "r36hello.ko")]:
        transport.put(local, "/cubegm/" + remote)
        assert hashlib.md5(local.read_bytes()).hexdigest().encode() in run("md5sum " + SD + remote)
    profile = Path(manifest.get("source_profile", ROOT / "payload/kernel_ready/boot"))
    profile_manifest = json.loads((profile / "manifest.json").read_text())
    for name in manifest.get("extra_device_files", []):
        assert Path(name).name == name
        local = profile / name
        assert hashlib.sha256(local.read_bytes()).hexdigest() == profile_manifest["sha256"][name]
        transport.put(local, "/cubegm/" + name)
        assert hashlib.md5(local.read_bytes()).hexdigest().encode() in run("md5sum " + SD + name)
    previous = run("if test -f " + SD + "r36-own-kernel-proof.txt; then cat " + SD + "r36-own-kernel-proof.txt; fi")
    receipt.with_suffix(".previous-proof.txt").write_bytes(previous)
    run("printf '%s' " + record["run_id"] + " > " + SD + "r36-run-id.txt; rm -f " + SD +
        "r36-own-kernel-proof.txt " + SD + "r36-driver-test.txt " + SD + "r36-minimal-meminfo.txt " +
        SD + "r36-minimal-interrupts.txt " + SD + "r36-avp-probe.txt " + SD + "r36-display-probe.txt " +
        SD + "r36-usb-cdc-probe.txt " + SD + "r36-usb-interrupts.txt " + SD + "r36-frontend-probe.txt " +
        SD + "r36-ui-probe.txt " + SD + "r36-ui-child.txt " + SD + "r36-ui-keys.txt; sync")
    staged = "r36-cold-" + manifest["session_tag"][2:] + ".staged"
    transport.put(image, "/cubegm/" + staged)
    expected_image_md5 = hashlib.md5(image.read_bytes()).hexdigest().encode()
    assert expected_image_md5 in run("md5sum " + SD + staged)
    record.update(active=True, state="installing verified cold image")
    save()
    try:
        assert expected_image_md5 in run("cat " + SD + staged + " > " + SD + "advapi32.dll; sync; md5sum " + SD + "advapi32.dll", timeout=25)
        mounts = run("kill -STOP $(pidof cubevol) 2>/dev/null; kill -STOP $(pidof picoarch) 2>/dev/null; "
                     "swapoff -a || exit 21; sync; "
                     "mount -t vfat -o remount,ro /dev/mmcblk0p1 /mnt/sdcard || exit 22; cat /proc/mounts", timeout=35)
        rows = [line.split() for line in mounts.decode().splitlines() if line.startswith("/dev/mmcblk0p1 ")]
        assert rows and all("ro" in row[3].split(",") for row in rows)
        receipt.with_suffix(".quiesce.txt").write_bytes(mounts)
        record.update(boot_requests=1, state="hardware watchdog reset requested; no RAM handoff")
        save()
        run(SD + "r36-wdt-diag --arm 187500 5", timeout=12)
        time.sleep(watchdog_seconds + 5)
        deadline = time.monotonic() + 90
        while True:
            try:
                raw = run("uname -a; cat /proc/uptime", timeout=10)
                assert b"4.4.186-release" in raw
                break
            except Exception as error:
                record["last_reconnect_error"] = str(error)
                save()
                if time.monotonic() >= deadline:
                    raise RuntimeError("stock MTP did not return; no further reset requested") from error
                time.sleep(4)
        record["stock_after"] = raw.decode().strip()
        receipt.with_suffix(".runtime.txt").write_bytes(raw)
        before_cleanup = hashes()
        record["stock_hashes_before_cleanup"] = before_cleanup
        record["stock_already_restored_before_host_cleanup"] = before_cleanup == STOCK
        trace_raw = run(SD + "mdump 2f91000 3584")
        receipt.with_suffix(".trace.bin").write_bytes(trace_raw)
        try:
            metadata, log = decode(trace_raw)
            record["trace"] = metadata
            receipt.with_suffix(".kernel.log").write_bytes(log)
        except ValueError as error:
            record["trace_error"] = str(error)
        stamp_raw = run(SD + "mdump 2f91e00 64")
        receipt.with_suffix(".restore.bin").write_bytes(stamp_raw)
        stamp = struct.unpack("<16I", stamp_raw)
        record["restore_receipt"] = {"words": [hex(value) for value in stamp]}
        expected = (RESTORE_MAGIC, 1, int(manifest["session_tag"], 0), 1,
                    manifest["copy_spec"]["bytes"], manifest["copy_spec"]["crc32"], manifest["copy_spec"]["crc32"], 6)
        record["native_restore_verified"] = stamp[:8] == expected and before_cleanup == STOCK
        for remote, suffix in [("r36-own-kernel-proof.txt", ".proof.txt"),
                               ("r36-driver-test.txt", ".driver.txt"),
                               ("r36-minimal-meminfo.txt", ".meminfo.txt"),
                               ("r36-minimal-interrupts.txt", ".interrupts.txt"),
                               ("r36-avp-probe.txt", ".avp.txt"),
                               ("r36-display-probe.txt", ".display.txt"),
                               ("r36-usb-cdc-probe.txt", ".usb.txt"),
                               ("r36-usb-interrupts.txt", ".usb-interrupts.txt"),
                               ("r36-frontend-probe.txt", ".frontend.txt"),
                               ("r36-ui-probe.txt", ".ui.txt"),
                               ("r36-ui-child.txt", ".ui-child.txt"),
                               ("r36-ui-keys.txt", ".ui-keys.txt")]:
            code, data = transport.run("cat " + SD + remote, timeout=12)
            if code == 0:
                receipt.with_suffix(suffix).write_bytes(data)
                if remote == "r36-avp-probe.txt":
                    accepted = avp_result(data, record["run_id"])
                    record["avp_acceptance"] = accepted
                    record["avp_transport_verified"] = accepted["userspace_verified"]
                    record["kernel_avp_transport_verified"] = accepted["kernel_verified"]
                elif remote == "r36-usb-cdc-probe.txt":
                    record["usb_device_acceptance"] = usb_cdc_result(data, record["run_id"], profile_manifest["release"])
                elif remote == "r36-frontend-probe.txt":
                    record["frontend_backend_acceptance"] = frontend_backend_result(data, record["run_id"], profile_manifest["release"])
                elif remote == "r36-display-probe.txt":
                    accepted = display_result(data, record["run_id"], profile_manifest["release"],
                                              kms=profile_manifest.get("profile") == "display-kms-probe")
                    record["display_acceptance"] = accepted
                    record["display_passive_verified"] = accepted["passive_verified"]
                    record["display_scanout_verified"] = accepted["scanout_verified"]
                    if b"R36 INPUT INVENTORY V1" in data:
                        record["input_acceptance"] = input_result(data, record["run_id"], profile_manifest["release"])
                    if b"R36 AUDIO SILENT PROBE V1" in data:
                        record["audio_acceptance"] = audio_result(data, record["run_id"], profile_manifest["release"])
                    if b"R36 CORE CONSOLE PROBE V1" in data:
                        record["core_acceptance"] = core_result(data, record["run_id"], profile_manifest["release"])
        try:
            profile = Path(manifest.get("source_profile", ROOT / "payload/kernel_ready/boot"))
            kernel_manifest = json.loads((profile / "manifest.json").read_text())
            record["proof"] = acceptance.proof_result(receipt.with_suffix(".proof.txt").read_bytes(), kernel_manifest, record["run_id"])
            trace = record.get("trace", {})
            record["cold_boot_verified"] = (record["native_restore_verified"] and trace.get("stage") == 6 and
                                             trace.get("session_tag") == manifest["session_tag"] and
                                             trace.get("entry") == manifest["original_entry"])
        except (ValueError, OSError) as error:
            record["proof_error"] = str(error)
        record["state"] = "cold trial collected; inspecting final stock files"
        save()
    except Exception as error:
        record["trial_error"] = str(error)
        save()
    finally:
        try:
            current = hashes()
            assert all(current[name] == digest for name, digest in STOCK.items() if name != "advapi32.dll")
            if current["advapi32.dll"] != STOCK["advapi32.dll"]:
                assert STOCK["advapi32.dll"].encode() in run("md5sum " + SD + "R36STOCK.ENC")
                run("mount -t vfat -o remount,rw /dev/mmcblk0p1 /mnt/sdcard")
                assert STOCK["advapi32.dll"].encode() in run("cat " + SD + "R36STOCK.ENC > " + SD + "advapi32.dll; sync; md5sum " + SD + "advapi32.dll", timeout=25)
                record["host_cleanup_wrote_boot_file"] = True
            else:
                record["host_cleanup_wrote_boot_file"] = False
            assert hashes() == STOCK
            record.update(active=False, stock_restored=True)
        except Exception as error:
            record["restore_error"] = str(error)
        if record["stock_restored"]:
            record["state"] = ("direct NOR Linux7/PID1/SD verified; automatic stock return and native restoration verified"
                               if record["cold_boot_verified"] else "cold trial evidence collected; stock restoration verified")
        if record["poweroff_requested"]:
            save()
            poweroff_console(transport, record, started, args.poweroff_after)
        save()
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
