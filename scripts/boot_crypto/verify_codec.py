"""Validate recovered cipher against full original files and inner image CRCs."""
from pathlib import Path
import gzip
import hashlib
import json

from codec import decrypt, encrypt, recover_key, parse_uimage, unpack_loader

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / "analysis/card2_files"
folder = ROOT / "analysis/boot_crypto"
loader = (source / "kdump/tpl_decrypted.bin").read_bytes()
unpacked = unpack_loader(loader)
key = recover_key(loader)
rows = []
for name in ["driver.so", "rkgame", "vmlinux.uImage", "avp.uImage"]:
    data = (source / "cubegm_enc" / name).read_bytes()
    plain = decrypt(data, key)
    row = {"file": name, "container_bytes": len(data), "plaintext_bytes": len(plain),
           "plaintext_sha256": hashlib.sha256(plain).hexdigest(),
           "exact_original_reencrypted": encrypt(plain, key, data[:12]) == data}
    if name in ["driver.so", "rkgame"]:
        known = source / ("driver_plain.so" if name == "driver.so" else "rkgame.elf")
        row["full_known_plaintext_match"] = plain == known.read_bytes()
        assert row["full_known_plaintext_match"]
    else:
        row["uImage"] = parse_uimage(plain)
        assert row["uImage"]["compression"] == 1
        inflated = gzip.decompress(plain[64:64 + row["uImage"]["payload_bytes"]])
        row["inflated_bytes"] = len(inflated)
        row["inflated_sha256"] = hashlib.sha256(inflated).hexdigest()
        (folder / "decrypted" / (name + ".raw")).write_bytes(inflated)
    assert row["exact_original_reencrypted"]
    rows.append(row)
result = {"verified": True, "cipher": "ChaCha20, 256-bit key, 96-bit nonce, counter0",
          "container": "nonce12 || u32le(length) || ciphertext[length]",
          "key_sha256": hashlib.sha256(key).hexdigest(),
          "loader_sha256": hashlib.sha256(unpacked).hexdigest(),
          "loader_base": "0x89da0000", "wrapper": "0x89dab188", "primitive": "0x89daac80",
          "key_obfuscated_offset": "0x9cc98", "key_transform": "ROL8(blob[i] XOR ((0x33+7*i)&255) XOR 0x55,5) XOR 0xaa",
          "rows": rows, "hardware_independent_boot_verified": False}
(folder / "cipher_verified.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
