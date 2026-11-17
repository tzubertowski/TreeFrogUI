"""Validate and run a read-only MIPS ABI/framebuffer/input inventory on stock."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--avp-inspect", action="store_true")
    args = parser.parse_args()
    name = "r36-avp-probe" if args.avp_inspect else "r36-runtime-probe"
    binary = ROOT / "analysis/driver_port" / name
    with binary.open("rb") as handle:
        elf = ELFFile(handle)
        assert elf.elfclass == 32 and elf.little_endian and elf["e_machine"] == "EM_MIPS"
        assert elf["e_type"] == "ET_EXEC"
        assert not any(segment["p_type"] == "PT_INTERP" for segment in elf.iter_segments())
        abi = elf.get_section_by_name(".MIPS.abiflags").data()
        assert abi[7] == 3, "must use software floating point"
        flags = elf["e_flags"]
    runpy.run_path(str(ROOT / "payload/kernel_ready/START.py"), run_name="peripheral_runtime_inventory")
    transport = sys.modules["acceptance"].WorkerTransport()
    code, identity = transport.run("uname -a", timeout=12)
    assert code == 0 and b"4.4.186-release #23" in identity
    transport.put(binary, "/cubegm/" + name)
    code, check = transport.run("md5sum /mnt/sdcard/cubegm/" + name, timeout=12)
    assert code == 0 and hashlib.md5(binary.read_bytes()).hexdigest().encode() in check
    code, raw = transport.run("/mnt/sdcard/cubegm/" + name + (" --inspect" if args.avp_inspect else ""), timeout=25)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = ROOT / "analysis/driver_port" / ("runtime_" + stamp)
    folder.mkdir()
    (folder / "inventory.txt").write_bytes(raw)
    end = b"R36 AVP PROBE END" if args.avp_inspect else b"R36 PERIPHERAL INVENTORY END"
    result = {"captured_utc": stamp, "read_only_device_IO": True, "kernel": identity.decode().strip(), "probe": name,
              "probe_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
              "elf_flags": hex(flags), "soft_float": True, "static_ELF": True,
              "exit_code": code, "complete": code == 0 and end in raw,
              "bytes": len(raw), "inventory": str(folder / "inventory.txt")}
    (folder / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    assert result["complete"]


if __name__ == "__main__":
    main()
