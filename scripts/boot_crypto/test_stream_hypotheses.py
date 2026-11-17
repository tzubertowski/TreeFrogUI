"""Bounded known-plaintext checks; a negative result only excludes listed keys."""
import hashlib
import json
from pathlib import Path
import struct

from Crypto.Cipher import ARC4, Salsa20

ROOT = Path(__file__).resolve().parents[2]
MASK = 0xFFFFFFFF


def rotate(value, count):
    return ((value << count) | (value >> (32 - count))) & MASK


def block(key, iv, rounds=20):
    if len(key) not in (16, 32) or len(iv) != 16:
        raise ValueError("key must be 16/32 bytes; state IV must be 16 bytes")
    sigma = b"expand 32-byte k" if len(key) == 32 else b"expand 16-byte k"
    state = list(struct.unpack("<4I", sigma) + struct.unpack("<8I", key if len(key) == 32 else key * 2)
                 + struct.unpack("<4I", iv))
    work = state.copy()

    def qr(a, b, c, d):
        work[a] = (work[a] + work[b]) & MASK; work[d] = rotate(work[d] ^ work[a], 16)
        work[c] = (work[c] + work[d]) & MASK; work[b] = rotate(work[b] ^ work[c], 12)
        work[a] = (work[a] + work[b]) & MASK; work[d] = rotate(work[d] ^ work[a], 8)
        work[c] = (work[c] + work[d]) & MASK; work[b] = rotate(work[b] ^ work[c], 7)

    for _ in range(rounds // 2):
        for indices in [(0, 4, 8, 12), (1, 5, 9, 13), (2, 6, 10, 14), (3, 7, 11, 15),
                        (0, 5, 10, 15), (1, 6, 11, 12), (2, 7, 8, 13), (3, 4, 9, 14)]:
            qr(*indices)
    return struct.pack("<16I", *((a + b) & MASK for a, b in zip(state, work)))


def main():
    expected = bytes.fromhex("10f1e7e4d13b5915500fdd1fa32071c4c7d1f4c733c068030422aa9ac3d46c4e"
                             "d2826446079faa0914c2d705d98b02a2b5129cd1de164eb9cbd083e8a2503c4e")
    assert block(bytes(range(32)), bytes.fromhex("01000000000000090000004a00000000")) == expected
    otp = bytes.fromhex("84a6edba184d29ef40550000e09c9086")
    otp32 = otp + bytes(15) + b"\x0f"
    keys = {"zero16": bytes(16), "zero32": bytes(32), "ff32": b"\xff" * 32,
            "range0_16": bytes(range(16)), "range0_32": bytes(range(32)), "range1_32": bytes(range(1, 33)),
            "otp16": otp, "otp_row0_row1": otp32, "otp16_repeated": otp * 2,
            "sha256_otp16": hashlib.sha256(otp).digest(), "sha256_otp32": hashlib.sha256(otp32).digest(),
            "md5_otp16_repeated": hashlib.md5(otp).digest() * 2,
            "ascii_hex_repeated": b"0123456789abcdef" * 2,
            "ascii_hex32": b"0123456789abcdef0123456789ABCDEF"}
    keys = {name: key for name, key in keys.items() if len(key) in (16, 32)}
    report = {"rfc8439_block_vector": "PASS", "matches": [], "attempts": 0,
              "scope": "listed candidate keys only; no general rejection of any cipher"}
    parent = ROOT / "analysis/card2_files"
    for filename, plaintext in [("driver.so", "driver_plain.so"), ("rkgame", "rkgame.elf")]:
        container = (parent / "cubegm_enc" / filename).read_bytes()
        plain = (parent / plaintext).read_bytes()
        length = struct.unpack_from("<I", container, 12)[0]
        assert length == len(container) - 16 == len(plain)
        nonce = container[:12]
        target = bytes(a ^ b for a, b in zip(container[16:80], plain[:64]))
        ivs = {"counter0_nonce": bytes(4) + nonce, "counter1_nonce": struct.pack("<I", 1) + nonce,
               "header16": container[:16], "nonce_counter0": nonce + bytes(4),
               "nonce_counter1": nonce + struct.pack("<I", 1),
               "size_nonce": struct.pack("<I", length) + nonce, "zero16": bytes(16)}
        for key_name, key in keys.items():
            for iv_name, iv in ivs.items():
                for rounds in (8, 12, 20):
                    report["attempts"] += 1
                    if block(key, iv, rounds) == target:
                        report["matches"].append({"file": filename, "cipher": f"ChaCha{rounds}",
                                                   "key_candidate": key_name, "iv": iv_name})
            for which, n in [("first8", nonce[:8]), ("last8", nonce[-8:])]:
                report["attempts"] += 1
                if Salsa20.new(key=key, nonce=n).encrypt(bytes(64)) == target:
                    report["matches"].append({"file": filename, "cipher": "Salsa20", "key_candidate": key_name, "iv": which})
            for label, rc4key in [("key", key), ("key_nonce", key + nonce), ("nonce_key", nonce + key)]:
                for drop in (0, 256, 768, 1536):
                    report["attempts"] += 1
                    if ARC4.new(rc4key, drop=drop).encrypt(bytes(64)) == target:
                        report["matches"].append({"file": filename, "cipher": "RC4", "key_candidate": key_name,
                                                   "iv": label, "drop": drop})
    path = ROOT / "analysis/boot_crypto/stream_candidates.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
