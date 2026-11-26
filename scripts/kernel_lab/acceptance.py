"""Bounded boot/module acceptance. Importing this module never touches USB."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from preflight import validate
from trace_format import decode, PHYSICAL, SIZE

ROOT = Path(os.environ.get("R36_PROJECT_ROOT", Path(__file__).resolve().parents[2]))
STOCK_FILES = {
    "vmlinux.uImage": "f994b5e32dc90c5eec7e4bd965bff8fe",
    "avp.uImage": "36cf812151712a8a1ec01911ac03ab74",
    "dtb.bin": "9492f590fc2db86694d3fdc52a25c3e4",
}
INSPECT = "uname -a; cat /proc/uptime; test -e /proc/r36boot && echo LOADER_LOADED; echo R36_INSPECT_END"


class TransportError(RuntimeError):
    pass


class WrongFirmware(ValueError):
    pass


class WorkerTransport:
    def __init__(self, clock=time):
        self.clock = clock

    def call(self, action, timeout=20, **arguments):
        request = json.dumps({"action": action, **arguments})
        try:
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("device_worker.py")), request],
                                    capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise TransportError(f"WPD worker exceeded {timeout}s and was terminated") from error
        replies = [line[len("R36_RESULT="):] for line in result.stdout.splitlines() if line.startswith("R36_RESULT=")]
        if len(replies) != 1:
            raise TransportError(f"worker protocol error: {result.stderr or result.stdout}")
        reply = json.loads(replies[0])
        if not reply.get("ok"):
            raise TransportError(f"{reply.get('error_type')}: {reply.get('error')}")
        return reply

    def run(self, command, timeout=20):
        reply = self.call("run", command=command, timeout=timeout)
        return reply["code"], base64.b64decode(reply["output"], validate=True)

    def put(self, local, remote):
        reply = self.call("put", local=str(local), remote=remote, timeout=45)
        if reply["bytes"] != Path(local).stat().st_size:
            raise TransportError("upload size differs from local artifact")


def fields(raw, heading):
    lines = raw.decode("ascii").splitlines()
    if not lines or lines[0] != heading:
        raise ValueError("report header missing")
    result = {}
    for line in lines[1:]:
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in result:
            raise ValueError(f"duplicate report key: {key}")
        result[key] = value
    return result


def proof_result(raw, manifest, run_id):
    values = fields(raw, "R36 OWN KERNEL USERSPACE REACHED")
    required = {"run_id": run_id, "sysname": "Linux", "pid": "1", "machine": "mips",
                "release": manifest["release"], "version": manifest["build_version"]}
    if any(values.get(key) != value for key, value in required.items()):
        raise ValueError("proof is stale or belongs to another image/PID")
    return values


def driver_result(raw, manifest, run_id):
    values = fields(raw, "R36 DRIVER TEST")
    required = {"run_id": run_id, "release": manifest["release"], "version": manifest["build_version"],
                "load_rc": "0", "parameter_ok": "1", "unload_rc": "0", "sysfs_removed": "1", "result": "PASS"}
    if any(values.get(key) != value for key, value in required.items()):
        raise ValueError("driver test did not complete successfully for this run")
    return values


def inspect(raw):
    lines = raw.decode("ascii").splitlines()
    if len(lines) < 3 or lines[-1] != "R36_INSPECT_END":
        raise ValueError("incomplete stock identity response")
    if not lines[0].startswith("Linux buildroot 4.4.186-release #23 PREEMPT Tue Jan 27 16:21:59 CST 2026 mips "):
        raise WrongFirmware("console firmware does not match measured stock ABI")
    return {"uname": lines[0], "uptime": float(lines[1].split()[0]), "loader_loaded": "LOADER_LOADED" in lines}


def require_run(transport, command, timeout=20):
    code, raw = transport.run(command, timeout=timeout)
    if code:
        raise TransportError(f"remote exit {code}: {raw.decode('utf-8', 'replace')}")
    return raw


def wait_stock(transport, clock, timeout):
    end = clock.monotonic() + timeout
    errors = []
    while clock.monotonic() < end:
        remaining = end - clock.monotonic()
        try:
            code, raw = transport.run(INSPECT, timeout=max(0.1, min(8, remaining)))
            if code == 0:
                return inspect(raw), errors
        except WrongFirmware:
            raise
        except (TransportError, ValueError) as error:
            errors.append(str(error))
        remaining = end - clock.monotonic()
        if remaining > 0:
            clock.sleep(min(2, remaining))
    raise TransportError(f"stock MTP did not return before deadline; last error: {errors[-1:]}")


def parse_hashes(raw):
    return {path.decode("ascii"): digest.decode("ascii") for digest, path in
            re.findall(rb"^([0-9a-f]{32})\s+(/\S+)$", raw, re.M)}


def verify_remote(transport, expected):
    raw = require_run(transport, "md5sum " + " ".join(expected))
    actual = parse_hashes(raw)
    if any(actual.get(path) != digest for path, digest in expected.items()):
        raise ValueError("remote content digest differs; handoff not allowed")
    return actual


def run_profile(out, shared, transport, clock, directory, *, stock_wait=90):
    """One attempt only. Failures are checkpointed, never silently retried."""
    manifest = json.loads((out / "manifest.json").read_text())
    run_id = uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=True)
    result = {"run_id": run_id, "profile": manifest["profile"], "passed": False,
              "image_sha256": manifest["sha256"]["vmlinux.bin"], "handoff_requested": False}

    def checkpoint(state):
        result["state"] = state
        (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    checkpoint("checking stock")
    try:
        before, _ = wait_stock(transport, clock, stock_wait)
        result["stock_before"] = before
        verify_remote(transport, {"/mnt/sdcard/cubegm/" + name: digest for name, digest in STOCK_FILES.items()})
        transport.put(shared / "r36_keepawake.sh", "/cubegm/r36_keepawake.sh")
        transport.put(shared / "mdump", "/cubegm/mdump")
        verify_remote(transport, {"/mnt/sdcard/cubegm/" + name: hashlib.md5((shared / name).read_bytes()).hexdigest()
                                  for name in ["r36_keepawake.sh", "mdump"]})
        require_run(transport, "sh /mnt/sdcard/cubegm/r36_keepawake.sh start")
        if before["loader_loaded"]:
            transport.put(out / "r36-wdt-diag", "/cubegm/r36-wdt-diag")
            verify_remote(transport, {"/mnt/sdcard/cubegm/r36-wdt-diag": hashlib.md5((out / "r36-wdt-diag").read_bytes()).hexdigest()})
            checkpoint("resetting already-loaded diagnostic module")
            require_run(transport, "/mnt/sdcard/cubegm/r36-wdt-diag --arm 187500 5")
            clock.sleep(17)
            before, errors = wait_stock(transport, clock, stock_wait)
            result["initial_reset_poll_errors"] = errors
            if before["loader_loaded"]:
                raise ValueError("existing loader survived expected stock reset")
            require_run(transport, "sh /mnt/sdcard/cubegm/r36_keepawake.sh start")
            result["stock_before"] = before
            verify_remote(transport, {"/mnt/sdcard/cubegm/" + name: digest for name, digest in STOCK_FILES.items()})
        files = [("r36boot.ko", "r36boot.ko"), ("r36bootctl", "r36bootctl"),
                 ("vmlinux.bin", "r36-vmlinux.bin"), ("r36-lab.dtb", "r36-lab.dtb"),
                 ("r36hello.ko", "r36hello.ko"), ("r36-wdt-diag", "r36-wdt-diag")]
        expected = {}
        for local, remote in files:
            transport.put(out / local, "/cubegm/" + remote)
            expected["/mnt/sdcard/cubegm/" + remote] = hashlib.md5((out / local).read_bytes()).hexdigest()
        result["delivered_hashes"] = verify_remote(transport, expected)
        checkpoint("delivery verified")
        require_run(transport, "printf '%s' " + run_id + " > /mnt/sdcard/cubegm/r36-run-id.txt; "
                    "rm -f /mnt/sdcard/cubegm/r36-own-kernel-proof.txt /mnt/sdcard/cubegm/r36-driver-test.txt; sync")
        result["preparation"] = require_run(transport,
            "insmod /mnt/sdcard/cubegm/r36boot.ko || exit 1; "
            "echo 3 > /proc/sys/vm/drop_caches; "
            "/mnt/sdcard/cubegm/r36bootctl prepare || exit 2; "
            "/mnt/sdcard/cubegm/r36bootctl probe || exit 3; cat /proc/r36boot", timeout=40).decode()
        checkpoint("prepared and probed")
        result["handoff_requested"] = True
        started = clock.monotonic()
        checkpoint("handoff requested; response may be lost on disconnect")
        try:
            result["handoff_reply"] = require_run(transport, "/mnt/sdcard/cubegm/r36bootctl boot-detached").decode()
        except TransportError as error:
            result["handoff_transport_error"] = str(error)
        checkpoint("waiting for watchdog")
        seconds = manifest["diagnostic_watchdog"]["timeout_seconds"]
        clock.sleep(max(0, seconds + 5 - (clock.monotonic() - started)))
        after, errors = wait_stock(transport, clock, stock_wait)
        result["stock_after"] = after
        result["reconnect_poll_errors"] = errors
        result["reset_observed"] = after["uptime"] + 3 < before["uptime"] + clock.monotonic() - started
        require_run(transport, "sh /mnt/sdcard/cubegm/r36_keepawake.sh start")
        trace_raw = require_run(transport, f"/mnt/sdcard/cubegm/mdump {PHYSICAL:x} {SIZE}")
        # The original console has mdump; bundle tests require that dependency.
        (directory / "trace.bin").write_bytes(trace_raw)
        trace, log = decode(trace_raw)
        result["trace"] = trace
        (directory / "kernel.log").write_bytes(log)
        for remote, local in [("r36-own-kernel-proof.txt", "proof.txt"),
                              ("r36-driver-test.txt", "driver.txt"),
                              ("r36-minimal-meminfo.txt", "meminfo.txt"),
                              ("r36-minimal-interrupts.txt", "interrupts.txt")]:
            code, raw = transport.run("cat /mnt/sdcard/cubegm/" + remote)
            if code == 0:
                (directory / local).write_bytes(raw)
        result["stock_files_after"] = verify_remote(transport,
            {"/mnt/sdcard/cubegm/" + name: digest for name, digest in STOCK_FILES.items()})
        if not result["reset_observed"] or after["loader_loaded"]:
            raise ValueError("automatic fresh stock return not proven")
        if trace["entry"] != manifest["entry"] or trace["watchdog_seconds"] != seconds:
            raise ValueError("retained trace belongs to a different diagnostic image")
        if trace["destination_crc32"] != manifest["relocation_crc32"]:
            raise ValueError("destination CRC missing or failed; new kernel acceptance blocked")
        result["proof"] = proof_result((directory / "proof.txt").read_bytes(), manifest, run_id)
        if manifest["profile"] == "driver":
            result["driver"] = driver_result((directory / "driver.txt").read_bytes(), manifest, run_id)
        result["passed"] = True
        checkpoint("passed")
    except (TransportError, ValueError, OSError) as error:
        result["error"] = str(error)
        if not result["handoff_requested"]:
            try:
                transport.run("test ! -e /proc/r36boot || /mnt/sdcard/cubegm/r36bootctl cancel", timeout=8)
            except TransportError:
                pass
        checkpoint("failed; no further boot attempted")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--wait", type=int, default=180)
    args = parser.parse_args()
    if not 1 <= args.wait <= 600:
        parser.error("--wait must be 1..600 seconds")
    bundle_bytes = (args.bundle / "bundle.json").read_bytes()
    ready = json.loads((args.bundle / "READY.json").read_text())
    if not ready.get("offline_passed") or ready.get("emulated_cases") != 6:
        raise SystemExit("bundle has no complete offline acceptance record")
    if ready["bundle_manifest_sha256"] != hashlib.sha256(bundle_bytes).hexdigest():
        raise SystemExit("bundle manifest differs from offline acceptance record")
    bundle = json.loads(bundle_bytes)
    if bundle.get("version") != 1 or bundle.get("profiles") != ["boot", "driver"]:
        raise SystemExit("unexpected acceptance profile order")
    for name, digest in bundle["references_sha256"].items():
        path = ROOT / name
        if ROOT.resolve() not in path.resolve().parents or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise SystemExit(f"offline reference changed: {name}")
    for name, digest in bundle["sha256"].items():
        path = args.bundle / name
        if args.bundle.resolve() not in path.resolve().parents or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise SystemExit(f"frozen bundle changed: {name}")
    for profile in bundle["profiles"]:
        validate(args.bundle / profile)
    transport = WorkerTransport()
    transport.call("selfcheck", timeout=20)
    directory = ROOT / "analysis/acceptance" / str(time.time_ns())
    directory.mkdir(parents=True, exist_ok=True)
    print("Offline checks passed. Waiting for stock console...", flush=True)
    print("Reports:", directory, flush=True)
    results = []
    error = None
    try:
        wait_stock(transport, time, args.wait)
        for profile in bundle["profiles"]:
            print("Testing profile:", profile, flush=True)
            result = run_profile(args.bundle / profile, args.bundle / "shared", transport, time, directory / profile)
            results.append(result)
            print(json.dumps(result, indent=2), flush=True)
            if not result["passed"]:
                break
    except (TransportError, ValueError, OSError) as failure:
        error = str(failure)
    report = {"passed": len(results) == len(bundle["profiles"]) and all(r["passed"] for r in results),
              "results": results, "error": error}
    (directory / "suite.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Reports:", directory)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
