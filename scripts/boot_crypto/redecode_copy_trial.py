"""Recalculate copy verification from a saved trace without rebooting the device."""
import argparse
import json
from pathlib import Path
import sys

from loader_fs_probe import decode_copy_trace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/kernel_lab"))
from trace_format import decode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(args.receipt.read_text())
    manifest = json.loads((args.folder / "manifest.json").read_text())
    assert record["candidate_sha256"] == manifest["sha256"]
    raw = args.receipt.with_suffix(".trace.bin").read_bytes()
    metadata, _ = decode(raw)
    values = decode_copy_trace(raw)
    values["output_hash_after_boot"] = record["native_copy"]["output_hash_after_boot"]
    expected = manifest["copy_spec"]
    passed = (metadata["session_tag"] == manifest["session_tag"] and metadata["stage"] == manifest["trace_stage"] and
              values["read_bytes"] == values["written_bytes"] == expected["bytes"] and
              values["source_crc32"] == values["readback_crc32"] == expected["crc32"] and
              values["phase"] == 6 and values["output_hash_after_boot"].startswith("3510ffdfd039f850345ace1489572659 "))
    if expected["restore_stock"]:
        passed = passed and record.get("stock_already_restored_before_host_cleanup", False) and not record.get("host_cleanup_wrote_boot_file", True)
    record["decoder_correction"] = "Copy fields decoded at source416/readback420/phase424; uncaptured debug areas omitted; recalculated from original saved trace, no additional hardware trial"
    for name in ("globals_before", "last_resolver_path"):
        record.get("loader_fs_probe", {}).pop(name, None)
    record["trace"] = metadata
    record["native_copy"] = values
    record["hardware_verified"] = passed
    args.receipt.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    assert passed


if __name__ == "__main__":
    main()
