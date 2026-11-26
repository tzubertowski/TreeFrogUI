"""Snapshot only build inputs into the owned VM and start one kernel/module build."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import time
import shutil
import argparse

from build_vm import WORK

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--display-source", type=Path)
    parser.add_argument("--audio-source", type=Path, help="compile opt-in audio module; DT stays disabled")
    parser.add_argument("--init", type=Path)
    parser.add_argument("--usb-probe", action="store_true", help="isolated USB0 CDC/PIO build without display/audio/input")
    parser.add_argument("--input-probe", action="store_true", help="include isolated polled key nodes in display build")
    parser.add_argument("--otg-wifi-bt", action="store_true", help="enable USB dual-role OTG, Wi-Fi (802.11) and Bluetooth (btusb) modules")
    parser.add_argument("--full", action="store_true", help="build unified Linux 7.2 profile (display + audio + full input + adc + pwm + otg wifi/bt)")
    args = parser.parse_args()
    if args.input_probe and not (args.display_source or args.full):
        parser.error("--input-probe requires --display-source or --full")
    if args.full and (not args.display_source or not args.audio_source):
        parser.error("--full requires --display-source and --audio-source")
    if args.usb_probe and (args.display_source or args.audio_source or args.input_probe or args.full):
        parser.error("USB diagnostic must be isolated from display/audio/input candidates")
    kind = "full" if args.full else "usb" if args.usb_probe else "display" if args.display_source else "avp"
    init = args.init or ROOT / ("analysis/driver_port/r36-usb-cdc-init-v1" if args.usb_probe else "analysis/driver_port/r36-display-probe" if args.display_source else "analysis/driver_port/r36-avp-probe")
    assert init.is_file()
    if args.display_source:
        provenance = json.loads((args.display_source / "port_source.json").read_text())
        for name, digest in provenance["files_sha256"].items():
            assert hashlib.sha256((args.display_source / name).read_bytes()).hexdigest() == digest
    if args.audio_source:
        provenance = json.loads((args.audio_source / "port_source.json").read_text())
        for name, digest in provenance["files_sha256"].items():
            assert Path(name).name == name
            assert hashlib.sha256((args.audio_source / name).read_bytes()).hexdigest() == digest
    state = json.loads((WORK / "state.json").read_text())
    assert state["ssh_port"] == 22222
    archive = WORK / ("project-build-" + str(int(time.time())) + ".tar.gz")
    sources = []
    previous_log = WORK / "kernel-build.log"
    if previous_log.exists():
        shutil.copy2(previous_log, WORK / ("kernel-build-previous-" + str(int(time.time())) + ".log"))
    with tarfile.open(archive, "w:gz") as output:
        for directory in (ROOT / "scripts/kernel_lab", ROOT / "scripts/peripheral_lab"):
            for path in directory.rglob("*"):
                if path.is_file() and (path.suffix in (".c", ".h", ".S", ".dts", ".py", ".sh") or path.name in ("Makefile", "Kconfig")) and "__pycache__" not in path.parts:
                    output.add(path, arcname=path.relative_to(ROOT).as_posix())
                    sources.append(str(path.relative_to(ROOT)))
        output.add(ROOT / "payload/kernel_ready/boot/kernel.config", arcname="base/kernel.config")
        output.add(init, arcname="init.elf")
        if args.display_source:
            output.add(args.display_source, arcname="display_driver")
        if args.audio_source:
            output.add(args.audio_source, arcname="audio_driver")
    options = ["-i", state["private_key"], "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
               "-o", "UserKnownHostsFile=" + str(WORK / "known_hosts")]
    subprocess.run(["scp", "-P", "22222", *options, archive.relative_to(ROOT).as_posix(), "root@127.0.0.1:/work/project-build.tar.gz"], cwd=ROOT, check=True)
    command = ("if test -f /work/kernel-build.pid && kill -0 $(cat /work/kernel-build.pid) 2>/dev/null; then exit 9; fi; "
               "date -u -s '@" + str(int(time.time())) + "' >/dev/null || exit 10; "
               "mkdir -p /work/project; tar -xzf /work/project-build.tar.gz -C /work/project; rm -f /work/kernel-build.exit; "
               "nohup env R36_BUILD_PROFILE=" + kind + " R36_INPUT_PROBE=" + str(int(args.input_probe)) + " R36_AUDIO_BUILD=" + str(int(bool(args.audio_source))) + " R36_OTG_WIFI_BT=" + str(int(args.otg_wifi_bt)) + " bash /work/project/scripts/peripheral_lab/vm_build_kernel.sh > /work/kernel-build.log 2>&1 < /dev/null & "
               "echo $! > /work/kernel-build.pid; cat /work/kernel-build.pid")
    reply = subprocess.check_output(["ssh", "-p", "22222", *options, "root@127.0.0.1", command])
    record = {"started": True, "kind": kind, "input_probe": args.input_probe, "audio_module_build": bool(args.audio_source), "otg_wifi_bt": args.otg_wifi_bt, "init_sha256": hashlib.sha256(init.read_bytes()).hexdigest(),
              "guest_pid": int(reply.strip()), "archive": str(archive),
              "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "sources": sources,
              "kernel_revision": "da5f1a22ef2ff5c46aa3f750fa10825813970b09", "compiler": "Alpine LLVM20/clang20 + GNU MIPS assembler2.44",
              "host_WSL_modified": False, "hardware_validated": False}
    (WORK / "kernel-build-request.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({key: value for key, value in record.items() if key != "sources"}, indent=2))


if __name__ == "__main__":
    main()
