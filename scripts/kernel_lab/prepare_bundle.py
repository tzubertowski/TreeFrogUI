"""Build, emulate, fault-test and freeze acceptance artifacts without a console."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
LAB = Path(__file__).resolve().parent
REV = "da5f1a22ef2ff5c46aa3f750fa10825813970b09"


def wslpath(path):
    path = Path(path).resolve()
    return "/mnt/" + path.drive[0].lower() + str(path)[2:].replace("\\", "/")


def run(command, log, *, env=None, timeout=600):
    if Path(log).exists():
        shutil.copy2(log, str(log) + ".previous")
    with Path(log).open("wb") as output:
        completed = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, cwd=ROOT, env=env, timeout=timeout)
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}); inspect {log}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "payload/kernel_ready")
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"Output already exists; preserving it: {output}")
    if output.parent != (ROOT / "payload").resolve():
        raise SystemExit("Output must be a new direct child of this project's payload directory")
    for module in ["elftools", "unicorn", "pytest", "comtypes"]:
        if importlib.util.find_spec(module) is None:
            raise SystemExit(f"Required installed dependency unavailable: {module}")
    stock_source = Path(r"\\wsl$\ubmips\root") / ("linux-hichip-" + REV) / "Makefile"
    if not stock_source.is_file():
        raise SystemExit("Pinned kernel source is unavailable in WSL ubmips")
    staging = args.resume.resolve() if args.resume else output.with_name(output.name + ".work-" + str(time.time_ns()))
    if staging.parent != output.parent or not staging.name.startswith(output.name + ".work-"):
        raise SystemExit("Resume directory must be this bundle's preparation directory")
    staging.mkdir(exist_ok=bool(args.resume))
    env = dict(os.environ, R36_PROJECT_ROOT=str(ROOT), R36_BOOT_TIMEOUT="30")
    print("Offline preparation only; no console will be opened.", flush=True)
    for profile in ["boot", "driver"]:
        candidate = staging / profile
        candidate.mkdir(exist_ok=True)
        print("Building", profile, flush=True)
        run(["wsl", "-d", "ubmips", "--", "env", "LAB_PROFILE=" + profile,
             "OUT=" + wslpath(candidate), "bash", wslpath(LAB / "build_kernel.sh")],
            candidate / "build.log", env=env)
        loader_env = dict(env, R36_KERNEL_OUT=str(candidate))
        run([sys.executable, str(LAB / "build_loader.py")], candidate / "loader.log", env=loader_env)
        print("Emulating actual MIPS boot:", profile, flush=True)
        run([sys.executable, str(LAB / "emulate_boot.py"), str(candidate)],
            candidate / "emulate.log", env=env, timeout=240)
        run([sys.executable, str(LAB / "preflight.py"), str(candidate)],
            candidate / "preflight.log", env=env, timeout=60)
    print("Running fault-injection tests", flush=True)
    with tempfile.TemporaryDirectory(prefix="kernel-offline-tests-", dir=ROOT / "payload") as scratch:
        test_env = dict(env, R36_TEST_CANDIDATE=str(staging / "boot"))
        run([sys.executable, "-m", "pytest", "-q", str(LAB / "tests"),
             "--basetemp", str(Path(scratch) / "pytest"), "--junitxml", str(staging / "offline-tests.xml")],
            staging / "offline-tests.log", env=test_env, timeout=180)
    from acceptance import WorkerTransport
    check = WorkerTransport().call("selfcheck", timeout=20)
    if not check.get("client_imported"):
        raise RuntimeError("Windows WPD client dependency check failed")
    shared = staging / "shared"
    shared.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "scripts/r36_keepawake.sh", shared / "r36_keepawake.sh")
    shutil.copy2(ROOT / "payload/mdump", shared / "mdump")
    from preflight import check_elf
    check_elf(shared / "mdump", "ET_EXEC")
    tools = staging / "tools"
    tools.mkdir(exist_ok=True)
    for name in ["acceptance.py", "device_worker.py", "preflight.py", "trace_format.py"]:
        shutil.copy2(LAB / name, tools / name)
    shutil.copy2(LAB / "start_ready.py", staging / "START.py")
    shutil.copy2(LAB / "start_ready.ps1", staging / "START.ps1")
    shutil.copy2(LAB / "READY_README.ru.md", staging / "README.ru.md")
    digests = {p.relative_to(staging).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(staging.rglob("*")) if p.is_file()}
    reference_names = ["analysis/kmem/kernel_80000000.bin",
                       "analysis/card2_files/kdump/proc_kallsyms.txt",
                       "analysis/rootfs_card2/lib/modules/4.4.186-release/extra/dsc.ko",
                       "release/upstream-TreeFrogUI/apps/usb_mode/pc/r36.py"]
    references = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in reference_names}
    bundle = {"version": 1, "profiles": ["boot", "driver"], "sha256": digests,
              "references_sha256": references}
    manifest = (json.dumps(bundle, indent=2) + "\n").encode()
    (staging / "bundle.json").write_bytes(manifest)
    suites = ET.parse(staging / "offline-tests.xml").getroot()
    test_count = sum(int(s.get("tests", "0")) for s in suites.iter("testsuite"))
    ready = {"offline_passed": True, "offline_tests": test_count,
             "emulated_cases": 6, "wpd_client_selfcheck": "PASS",
             "bundle_manifest_sha256": hashlib.sha256(manifest).hexdigest(),
             "hardware_acceptance": "pending for these exact candidates",
             "source_revision": REV}
    (staging / "READY.json").write_text(json.dumps(ready, indent=2) + "\n")
    staging.rename(output)
    print(json.dumps({"bundle": str(output), **ready}, indent=2))


if __name__ == "__main__":
    main()
