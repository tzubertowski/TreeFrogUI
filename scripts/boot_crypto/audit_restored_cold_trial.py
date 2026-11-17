"""Revalidate a saved NOR-boot trial and emit a bounded independent evidence receipt."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import runpy
import struct
import sys

from codec import decrypt, recover_key
from loader_fs_probe import RESTORE_MAGIC
from run_restored_cold_trial import STOCK

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/kernel_lab"))
from trace_format import decode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trial", type=Path)
    args = parser.parse_args()
    trial = json.loads(args.trial.read_text())
    folder = Path(trial["candidate_folder"])
    manifest = json.loads((folder / "manifest.json").read_text())
    encrypted = (folder / "advapi32.dll.encrypted.NOT_DEPLOYED").read_bytes()
    assert hashlib.sha256(encrypted).hexdigest() == manifest["sha256"] == trial["image_sha256"]
    frozen = Path(manifest.get("source_profile", ROOT / "payload/kernel_ready/boot"))
    source = json.loads((frozen / "manifest.json").read_text())
    key = recover_key((ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes())
    raw = gzip.decompress(decrypt(encrypted, key)[64:])
    kernel = (frozen / "vmlinux.bin").read_bytes()
    offset = int(source["load"], 0) - 0x80000000
    assert raw[offset:offset + len(kernel)] == kernel
    assert hashlib.sha256(kernel).hexdigest() == source["sha256"]["vmlinux.bin"] == manifest["source_kernel_sha256"]
    dtb = (frozen / "r36-lab.dtb").read_bytes()
    dtb_offset = int(manifest["inline_dtb"], 0) - 0x80000000
    assert raw[dtb_offset:dtb_offset + len(dtb)] == dtb
    assert hashlib.sha256(dtb).hexdigest() == manifest["source_dtb_sha256"]
    trace_raw = args.trial.with_suffix(".trace.bin").read_bytes()
    trace, log = decode(trace_raw)
    assert trace["stage"] == 6 and trace["session_tag"] == trial["session_tag"]
    assert trace["entry"] == source["entry"] and trace["fw_arg0"] == "0xfffffffe"
    assert trace["fw_arg1"] == trace["fdt"] == manifest["inline_dtb"]
    stamp_raw = args.trial.with_suffix(".restore.bin").read_bytes()
    stamp = struct.unpack("<16I", stamp_raw)
    spec = manifest["copy_spec"]
    assert stamp[:8] == (RESTORE_MAGIC, 1, int(trial["session_tag"], 0), 1,
                          spec["bytes"], spec["crc32"], spec["crc32"], 6)
    runpy.run_path(str(ROOT / "payload/kernel_ready/START.py"), run_name="cold_saved_audit")
    proof_raw = args.trial.with_suffix(".proof.txt").read_bytes()
    proof = sys.modules["acceptance"].proof_result(proof_raw, source, trial["run_id"])
    assert trial["boot_requests"] == 1 and trial["cold_boot_verified"] and trial["native_restore_verified"]
    assert trial["stock_restored"] and not trial["active"] and not trial["host_cleanup_wrote_boot_file"]
    assert trial["stock_already_restored_before_host_cleanup"]
    assert trial["stock_hashes_before_cleanup"] == STOCK
    evidence = {name: hashlib.sha256(data).hexdigest() for name, data in
                [("trace", trace_raw), ("restore_receipt", stamp_raw), ("proof", proof_raw)]}
    result = {"audited_utc": datetime.now(timezone.utc).isoformat(), "nor_boot_verified": True,
              "reset_method": "hardware watchdog reset, NOR SD-image boot", "power_cycle_verified": False,
              "normal_path_requires_stock_Linux_runtime": False, "run_id": trial["run_id"],
              "session_tag": trial["session_tag"], "image_sha256": manifest["sha256"],
              "kernel_sha256": manifest["source_kernel_sha256"], "proof": proof,
              "native_restore_before_kernel_verified": True, "host_restore_required": False,
              "stock_return_verified": True, "evidence_sha256": evidence,
              "trial": str(args.trial), "scope": "minimal Linux7/PID1/SD/timer; no cold module or TreeFrogUI/peripheral acceptance"}
    output = args.trial.with_name(args.trial.stem + "_VERIFIED.json")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
