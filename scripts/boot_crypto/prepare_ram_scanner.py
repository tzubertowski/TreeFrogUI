"""Retarget only fixed-length search constants in our existing MIPS scanner."""
from pathlib import Path
import hashlib
import io
import json
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / "payload/mscan"
original = source.read_bytes()
patched = bytearray(original)
replacements = [
    (bytes.fromhex("41e97426c90d7a5e65b6afd9"), b"expand 32-by", "nonce_avp"),
    (bytes.fromhex("476de69e35a652805d1c4cc9"), b"expand 16-by", "nonce_vmlinux"),
    (bytes.fromhex("71fbf07e1cd1615306db9446"), b"ECRYPT_keyse", "nonce_driver"),
    (b"Linux version", b"chacha_decryp", "LinuxVersion"),
    (b"HC16E310", b"chacha20", "chip"),
    (bytes.fromhex("637c777bf26b6fc5"), b"ChaCha20", "aes_sbox"),
]
locations = []
elf = ELFFile(io.BytesIO(original))
executable = [(s["sh_offset"], s["sh_offset"] + s["sh_size"])
              for s in elf.iter_sections() if s["sh_flags"] & 4]
for old, new, label in replacements:
    assert len(old) == len(new) and original.count(old) == 1, label
    offset = original.index(old)
    assert not any(begin <= offset < end for begin, end in executable)
    patched[offset:offset + len(old)] = new
    locations.append({"file_offset": hex(offset), "output_label": label, "actual_pattern": new.decode()})
assert len(patched) == len(original)
for begin, end in executable:
    assert patched[begin:end] == original[begin:end]
target = ROOT / "payload/scan_boot_crypto"
target.write_bytes(patched)
report = {"source_sha256": hashlib.sha256(original).hexdigest(),
          "scanner_sha256": hashlib.sha256(patched).hexdigest(),
          "instruction_bytes_unchanged": True, "patterns": locations,
          "scope": "RAM only; scanner embeds its patterns, so its own pages are expected hits"}
(ROOT / "analysis/boot_crypto/ram_scanner.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
