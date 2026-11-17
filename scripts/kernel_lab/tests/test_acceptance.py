import base64
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys
import subprocess

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acceptance import (INSPECT, STOCK_FILES, TransportError, WorkerTransport, driver_result,
                        proof_result, run_profile, wait_stock)
from trace_format import CAPACITY, MAGIC, SIZE, VERSION, decode


class Clock:
    def __init__(self): self.now = 0.0
    def monotonic(self): return self.now
    def sleep(self, seconds): self.now += seconds


class FakeConsole:
    def __init__(self, clock, manifest, fault=None):
        self.clock, self.manifest, self.fault = clock, manifest, fault
        self.files, self.commands = {}, []
        self.booted = False
        self.nonce = None
        self.gone_until = 0
        self.first_post = True

    def put(self, local, remote):
        self.files["/mnt/sdcard" + remote] = Path(local).read_bytes()

    def run(self, command, timeout=20):
        self.commands.append(command)
        if command == INSPECT:
            if self.clock.now < self.gone_until or self.fault == "never_returns" and self.booted:
                self.clock.sleep(min(timeout, 1))
                raise TransportError("device unavailable")
            if self.booted and self.fault == "slow_return" and self.first_post:
                self.first_post = False
                self.clock.sleep(min(timeout, 1))
                raise TransportError("WPD transient")
            uname = "Linux buildroot 4.4.186-release #23 PREEMPT Tue Jan 27 16:21:59 CST 2026 mips GNU/Linux"
            if self.fault == "wrong_firmware": uname = "Linux other 5.0 mips"
            uptime = 20 if self.booted else 1000
            return 0, f"{uname}\n{uptime}.00 0.00\nR36_INSPECT_END\n".encode()
        if command.startswith("md5sum "):
            import hashlib
            result = []
            for path in command.split()[1:]:
                digest = STOCK_FILES.get(path.rsplit("/", 1)[-1])
                if digest is None: digest = hashlib.md5(self.files[path]).hexdigest()
                if self.fault == "corrupt_upload" and path.endswith("r36-vmlinux.bin"): digest = "0" * 32
                if self.fault == "stock_changed" and path.endswith("vmlinux.uImage"): digest = "0" * 32
                result.append(f"{digest}  {path}\n")
            return 0, "".join(result).encode()
        if command.startswith("printf "):
            self.nonce = re.search(r"\b([0-9a-f]{32})\b", command).group(1)
            return 0, b""
        if command.startswith("insmod "):
            return (2, b"prepare failed") if self.fault == "prepare_fails" else (0, b"prepared\n")
        if command.endswith("boot-detached"):
            self.booted = True
            self.gone_until = self.clock.now + 33
            if self.fault == "disconnect_during_handoff": raise TransportError("USB disappeared before reply")
            return 0, b"Detached handoff pid=123\n"
        if "mdump " in command:
            crc = int(self.manifest["relocation_crc32"], 16)
            if self.fault == "bad_destination_crc": crc ^= 1
            words = [MAGIC, 0, CAPACITY, VERSION, 6, int(self.manifest["entry"], 0), 0, 0,
                     187500, 30, 123, 100, 0xFFFFFFFE, 0x82E00000, 0x82E00000, crc]
            return 0, struct.pack("<16I", *words) + bytes(SIZE - 64)
        if command.startswith("cat /mnt/sdcard/cubegm/"):
            path = command.rsplit("/", 1)[-1]
            nonce = "stale" if self.fault == "stale_proof" else self.nonce
            common = f"run_id={nonce}\nrelease={self.manifest['release']}\nversion={self.manifest['build_version']}\n"
            if path == "r36-own-kernel-proof.txt":
                return 0, ("R36 OWN KERNEL USERSPACE REACHED\n" + common + "sysname=Linux\nmachine=mips\npid=1\n").encode()
            if path == "r36-driver-test.txt":
                unload = "-1" if self.fault == "driver_unload_fails" else "0"
                return 0, ("R36 DRIVER TEST\n" + common +
                           f"load_rc=0\nparameter_ok=1\nunload_rc={unload}\nsysfs_removed=1\nresult=PASS\n").encode()
            return 0, (f"run_id={nonce}\nMemTotal: 40000 kB\n").encode()
        return 0, b""


