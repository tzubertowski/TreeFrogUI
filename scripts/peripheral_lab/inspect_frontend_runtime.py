"""Resolve unchanged frontend/core ELF dependencies using saved local userland.

Only reads files. Does not execute UI, change SD or claim device compatibility.
"""
import argparse
import hashlib
import json
from pathlib import Path

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]


def details(path):
    with path.open("rb") as handle:
        elf = ELFFile(handle)
        dynamic = elf.get_section_by_name(".dynamic")
        needed = [] if dynamic is None else [tag.needed for tag in dynamic.iter_tags() if tag.entry.d_tag == "DT_NEEDED"]
        versions = elf.get_section_by_name(".gnu.version_r")
        required = {} if versions is None else {v.name: [item.name for item in aux] for v, aux in versions.iter_versions()}
        return {"path": str(path.relative_to(ROOT)), "machine": elf["e_machine"], "bits": elf.elfclass,
                "little_endian": elf.little_endian, "needed": needed, "required_versions": required,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output must be new")
    card = ROOT / "treefrog/extracted/release/cubegm"
    roots = [ROOT / "analysis/rootfs_card2/lib", ROOT / "analysis/rootfs_card2/usr/lib", card / "lib",
             ROOT / "analysis/card2_files/sdcard_cubegm/lib"]
    pending = [card / "picoarch", card / "cores/frogui_libretro.so",
               ROOT / "analysis/driver_port/driver_r36_drm_video_v2.so"]
    visited, missing, records = set(), set(), []
    while pending:
        path = pending.pop(0)
        if path in visited:
            continue
        visited.add(path)
        if not path.is_file():
            missing.add(str(path.relative_to(ROOT))); continue
        item = details(path)
        records.append(item)
        for name in item["needed"]:
            match = next((p / name for p in roots if (p / name).is_file()), None)
            if match is None:
                missing.add(name)
            else:
                pending.append(match)
    report = {"scope": "read-only saved userspace dependency resolution, not actual console filesystem or UI execution",
              "all_needed_files_found": not missing, "missing": sorted(missing), "ELFs": records,
              "hardware_verified": False, "ui_started": False}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"ELFs": len(records), "missing": sorted(missing), "ui_started": False}, indent=2))


if __name__ == "__main__":
    main()
