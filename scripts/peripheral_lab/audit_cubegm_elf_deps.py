"""Audit ELF dependencies (PT_INTERP, DT_NEEDED, GLIBC/GLIBCXX versions) in the /cubegm backup."""
import argparse
import json
from pathlib import Path
from typing import Any

from elftools.elf.dynamic import DynamicSection
from elftools.elf.elffile import ELFFile
from elftools.elf.gnuversions import GNUVerNeedSection


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BACKUP = ROOT / "analysis/boot_crypto/backups/20261116T161658Z_cubegm"
DEFAULT_ROOTFS = ROOT / "analysis/rootfs_card2"


def inspect_elf(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("rb") as fh:
            if fh.read(4) != b"\x7fELF":
                return None
            fh.seek(0)
            elf = ELFFile(fh)
            interp = None
            for seg in elf.iter_segments():
                if seg["p_type"] == "PT_INTERP":
                    interp = seg.get_interp_name()
                    break

            needed: list[str] = []
            rpath: list[str] = []
            runpath: list[str] = []
            soname: str | None = None
            for sec in elf.iter_sections():
                if isinstance(sec, DynamicSection):
                    for tag in sec.iter_tags():
                        if tag.entry.d_tag == "DT_NEEDED":
                            needed.append(tag.needed)
                        elif tag.entry.d_tag == "DT_RPATH":
                            rpath.extend(tag.rpath.split(":"))
                        elif tag.entry.d_tag == "DT_RUNPATH":
                            runpath.extend(tag.runpath.split(":"))
                        elif tag.entry.d_tag == "DT_SONAME":
                            soname = tag.soname

            ver_needs: dict[str, list[str]] = {}
            for sec in elf.iter_sections():
                if isinstance(sec, GNUVerNeedSection):
                    for verneed, aux in sec.iter_versions():
                        ver_needs[verneed.name] = sorted({a.name for a in aux})

            return {
                "size": path.stat().st_size,
                "e_type": elf["e_type"],
                "e_machine": elf["e_machine"],
                "class": elf.elfclass,
                "little_endian": elf.little_endian,
                "interp": interp,
                "soname": soname,
                "needed": needed,
                "rpath": [x for x in rpath if x],
                "runpath": [x for x in runpath if x],
                "ver_needs": ver_needs,
            }
    except Exception:
        return None


def collect_available_libs(*roots: Path) -> dict[str, list[str]]:
    libs: dict[str, list[str]] = {}
    for base in roots:
        if not base.is_dir():
            continue
        for p in base.rglob("*.so*"):
            if p.is_file():
                libs.setdefault(p.name, []).append(p.relative_to(base).as_posix())
    return libs


def audit_cubegm(backup_dir: Path, rootfs_dir: Path) -> dict[str, Any]:
    targets: list[Path] = []
    for rel in ("picoarch", "tfmtp", "r36_keepawake.sh"):
        p = backup_dir / rel
        if p.is_file():
            targets.append(p)
    for sub in ("usr/bin", "cores"):
        d = backup_dir / sub
        if d.is_dir():
            for p in sorted(d.iterdir()):
                if p.is_file():
                    targets.append(p)
    for p in sorted(backup_dir.iterdir()):
        if p.is_file() and (p.suffix == ".so" or ".so." in p.name):
            targets.append(p)

    seen: set[Path] = set()
    binaries: dict[str, dict[str, Any]] = {}
    all_needed: set[str] = set()
    for p in targets:
        if p in seen:
            continue
        seen.add(p)
        info = inspect_elf(p)
        if info is not None:
            rel = p.relative_to(backup_dir).as_posix()
            binaries[rel] = info
            all_needed.update(info["needed"])

    cubegm_libs = collect_available_libs(backup_dir / "lib", backup_dir / "usr/lib", backup_dir)
    rootfs_libs = collect_available_libs(rootfs_dir)

    needed_resolution: dict[str, dict[str, Any]] = {}
    missing_from_both: list[str] = []
    for lib in sorted(all_needed):
        in_cubegm = cubegm_libs.get(lib, [])
        in_rootfs = rootfs_libs.get(lib, [])
        needed_resolution[lib] = {
            "in_cubegm": in_cubegm,
            "in_rootfs_snapshot": in_rootfs,
        }
        if not in_cubegm and not in_rootfs:
            missing_from_both.append(lib)

    return {
        "backup_dir": backup_dir.relative_to(ROOT).as_posix() if backup_dir.is_relative_to(ROOT) else str(backup_dir),
        "elf_count": len(binaries),
        "unique_needed": sorted(all_needed),
        "missing_from_local_snapshots": missing_from_both,
        "needed_resolution": needed_resolution,
        "binaries": binaries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, default=DEFAULT_BACKUP)
    parser.add_argument("--rootfs", type=Path, default=DEFAULT_ROOTFS)
    parser.add_argument("--out", type=Path, default=ROOT / "analysis/driver_port/CUBEGM_ELF_DEPS_v1.json")
    args = parser.parse_args()

    report = audit_cubegm(args.backup, args.rootfs)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Audited {report['elf_count']} ELFs; unique NEEDED={len(report['unique_needed'])}; missing={report['missing_from_local_snapshots']}")


if __name__ == "__main__":
    main()
