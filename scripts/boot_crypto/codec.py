"""Verified hcboot SD container: nonce[12], size_le32, ChaCha20(counter=0)."""
import argparse
import gzip
import hashlib
import json
import lzma
from pathlib import Path
import struct
import sys
import zlib

from Crypto.Cipher import ChaCha20

ROOT = Path(__file__).resolve().parents[2]
LOADER_HASH = "c95aa3062c308818e4572f65e8c29632ec04cd390cceac0a63d4b053fb4d0ebc"
KEY_OFFSET = 0x9CC98


def unpack_loader(data):
    if hashlib.sha256(data).hexdigest() == LOADER_HASH:
        return data
    if data[0x2E48:0x2E4D] != bytes.fromhex("5d00008000"):
        raise ValueError("not the measured hcboot compressed image")
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE, memlimit=64 * 1024 * 1024)
    unpacked = decoder.decompress(data[0x2E48:], max_length=2 * 1024 * 1024)
    if not decoder.eof or len(unpacked) != 812464 or hashlib.sha256(unpacked).hexdigest() != LOADER_HASH:
        raise ValueError("loader identity/decompression mismatch; do not reuse offsets for another version")
    return unpacked


def recover_key(loader):
    plain = unpack_loader(loader)
    obfuscated = plain[KEY_OFFSET:KEY_OFFSET + 32]
    key = bytearray()
    for i, byte in enumerate(obfuscated):
        value = byte ^ ((0x33 + 7 * i) & 255) ^ 0x55
        key.append((((value << 5) | (value >> 3)) & 255) ^ 0xAA)
    return bytes(key)


def decrypt(container, key, *, allow_trailing=False):
    if len(key) != 32 or len(container) < 16:
        raise ValueError("invalid key/header length")
    size = struct.unpack_from("<I", container, 12)[0]
    if not size or size > len(container) - 16:
        raise ValueError("invalid declared plaintext length")
    if not allow_trailing and size != len(container) - 16:
        raise ValueError("trailing bytes; this tool defaults to strict containers")
    # IETF nonce layout: counter word12 starts at zero; nonce words13..15.
    return ChaCha20.new(key=key, nonce=container[:12]).decrypt(container[16:16 + size])


def encrypt(plaintext, key, nonce):
    if len(key) != 32 or len(nonce) != 12 or not 0 < len(plaintext) <= 0xFFFFFFFF:
        raise ValueError("invalid key/nonce/plaintext size")
    return nonce + struct.pack("<I", len(plaintext)) + ChaCha20.new(key=key, nonce=nonce).encrypt(plaintext)


def parse_uimage(image):
    if len(image) < 64:
        raise ValueError("short uImage")
    magic, hcrc, timestamp, size, load, entry, dcrc, os_id, arch, kind, comp, name = struct.unpack(">7I4B32s", image[:64])
    if magic != 0x27051956 or size > len(image) - 64:
        raise ValueError("invalid legacy uImage header/size")
    header = image[:4] + bytes(4) + image[8:64]
    if zlib.crc32(header) != hcrc or zlib.crc32(image[64:64 + size]) != dcrc:
        raise ValueError("uImage header/payload checksum mismatch")
    return {"timestamp": timestamp, "payload_bytes": size, "load": hex(load), "entry": hex(entry),
            "os": os_id, "arch": arch, "type": kind, "compression": comp,
            "name": name.split(b"\0", 1)[0].decode("ascii"), "trailing_bytes": len(image) - size - 64}


def make_uimage(payload, load, entry, *, timestamp=0, name="vmlinux", compression=1):
    if compression == 1:
        body = gzip.compress(payload, compresslevel=9, mtime=0)
    elif compression == 0:
        body = payload
    else:
        raise ValueError("builder supports none/gzip only")
    label = name.encode("ascii")
    if len(label) > 32 or not body or not 0 <= load <= 0xFFFFFFFF or not 0 <= entry <= 0xFFFFFFFF:
        raise ValueError("invalid uImage parameters")
    header = struct.pack(">7I4B32s", 0x27051956, 0, timestamp, len(body), load, entry,
                         zlib.crc32(body), 5, 5, 2, compression, label.ljust(32, b"\0"))
    return header[:4] + struct.pack(">I", zlib.crc32(header)) + header[8:] + body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["decrypt", "encrypt", "inspect"])
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--loader", type=Path, default=ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin")
    parser.add_argument("--nonce", help="12-byte nonce as 24 hex characters; encrypt only")
    args = parser.parse_args()
    key = recover_key(args.loader.read_bytes())
    data = args.input.read_bytes()
    if args.operation == "encrypt":
        import secrets
        nonce = bytes.fromhex(args.nonce) if args.nonce else secrets.token_bytes(12)
        result = encrypt(data, key, nonce)
    else:
        result = decrypt(data, key)
    if args.operation != "inspect":
        if args.output is None or not args.output.parent.is_dir() or args.output.resolve() == args.input.resolve():
            parser.error("provide a different output file in an existing directory")
        args.output.write_bytes(result)
    report = {"operation": args.operation, "input_bytes": len(data), "output_bytes": len(result),
              "output_sha256": hashlib.sha256(result).hexdigest(),
              "key_sha256": hashlib.sha256(key).hexdigest(), "device_writes": False}
    plain = data if args.operation == "encrypt" else result
    if plain[:4] == bytes.fromhex("27051956"):
        report["uImage"] = parse_uimage(plain)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
