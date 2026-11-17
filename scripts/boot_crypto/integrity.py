"""The observed AcXtrnal format and fixed-length CRC-preserving DTB edits."""
import argparse
import json
from pathlib import Path
import re
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]


def manifest_entries(raw):
    plain = bytes(value ^ 0x5A for value in raw).decode("ascii")
    result = []
    for line in plain.splitlines():
        match = re.fullmatch(r"([^:]+):\s+0x([0-9a-fA-F]{8})", line)
        if not match:
            raise ValueError("invalid AcXtrnal record")
        result.append((match[1], int(match[2], 16)))
    return result


def file_check(data):
    return zlib.crc32(data) ^ 0xFFFFFFFF


def preserve_crc(data, offset, target):
    if not 0 <= offset <= len(data) - 4:
        raise ValueError("CRC compensation field outside buffer")
    base = bytearray(data)
    base[offset:offset + 4] = bytes(4)
    start_crc = zlib.crc32(base)
    basis = {}
    for bit in range(32):
        changed = base.copy()
        changed[offset + bit // 8] ^= 1 << (bit % 8)
        vector, combination = zlib.crc32(changed) ^ start_crc, 1 << bit
        while vector:
            pivot = vector.bit_length() - 1
            if pivot not in basis:
                basis[pivot] = vector, combination
                break
            vector ^= basis[pivot][0]
            combination ^= basis[pivot][1]
    vector, solution = target ^ start_crc, 0
    while vector:
        pivot = vector.bit_length() - 1
        if pivot not in basis:
            raise ValueError("CRC compensation equations have no solution")
        vector ^= basis[pivot][0]
        solution ^= basis[pivot][1]
    base[offset:offset + 4] = solution.to_bytes(4, "little")
    if zlib.crc32(base) != target:
        raise ValueError("CRC compensation failed")
    return bytes(base)


def main():
    sys.path.insert(0, str(ROOT / "scripts"))
    from fat32img import Fat32
    fs = Fat32(str(ROOT / "dumpcard/dump_card.img"))
    try:
        entry = fs.find("/cubegm/AcXtrnal")
        raw = fs.read_clusters(entry["cl"], entry["size"])
        rows = []
        for name, expected in manifest_entries(raw):
            entry = fs.find("/" + name)
            data = fs.read_clusters(entry["cl"], entry["size"])
            actual = file_check(data)
            rows.append({"path": name, "bytes": len(data), "expected": f"{expected:08x}",
                         "computed": f"{actual:08x}", "matches": actual == expected})
    finally:
        fs.f.close()
    report = {"format": "text XOR 0x5a; each value is crc32(file) XOR 0xffffffff",
              "all_match": all(row["matches"] for row in rows), "rows": rows,
              "scope": "verified against original SD image bytes, including complete encrypted containers"}
    (ROOT / "analysis/boot_crypto/integrity_verified.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
