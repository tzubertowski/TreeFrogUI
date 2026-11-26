"""Ask the original MIPS decryptor to decode our container; no boot file writes."""
from pathlib import Path
import hashlib
import json
import os
import sys

from codec import encrypt, recover_key

ROOT = Path(__file__).resolve().parents[2]
os.environ["R36_PROJECT_ROOT"] = str(ROOT)
sys.path.insert(0, str(ROOT / "payload/kernel_ready/tools"))
from acceptance import WorkerTransport
from elftools.elf.elffile import ELFFile

folder = ROOT / "analysis/boot_crypto"
helper = folder / "original_initramfs/usr/bin/chacha_decrypt"
with helper.open("rb") as handle:
    assert ELFFile(handle)["e_machine"] == "EM_MIPS"
key = recover_key((ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes())
plain = (folder / "dtb.live.before.bin").read_bytes()
trial = folder / "native_oracle.input.enc"
trial.write_bytes(encrypt(plain, key, bytes(range(12))))
transport = WorkerTransport()
transport.put(helper, "/cubegm/r36-original-chacha-decrypt")
transport.put(trial, "/cubegm/r36-crypto-oracle-input.enc")
code, text = transport.run(
    "/mnt/sdcard/cubegm/r36-original-chacha-decrypt "
    "/mnt/sdcard/cubegm/r36-crypto-oracle-input.enc /tmp/r36-crypto-oracle.out", timeout=20)
if code:
    raise RuntimeError(f"native decryptor exited {code}: {text!r}")
code, output = transport.run("cat /tmp/r36-crypto-oracle.out", timeout=15)
assert code == 0 and output == plain, "native output differs from our original plaintext"
result = {"native_original_decryptor_verified": True, "tested_plaintext_bytes": len(plain),
          "plaintext_sha256": hashlib.sha256(plain).hexdigest(),
          "helper_sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
          "input_cipher_sha256": hashlib.sha256(trial.read_bytes()).hexdigest(),
          "key_sha256": hashlib.sha256(key).hexdigest(),
          "boot_files_written": False, "output_location": "/tmp/r36-crypto-oracle.out"}
(folder / "native_oracle.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
