"""Install one stock-bridge probe, collect evidence, and restore stock over MTP."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys
import time
import struct

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/kernel_lab"))
from trace_format import decode
from loader_fs_probe import decode_copy_trace

STOCK_MD5 = "3510ffdfd039f850345ace1489572659"
TARGET = "/mnt/sdcard/cubegm/advapi32.dll"
BACKUP = "/mnt/sdcard/cubegm/r36-stock-advapi32-3510ffdf.enc"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deploy", action="store_true", required=True)
    parser.add_argument("--folder", type=Path, default=ROOT / "payload/kernel_stock_bridge_probe_v1")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    folder = args.folder
    manifest = json.loads((folder / "manifest.json").read_text())
    image = folder / "advapi32.dll.encrypted.NOT_DEPLOYED"
    assert hashlib.sha256(image.read_bytes()).hexdigest() == manifest["sha256"]
    expected = hashlib.md5(image.read_bytes()).hexdigest().encode()
    receipt = args.receipt or ROOT / "analysis/boot_crypto" / (folder.name + "_trial.json")
    if not receipt.parent.is_dir():
        parser.error("receipt parent must already exist")
    if manifest.get("filesystem_probe"):
        report = "fallback_emulation.json" if manifest.get("stock_fallback") else "fs_emulation.json"
        assert json.loads((folder / report).read_text())["passed"]
        if manifest.get("stock_fallback"):
            assert json.loads((folder / "fallback_emulation_native_decrypt.json").read_text())["passed"]
    copy_spec = manifest.get("copy_spec")
    if copy_spec:
        assert json.loads((folder / "fs_emulation_full_copy.json").read_text())["passed"]
        if copy_spec["restore_stock"]:
            assert image.stat().st_size == copy_spec["bytes"]
    record = {"active": False, "stock_restored": False, "hardware_verified": False,
              "candidate_folder": str(folder),
              "candidate_sha256": manifest["sha256"], "session_tag": manifest["session_tag"],
              "kernel": "original stock 4.4", "state": "preflight"}

    def save():
        receipt.write_text(json.dumps(record, indent=2) + "\n")

    runpy.run_path(str(ROOT / "payload/kernel_ready/START.py"), run_name="stock_bridge_probe")
    transport = sys.modules["acceptance"].WorkerTransport()

    def run(command, timeout=15):
        code, raw = transport.run(command, timeout=timeout)
        if code:
            raise RuntimeError(f"rc={code}: {command}: {raw.decode('utf-8', 'replace')}")
        return raw

    raw = run("uname -r; md5sum " + TARGET + " " + BACKUP)
    assert b"4.4.186-release" in raw and raw.count(STOCK_MD5.encode()) == 2
    run("test -f /mnt/sdcard/cubegm/r36-wdt-diag")
    if manifest.get("filesystem_probe"):
        seed = folder / "R36PROBE.BIN"
        transport.put(seed, "/cubegm/R36PROBE.BIN")
        assert hashlib.md5(seed.read_bytes()).hexdigest().encode() in run("md5sum /mnt/sdcard/cubegm/R36PROBE.BIN")
    if manifest.get("filesystem_write_probe"):
        sandbox = folder / "R36WRITE.BIN"
        transport.put(sandbox, "/cubegm/R36WRITE.BIN")
        assert hashlib.md5(sandbox.read_bytes()).hexdigest().encode() in run("md5sum /mnt/sdcard/cubegm/R36WRITE.BIN")
    if copy_spec or manifest.get("stock_fallback"):
        transport.put(ROOT / "analysis/boot_crypto/original_advapi32.dll", "/cubegm/R36STOCK.ENC")
        assert STOCK_MD5.encode() in run("md5sum /mnt/sdcard/cubegm/R36STOCK.ENC")
        if copy_spec and not copy_spec["restore_stock"]:
            sandbox = folder / "R36COPY.BIN"
            transport.put(sandbox, "/cubegm/R36COPY.BIN")
            assert hashlib.md5(sandbox.read_bytes()).hexdigest().encode() in run("md5sum /mnt/sdcard/cubegm/R36COPY.BIN")
    staged = "/cubegm/r36-stock-bridge-" + manifest["session_tag"][2:] + ".staged"
    transport.put(image, staged)
    assert expected in run("md5sum /mnt/sdcard" + staged)
    record.update(active=True, state="installing stock bridge image")
    save()
    restored = False
    try:
        assert expected in run("cat /mnt/sdcard" + staged + " > " + TARGET + "; sync; md5sum " + TARGET, timeout=25)
        command = ("kill -STOP $(pidof cubevol) 2>/dev/null; "
                   "kill -STOP $(pidof picoarch) 2>/dev/null; "
                   "swapoff -a || exit 21; sync; "
                   "mount -t vfat -o remount,ro /dev/mmcblk0p1 /mnt/sdcard || exit 22; cat /proc/mounts")
        raw = run(command, timeout=35)
        mounts = [line.split() for line in raw.decode().splitlines() if line.startswith("/dev/mmcblk0p1 ")]
        assert mounts and all("ro" in line[3].split(",") for line in mounts)
        record["state"] = "SD readonly and swap off; requesting one hardware watchdog reset"
        save()
        run("/mnt/sdcard/cubegm/r36-wdt-diag --arm 187500 5", timeout=12)
        time.sleep(30)
        deadline = time.monotonic() + 60
        while True:
            try:
                runtime = run("uname -a; cat /proc/uptime; md5sum " + TARGET, timeout=12)
                assert b"4.4.186-release" in runtime
                if copy_spec and copy_spec["restore_stock"]:
                    assert expected in runtime or STOCK_MD5.encode() in runtime
                    record["stock_already_restored_before_host_cleanup"] = STOCK_MD5.encode() in runtime
                else:
                    assert expected in runtime
                break
            except Exception as error:
                record["last_reconnect_error"] = str(error)
                save()
                if time.monotonic() >= deadline:
                    raise RuntimeError("MTP did not return; no second reset requested") from error
                time.sleep(5)
        receipt.with_suffix(".runtime.txt").write_bytes(runtime)
        raw = run("/mnt/sdcard/cubegm/mdump 2f91000 3584")
        receipt.with_suffix(".trace.bin").write_bytes(raw)
        try:
            metadata, log = decode(raw)
            record["trace"] = metadata
            record["hardware_verified"] = (metadata["stage"] == manifest["trace_stage"] and
                                            metadata["session_tag"] == manifest["session_tag"])
            if manifest.get("filesystem_probe"):
                fields = struct.unpack_from("<10I", raw, 64)
                record["loader_fs_probe"] = dict(zip(
                    ["status_before", "status_resumed", "resolve_rc", "open_fd", "read_rc",
                     "close_rc", "status_after", "reserved0", "reserved1", "loader_image_buffer"],
                    [hex(value) for value in fields]))
                record["loader_fs_probe"]["content_matches"] = raw[128:192] == (folder / "R36PROBE.BIN").read_bytes()
                record["loader_fs_probe"]["critical_depth_before"] = struct.unpack_from("<I", raw, 108)[0]
                if not copy_spec and not manifest.get("forced_watchdog_test"):
                    record["loader_fs_probe"]["globals_before"] = [hex(value) for value in struct.unpack_from("<12I", raw, 192)]
                    record["loader_fs_probe"]["last_resolver_path"] = raw[256:384].split(b"\0", 1)[0].decode("ascii", "replace")
                record["loader_fs_probe"]["runtime_api_prefixes"] = raw[512:672].hex()
                if manifest.get("filesystem_write_probe"):
                    record["loader_fs_probe"]["write_results"] = [hex(value) for value in struct.unpack_from("<4I", raw, 112)]
                    record["loader_fs_probe"]["native_written_content_matches"] = raw[704:768] == (folder / "R36PROBE.BIN").read_bytes()
                    expected_output = hashlib.md5((folder / "R36PROBE.BIN").read_bytes()).hexdigest().encode()
                    output_hash = run("md5sum /mnt/sdcard/cubegm/R36WRITE.BIN")
                    record["loader_fs_probe"]["output_hash_after_boot"] = output_hash.decode().strip()
                    record["hardware_verified"] = record["hardware_verified"] and expected_output in output_hash and record["loader_fs_probe"]["native_written_content_matches"]
                if copy_spec:
                    values = decode_copy_trace(raw)
                    record["native_copy"] = values
                    destination = TARGET if copy_spec["restore_stock"] else "/mnt/sdcard/cubegm/R36COPY.BIN"
                    output_hash = run("md5sum " + destination)
                    record["native_copy"]["output_hash_after_boot"] = output_hash.decode().strip()
                    record["hardware_verified"] = (record["hardware_verified"] and STOCK_MD5.encode() in output_hash and
                                                    values["read_bytes"] == values["written_bytes"] == copy_spec["bytes"] and
                                                    values["source_crc32"] == values["readback_crc32"] == copy_spec["crc32"] and values["phase"] == 6)
                    if copy_spec["restore_stock"]:
                        record["hardware_verified"] = record["hardware_verified"] and record.get("stock_already_restored_before_host_cleanup", False)
                if manifest.get("stock_fallback"):
                    fields = struct.unpack_from("<4I", raw, 432)
                    record["native_fallback"] = dict(zip(["phase", "backup_crc32", "decrypt_rc", "plaintext_bytes"], fields))
                    spec = manifest["stock_fallback"]
                    record["hardware_verified"] = (record["hardware_verified"] and fields ==
                                                    (6, spec["crc32"], 0, spec["bytes"] - 16))
                record["watchdog_skip_observed"] = metadata["stage"] == 197 and metadata["session_tag"] == manifest["session_tag"]
        except ValueError as error:
            record["trace_error"] = str(error)
        record["state"] = "stock returned; probe evidence captured; restoring original file"
        save()
    finally:
        # Never reset again as a recovery attempt. Restore only through a live shell.
        try:
            assert STOCK_MD5.encode() in run("md5sum " + BACKUP)
            current_hash = run("md5sum " + TARGET)
            if STOCK_MD5.encode() not in current_hash:
                run("mount -t vfat -o remount,rw /dev/mmcblk0p1 /mnt/sdcard")
                raw = run("cat " + BACKUP + " > " + TARGET + "; sync; md5sum " + TARGET, timeout=25)
                assert STOCK_MD5.encode() in raw
                record["host_cleanup_wrote_boot_file"] = True
            else:
                record["host_cleanup_wrote_boot_file"] = False
            state = ("native pre-kernel restoration verified through MTP; host did not rewrite the boot file"
                     if record.get("stock_already_restored_before_host_cleanup") and not record["host_cleanup_wrote_boot_file"]
                     else "original advapi restored and checksum verified through MTP")
            record.update(active=False, stock_restored=True, state=state)
            restored = True
        except Exception as error:
            record.update(state="reader recovery required; no additional reset requested", restore_error=str(error))
        save()
    print(json.dumps(record, indent=2))
    if not restored:
        raise SystemExit("Stock restoration is not verified; stop for reader recovery")


if __name__ == "__main__":
    main()
