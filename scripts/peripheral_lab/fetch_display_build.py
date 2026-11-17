"""Fetch and validate a completed display build; never connect to the console."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/kernel_lab"))
sys.path.insert(0, str(ROOT / "scripts/boot_crypto"))
from preflight import cpio_files, properties
from capture_dtb import patch_property

DISPLAY_NODE = "/display-controller@1883a000"
REQUIRED = {
    "vmlinux.elf", "vmlinux.bin", "kernel.config", "System.map", "r36-lab.dtb",
    "init.elf", "initramfs.cpio.gz", "r36_hc16xx_drm.ko", "r36_amprpc_poll.ko",
    "r36hello.ko", "manifest.json", "port_source.json",
}
CONFIG = ("CPU_LITTLE_ENDIAN", "PAGE_SIZE_4KB", "SYSVIPC", "MODULES", "MODULE_UNLOAD",
          "DRM", "DRM_KMS_HELPER", "DRM_GEM_DMA_HELPER", "DRM_R36_HC16XX_DEPS",
          "CEVT_R4K", "CSRC_R4K", "MMC_BLOCK", "VFAT_FS")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_archive(archive, *, audio=False):
    """Only the known, flat build output is accepted; no links or extra code."""
    required = REQUIRED | ({"r36_hc16xx_i2s.ko"} if audio else set())
    names = set()
    for member in archive.getmembers():
        if member.name == "." and member.isdir():
            continue
        name = member.name.removeprefix("./")
        if not member.isfile() or name not in required or name in names:
            raise ValueError(f"unexpected archive member: {member.name}")
        if member.size > 32 * 1024 * 1024:
            raise ValueError(f"oversized archive member: {member.name}")
        names.add(name)
    if names != required:
        raise ValueError(f"missing build files: {sorted(required - names)}")


def abi(path):
    with Path(path).open("rb") as handle:
        elf = ELFFile(handle)
        if elf.elfclass != 32 or not elf.little_endian or elf["e_machine"] != "EM_MIPS":
            raise ValueError(f"not a little-endian MIPS32 ELF: {path}")
        section = elf.get_section_by_name(".r36abi")
        if section is None or section["sh_size"] != 16 * 4:
            raise ValueError("missing/incorrect display ABI section")
        words = struct.unpack("<16I", section.data())
        if words[:3] != (0x52334441, 1, 4):
            raise ValueError("display ABI header is not the expected 32-bit ABI")
        return words


def validate_display(out, latest_probe, source, *, audio=False):
    out, source = Path(out), Path(source)
    manifest = json.loads((out / "manifest.json").read_text())
    digests = manifest["sha256"]
    for name in REQUIRED - {"manifest.json", "port_source.json"}:
        if digests.get(name) != sha(out / name):
            raise ValueError(f"artifact hash mismatch/missing: {name}")
    if sha(out / "init.elf") != sha(latest_probe):
        raise ValueError("build does not contain the current display probe")
    provenance = json.loads((source / "port_source.json").read_text())
    if (out / "port_source.json").read_bytes() != (source / "port_source.json").read_bytes():
        raise ValueError("display provenance differs from build input")
    for name, digest in provenance["files_sha256"].items():
        if Path(name).name != name or sha(source / name) != digest:
            raise ValueError("display source changed since staging")
    config = (out / "kernel.config").read_text()
    for option in CONFIG:
        if f"CONFIG_{option}=y\n" not in config:
            raise ValueError(f"required display build option missing: {option}")
    if "CONFIG_DRM_FBDEV_EMULATION=y\n" in config:
        raise ValueError("automatic framebuffer client must remain disabled")
    release = manifest["release"]
    if release != "7.2.0-rc5-r36disp":
        raise ValueError("unexpected display kernel release")
    image = (out / "vmlinux.bin").read_bytes()
    with (out / "vmlinux.elf").open("rb") as handle:
        elf = ELFFile(handle)
        loads = [s for s in elf.iter_segments() if s["p_type"] == "PT_LOAD"]
        if len(loads) != 1:
            raise ValueError("kernel needs one load segment")
        segment = loads[0]
        if (segment["p_vaddr"], elf["e_entry"], segment["p_filesz"], segment["p_memsz"]) != (
            int(manifest["load"], 0), int(manifest["entry"], 0), manifest["filesz"], manifest["memsz"]
        ) or segment.data() != image:
            raise ValueError("kernel ELF/flat/manifest mismatch")
    compressed = (out / "initramfs.cpio.gz").read_bytes()
    if compressed not in image or cpio_files(gzip.decompress(compressed)).get("init") != (out / "init.elf").read_bytes():
        raise ValueError("embedded PID1 differs from the verified display probe")
    if ("Linux version " + release + " ").encode() not in image:
        raise ValueError("kernel release absent from image")
    probe_abi = abi(out / "init.elf")
    if abi(out / "r36_hc16xx_drm.ko") != probe_abi:
        raise ValueError("MIPS userspace/kernel DRM ioctl ABI mismatch")
    modules = {}
    exports = {line.split()[-1][len("__ksymtab_"):] for line in (out / "System.map").read_text().splitlines()
               if line.split() and line.split()[-1].startswith("__ksymtab_")}
    module_names = ["r36_hc16xx_drm.ko", "r36_amprpc_poll.ko", "r36hello.ko"]
    if audio:
        module_names.append("r36_hc16xx_i2s.ko")
        if digests.get("r36_hc16xx_i2s.ko") != sha(out / "r36_hc16xx_i2s.ko"):
            raise ValueError("audio module hash mismatch")
        for option in ("SOUND", "SND", "SND_PCM"):
            if f"CONFIG_{option}=y\n" not in config:
                raise ValueError(f"required ALSA option missing: {option}")
    for name in module_names:
        with (out / name).open("rb") as handle:
            elf = ELFFile(handle)
            if elf["e_type"] != "ET_REL" or elf["e_machine"] != "EM_MIPS" or elf.elfclass != 32 or not elf.little_endian:
                raise ValueError(f"incorrect module architecture: {name}")
            info = elf.get_section_by_name(".modinfo").data().split(b"\0")
            vermagic = next(v.split(b"=", 1)[1].decode() for v in info if v.startswith(b"vermagic="))
            if not vermagic.startswith(release + " ") or b"license=GPL" not in info:
                raise ValueError(f"module release/license mismatch: {name}")
            imports = {s.name for s in elf.get_section_by_name(".symtab").iter_symbols()
                       if s.name and s["st_shndx"] == "SHN_UNDEF"}
            if imports - exports:
                raise ValueError(f"module imports are not exported by kernel: {sorted(imports - exports)}")
            modules[name] = {"sha256": sha(out / name), "vermagic": vermagic, "imports_verified": len(imports)}
    nodes = properties((out / "r36-lab.dtb").read_bytes())
    if audio:
        sound = nodes["/sound@1880a000"]
        if sound["status"] != b"disabled\0" or sound["reg"] != struct.pack(">4I", 0x1880A000, 0x1000, 0x18800000, 0x500):
            raise ValueError("native audio must remain disabled with exact board resources")
    display = nodes[DISPLAY_NODE]
    if display["status"] != b"disabled\0" or display["compatible"] != b"r36lab,hc16e310-display\0":
        raise ValueError("base display node must be present and disabled")
    if display["reg"] != struct.pack(">II", 0x1883A000, 0x1000):
        raise ValueError("wrong display register region")
    if "width-mm" in display or "height-mm" in display:
        if any(display.get(key) != struct.pack(">I", 0) for key in ("width-mm", "height-mm")):
            raise ValueError("physical panel dimensions must be explicitly unknown, not guessed")
    if nodes["/amprpc-poll@18800800"]["status"] != b"disabled\0":
        raise ValueError("RPC must remain disabled during display tests")
    if nodes["/memory@0"]["reg"] != struct.pack(">II", 0, 0x02F91E50):
        raise ValueError("unexpected Linux/AVP RAM boundary")
    if not any(p.get("reg") == struct.pack(">II", 0x02F90000, 4096) and "no-map" in p
               for n, p in nodes.items() if n.startswith("/reserved-memory/")):
        raise ValueError("display descriptor reservation missing")
    if b"--display-kms-probe" in nodes["/chosen"]["bootargs"]:
        raise ValueError("passive candidate must not request KMS")
    return {"build_passed": True, "kernel_release": release, "kernel_sha256": sha(out / "vmlinux.bin"),
            "init_sha256": sha(out / "init.elf"), "modules": modules, "DRM_ABI": list(probe_abi),
            "default_display_disabled": True, "RPC_disabled": True,
            "hardware_verified": False, "deployed": False,
            "scope": "ELF, exports, ioctl ABI, embedded PID1, DT and source provenance; no display hardware test"}


def make_kms_variant(source, target):
    source, target = Path(source), Path(target)
    if target.exists():
        raise FileExistsError(target)
    shutil.copytree(source, target)
    dtb = (source / "r36-lab.dtb").read_bytes()
    nodes = properties(dtb)
    if nodes[DISPLAY_NODE]["status"] != b"disabled\0":
        raise ValueError("KMS variant requires passive source")
    dtb = patch_property(dtb, DISPLAY_NODE, "status", b"okay\0")
    bootargs = nodes["/chosen"]["bootargs"].rstrip(b"\0") + b" -- --display-kms-probe\0"
    dtb = patch_property(dtb, "/chosen", "bootargs", bootargs)
    (target / "r36-lab.dtb").write_bytes(dtb)
    manifest = json.loads((source / "manifest.json").read_text())
    manifest.update(profile="display-kms-probe", extra_device_files=["r36_hc16xx_drm.ko"],
                    hardware_boot_verified=False, ram_handoff_supported=False)
    manifest["sha256"]["r36-lab.dtb"] = sha(target / "r36-lab.dtb")
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # A passive receipt must not be mistaken for the modified candidate's receipt.
    receipt = target / "build_receipt.json"
    if receipt.exists():
        receipt.unlink()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT / "payload/display_driver_source_v3")
    parser.add_argument("--probe", type=Path, default=ROOT / "analysis/driver_port/r36-display-probe")
    parser.add_argument("--kms-variant", type=Path)
    parser.add_argument("--audio", action="store_true", help="also validate compiled opt-in ALSA module; never enable it")
    args = parser.parse_args()
    for output in [args.out] + ([args.kms_variant] if args.kms_variant else []):
        if output.exists() or not output.parent.is_dir():
            parser.error("outputs must be new with existing parents")
    from build_vm import WORK
    state = json.loads((WORK / "state.json").read_text())
    options = ["-i", state["private_key"], "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
               "-o", "UserKnownHostsFile=" + str(WORK / "known_hosts")]
    ssh = ["ssh", "-p", "22222", *options, "root@127.0.0.1"]
    status = subprocess.check_output(ssh + ["cat /work/kernel-build.exit"], timeout=20).strip()
    if status != b"0":
        raise RuntimeError(f"build is not successfully complete: {status!r}")
    digest = subprocess.check_output(ssh + ["sha256sum /work/kernel-display-build.tar.gz"], timeout=20).split()[0].decode()
    archive = WORK / (args.out.name + ".tar.gz")
    if archive.exists():
        raise FileExistsError(archive)
    subprocess.run(["scp", "-P", "22222", *options, "root@127.0.0.1:/work/kernel-display-build.tar.gz", str(archive)],
                   check=True, timeout=60)
    if sha(archive) != digest:
        raise ValueError("transferred archive checksum mismatch")
    with tarfile.open(archive) as bundle:
        check_archive(bundle, audio=args.audio)
        args.out.mkdir()
        bundle.extractall(args.out, filter="data")
    try:
        report = validate_display(args.out, args.probe, args.source, audio=args.audio)
    except (ValueError, KeyError, OSError) as error:
        (args.out / "VALIDATION_FAILED.json").write_text(json.dumps({
            "build_passed": False, "hardware_verified": False, "error": str(error),
            "archive_sha256": digest,
        }, indent=2) + "\n")
        raise
    manifest = json.loads((args.out / "manifest.json").read_text())
    manifest.update(profile="display-passive-probe", extra_device_files=[], ram_handoff_supported=False)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    report["archive_sha256"] = digest
    if args.kms_variant:
        variant = make_kms_variant(args.out, args.kms_variant)
        report["kms_variant"] = {"path": str(args.kms_variant),
                                 "dtb_sha256": variant["sha256"]["r36-lab.dtb"], "hardware_verified": False}
    (args.out / "build_receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
