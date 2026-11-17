"""Collect and validate diagnostic kernel boot proof after returning to stock."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "release/upstream-TreeFrogUI/apps/usb_mode/pc"))
import r36


def validate_proof(proof, raw):
    lines = proof.decode("ascii").splitlines()
    if not lines or lines[0] != "R36 OWN KERNEL USERSPACE REACHED":
        raise ValueError("missing proof header")
    fields = dict(line.split("=", 1) for line in lines[1:] if "=" in line)
    if fields.get("sysname") != "Linux" or fields.get("pid") != "1" or fields.get("machine") != "mips":
        raise ValueError("proof does not describe Linux MIPS PID 1")
    release = fields.get("release", "")
    version = fields.get("version", "")
    if not release.endswith("-r36lab") or not version:
        raise ValueError("unexpected release or absent build version")
    if ("Linux version " + release + " ").encode() not in raw or version.encode() not in raw:
        raise ValueError("proof release/build version does not match the local image")
    return fields


def main():
    out = ROOT / "payload/kernel_lab"
    manifest = json.loads((out / "manifest.json").read_text())
    raw = (out / "vmlinux.bin").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["sha256"]["vmlinux.bin"]:
        raise ValueError("local image no longer matches build manifest")
    device = r36.R36()
    proof_path = ROOT / "analysis/kernel_lab_boot_proof.txt"
    try:
        device.get("/cubegm/r36-own-kernel-proof.txt", str(proof_path))
        code, status = device.run(
            "uname -a; cat /proc/uptime; "
            "md5sum /mnt/sdcard/cubegm/r36-vmlinux.bin /mnt/sdcard/cubegm/r36-lab.dtb "
            "/mnt/sdcard/cubegm/vmlinux.uImage /mnt/sdcard/cubegm/avp.uImage /mnt/sdcard/cubegm/dtb.bin; "
            "sh /mnt/sdcard/cubegm/r36_keepawake.sh status; "
            "cat /tmp/r36_keepawake.paused")
        if code:
            raise RuntimeError(f"remote status command failed: {code}")
    finally:
        device.close()
    (ROOT / "analysis/kernel_lab_postboot.txt").write_bytes(status)
    proof = proof_path.read_bytes()
    fields = validate_proof(proof, raw)
    remote_hashes = {path.decode(): digest.decode() for digest, path in
                     re.findall(rb"^([0-9a-f]{32})\s+(/\S+)", status, re.M)}
    for local, remote in [("vmlinux.bin", "r36-vmlinux.bin"), ("r36-lab.dtb", "r36-lab.dtb")]:
        if remote_hashes.get("/mnt/sdcard/cubegm/" + remote) != hashlib.md5((out / local).read_bytes()).hexdigest():
            raise ValueError(f"remote {remote} no longer matches this build")
    expected_stock = {
        "vmlinux.uImage": "f994b5e32dc90c5eec7e4bd965bff8fe",
        "avp.uImage": "36cf812151712a8a1ec01911ac03ab74",
        "dtb.bin": "9492f590fc2db86694d3fdc52a25c3e4",
    }
    for name, digest in expected_stock.items():
        if remote_hashes.get("/mnt/sdcard/cubegm/" + name) != digest:
            raise ValueError(f"stock file changed: {name}")
    result = {
        "hardware_boot_verified": True,
        "method": "RAM-only warm handoff from stock Linux, followed by physical restart",
        "userspace_proof": fields,
        "proof_sha256": hashlib.sha256(proof).hexdigest(),
        "image_sha256": manifest["sha256"]["vmlinux.bin"],
        "dtb_sha256": manifest["sha256"]["r36-lab.dtb"],
        "stock_boot_files_unchanged": True,
        "postboot_stock_uname": status.decode("utf-8", "replace").splitlines()[0],
    }
    (ROOT / "analysis/kernel_lab_boot_result.json").write_text(json.dumps(result, indent=2) + "\n")
    manifest["hardware_boot_verified"] = True
    manifest["hardware_boot_evidence"] = "analysis/kernel_lab_boot_result.json"
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
