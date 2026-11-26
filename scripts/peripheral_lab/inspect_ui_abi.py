"""Inventory the existing UI's ELF ABI without loading or modifying its binaries."""
import hashlib
import json
from pathlib import Path
import re

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]


def inspect(path):
    raw = path.read_bytes()
    with path.open("rb") as handle:
        elf = ELFFile(handle)
        dynamic = elf.get_section_by_name(".dynamic")
        abi = elf.get_section_by_name(".MIPS.abiflags")
        needed = [tag.needed for tag in dynamic.iter_tags() if tag.entry.d_tag == "DT_NEEDED"] if dynamic else []
        symbols = elf.get_section_by_name(".dynsym")
        defined, imports = [], []
        if symbols:
            for symbol in symbols.iter_symbols():
                if not symbol.name: continue
                if symbol["st_shndx"] == "SHN_UNDEF":
                    imports.append(symbol.name)
                elif symbol["st_info"]["bind"] in ("STB_GLOBAL", "STB_WEAK"):
                    defined.append({"name": symbol.name, "type": symbol["st_info"]["type"],
                                    "address": hex(symbol["st_value"]), "bytes": symbol["st_size"]})
        strings = []
        for match in re.finditer(rb"[ -~]{5,}", raw):
            text = match.group().decode("ascii")
            if re.search(r"/dev/|/proc/|/sys/|driver_.*\.so|sndC|hcge|hcfb|/SYSV|EVIOC|FBIO|syscore|amprpc", text):
                strings.append(text)
        return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                "architecture": elf["e_machine"], "class": elf.elfclass,
                "needed": needed, "exports": defined, "imports": sorted(set(imports)),
                "hardware_strings": sorted(set(strings)), "has_dwarf": elf.has_dwarf_info(strict=True),
                "fp_abi": abi.data()[7] if abi else None}


def main():
    base = ROOT / "treefrog/extracted/release/cubegm"
    names = ["picoarch", "driver_gb350.so", "tfshim_gb350.so", "cores/frogui_libretro.so"]
    report = {"binaries_modified": False, "scope": "static user ABI inventory; signatures and Linux7 support require implementation/verification",
              "binaries": [inspect(base / name) for name in names if (base / name).is_file()]}
    output = ROOT / "analysis/driver_port/UI_ABI.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    for binary in report["binaries"]:
        print(Path(binary["path"]).name, "needed=", binary["needed"], "dwarf=", binary["has_dwarf"])
        if "driver_" in binary["path"]:
            print("exports:", ", ".join(item["name"] for item in binary["exports"]))
            print("hardware:", binary["hardware_strings"])


if __name__ == "__main__":
    main()
