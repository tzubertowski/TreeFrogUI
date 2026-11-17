"""Create a separate silent-audio-only candidate from a verified disabled build.

No device connection. Reject any missing/mismatched PCM UAPI or active other
client. Files in the source profile are never edited.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/boot_crypto"))
from capture_dtb import patch_property
from preflight import properties
from audio_validation import validate_audio_abi


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error("output must be new with existing parent")
    manifest = json.loads((args.source / "manifest.json").read_text())
    for name, expected in manifest["sha256"].items():
        if Path(name).name != name or hashlib.sha256((args.source / name).read_bytes()).hexdigest() != expected:
            raise ValueError("source artifact hash mismatch")
    abi = validate_audio_abi(args.source / "init.elf", args.source / "r36_hc16xx_i2s.ko")
    dtb = (args.source / "r36-lab.dtb").read_bytes()
    nodes = properties(dtb)
    for node in ("/sound@1880a000", "/display-controller@1883a000", "/amprpc-poll@18800800"):
        if nodes[node]["status"] != b"disabled\0":
            raise ValueError("source clients must be disabled")
    if b"--" in nodes["/chosen"]["bootargs"]:
        raise ValueError("source has unexpected userspace arguments")
    dtb = patch_property(dtb, "/sound@1880a000", "status", b"okay\0")
    shutil.copytree(args.source, args.out)
    (args.out / "r36-lab.dtb").write_bytes(dtb)
    manifest.update(profile="audio-silent-dma-probe", extra_device_files=["r36_hc16xx_i2s.ko"],
                    hardware_boot_verified=False, ram_handoff_supported=False)
    manifest["sha256"]["r36-lab.dtb"] = hashlib.sha256(dtb).hexdigest()
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # Replace the copied disabled-source receipt, rather than letting it certify
    # the DT we just changed. The candidate is software-verified only.
    receipt = {"build_passed": True, "source": str(args.source), "audio_ABI": abi,
               "audio_node_enabled": True, "display_node_enabled": False,
               "probe": "silent real ALSA PCM/DMA/IRQ/STOP; no tone or amplifier write",
               "hardware_verified": False, "deployed": False}
    (args.out / "build_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
