"""Fetch and verify the owned VM's completed MIPS kernel/module build."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile

from elftools.elf.elffile import ELFFile
from build_vm import WORK

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/kernel_lab"))
sys.path.insert(0, str(ROOT / "scripts/boot_crypto"))
from preflight import cpio_files, properties
from capture_dtb import patch_property


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--module-variant", type=Path)
    args = parser.parse_args()
    for output in [args.out] + ([args.module_variant] if args.module_variant else []):
        if output.exists() or not output.parent.is_dir(): parser.error("output must be new with an existing parent")
    state = json.loads((WORK / "state.json").read_text())
    options = ["-i", state["private_key"], "-o", "BatchMode=yes", "-o", "UserKnownHostsFile=" + str(WORK / "known_hosts")]
    ssh = ["ssh", "-p", "22222", *options, "root@127.0.0.1"]
    status = subprocess.check_output(ssh + ["cat /work/kernel-build.exit"]).strip()
    assert status == b"0", status
    remote_sha = subprocess.check_output(ssh + ["sha256sum /work/kernel-avp-build.tar.gz"]).split()[0].decode()
    archive = WORK / (args.out.name + ".tar.gz")
    subprocess.run(["scp", "-P", "22222", *options, "root@127.0.0.1:/work/kernel-avp-build.tar.gz", archive.relative_to(ROOT).as_posix()], cwd=ROOT, check=True)
    assert sha(archive) == remote_sha
    args.out.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(args.out, filter="data")
    manifest = json.loads((args.out / "manifest.json").read_text())
    for name, digest in manifest["sha256"].items(): assert sha(args.out / name) == digest, name
    module = args.out / "r36_amprpc_poll.ko"
    with module.open("rb") as handle:
        elf = ELFFile(handle)
        assert elf.elfclass == 32 and elf.little_endian and elf["e_machine"] == "EM_MIPS" and elf["e_type"] == "ET_REL"
        info = elf.get_section_by_name(".modinfo").data().split(b"\0")
        vermagic = next(value.split(b"=", 1)[1].decode() for value in info if value.startswith(b"vermagic="))
        assert vermagic.startswith(manifest["release"] + " ") and b"license=GPL" in info
    config = (args.out / "kernel.config").read_text()
    assert "CONFIG_SYSVIPC=y" in config and "CONFIG_MODULES=y" in config
    tree = properties((args.out / "r36-lab.dtb").read_bytes())
    node = "/amprpc-poll@18800800"
    assert tree[node]["status"] == b"disabled\0"
    assert tree[node]["reg"] == struct.pack(">4I", 0x18800800, 0x100, 0x18866800, 0x100)
    manifest["sha256"][module.name] = sha(module)
    manifest.update(hardware_boot_verified=False, ram_handoff_supported=False, build_environment="owned QEMU/WHPX Linux VM",
                    avp_transport_mode="userspace", extra_device_files=[])
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    latest = sha(args.out / "init.elf") == sha(ROOT / "analysis/driver_port/r36-avp-probe")
    record = {"build_passed": True, "archive_sha256": remote_sha, "kernel_release": manifest["release"],
              "kernel_sha256": sha(args.out / "vmlinux.bin"), "module_sha256": sha(module), "module_vermagic": vermagic,
              "SYSVIPC_enabled": True, "default_RPC_node_disabled": True, "init_matches_latest_probe": latest,
              "hardware_verified": False, "deployed": False, "profile": str(args.out)}
    if args.module_variant:
        assert latest, "rebuild with current probe before making a kernel-mode test"
        shutil.copytree(args.out, args.module_variant)
        dtb = (args.out / "r36-lab.dtb").read_bytes()
        dtb = patch_property(dtb, node, "status", b"okay\0")
        args_string = tree["/chosen"]["bootargs"].rstrip(b"\0") + b" -- --kernel-probe\0"
        dtb = patch_property(dtb, "/chosen", "bootargs", args_string)
        (args.module_variant / "r36-lab.dtb").write_bytes(dtb)
        module_manifest = json.loads(json.dumps(manifest))
        module_manifest.update(profile="avp-kernel-module-probe", avp_transport_mode="kernel", extra_device_files=[module.name])
        module_manifest["sha256"]["r36-lab.dtb"] = sha(args.module_variant / "r36-lab.dtb")
        (args.module_variant / "manifest.json").write_text(json.dumps(module_manifest, indent=2) + "\n")
        record["kernel_mode_profile"] = str(args.module_variant)
    (args.out / "build_receipt.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