@pytest.fixture
def candidate(tmp_path):
    out, shared = tmp_path / "candidate", tmp_path / "shared"
    out.mkdir(); shared.mkdir()
    manifest = {"profile": "driver", "release": "7.2.0-rc5-r36lab", "build_version": "#99 test build",
                "entry": "0x80500000", "sha256": {"vmlinux.bin": "example"},
                "diagnostic_watchdog": {"timeout_seconds": 30}, "relocation_crc32": "12345678"}
    (out / "manifest.json").write_text(json.dumps(manifest))
    for name in ["r36boot.ko", "r36bootctl", "vmlinux.bin", "r36-lab.dtb", "r36hello.ko", "r36-wdt-diag"]:
        (out / name).write_bytes((name + " bytes").encode())
    for name in ["mdump", "r36_keepawake.sh"]: (shared / name).write_bytes(name.encode())
    return out, shared, manifest


@pytest.mark.parametrize("fault", [None, "slow_return", "disconnect_during_handoff"])
def test_success_and_transient_disconnect(candidate, tmp_path, fault):
    out, shared, manifest = candidate
    clock = Clock(); console = FakeConsole(clock, manifest, fault)
    result = run_profile(out, shared, console, clock, tmp_path / "report", stock_wait=12)
    assert result["passed"] and result["reset_observed"]
    assert result["proof"]["run_id"] == console.nonce
    assert len([c for c in console.commands if c.endswith("boot-detached")]) == 1


@pytest.mark.parametrize("fault", ["corrupt_upload", "stock_changed", "wrong_firmware", "prepare_fails"])
def test_pre_handoff_failure_never_boots(candidate, tmp_path, fault):
    out, shared, manifest = candidate
    console = FakeConsole(Clock(), manifest, fault)
    result = run_profile(out, shared, console, console.clock, tmp_path / "report", stock_wait=6)
    assert not result["passed"] and not result["handoff_requested"]
    assert not console.booted
    assert (tmp_path / "report/result.json").is_file()


@pytest.mark.parametrize("fault", ["never_returns", "stale_proof", "bad_destination_crc", "driver_unload_fails"])
def test_post_handoff_failure_is_not_false_success(candidate, tmp_path, fault):
    out, shared, manifest = candidate
    console = FakeConsole(Clock(), manifest, fault)
    result = run_profile(out, shared, console, console.clock, tmp_path / "report", stock_wait=6)
    assert not result["passed"] and result["handoff_requested"]
    assert console.clock.now <= 45
    assert len([c for c in console.commands if c.endswith("boot-detached")]) == 1


def test_duplicate_proof_keys_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        proof_result(b"R36 OWN KERNEL USERSPACE REACHED\npid=99\npid=1\n", {}, "id")


def test_trace_wrap_and_invalid_header():
    stream = bytes(i % 251 for i in range(CAPACITY + 100))
    ring = bytearray(CAPACITY)
    for i, byte in enumerate(stream): ring[i % CAPACITY] = byte
    raw = struct.pack("<16I", MAGIC, len(stream), CAPACITY, VERSION, *([0] * 12)) + ring
    _, decoded = decode(raw)
    assert decoded == stream[-CAPACITY:]
    with pytest.raises(ValueError): decode(raw[:-1])
    with pytest.raises(ValueError): decode(b"BAD!" + raw[4:])


def test_stuck_wpd_worker_is_terminated(monkeypatch):
    def expired(*args, **kwargs): raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
    monkeypatch.setattr(subprocess, "run", expired)
    with pytest.raises(TransportError, match="terminated"):
        WorkerTransport().call("selfcheck", timeout=0.1)
