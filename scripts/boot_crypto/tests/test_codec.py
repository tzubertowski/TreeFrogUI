from pathlib import Path
import struct
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/boot_crypto"))
from codec import decrypt, encrypt, make_uimage, parse_uimage, recover_key


@pytest.fixture(scope="module")
def key():
    return recover_key((ROOT / "analysis/card2_files/kdump/tpl_decrypted.bin").read_bytes())


@pytest.mark.parametrize("name,plain_name", [("driver.so", "driver_plain.so"), ("rkgame", "rkgame.elf")])
def test_complete_known_pair(key, name, plain_name):
    folder = ROOT / "analysis/card2_files"
    container = (folder / "cubegm_enc" / name).read_bytes()
    plain = decrypt(container, key)
    assert plain == (folder / plain_name).read_bytes()
    assert encrypt(plain, key, container[:12]) == container


@pytest.mark.parametrize("name", ["vmlinux.uImage", "avp.uImage"])
def test_both_original_images_pass_full_checksums(key, name):
    container = (ROOT / "analysis/card2_files/cubegm_enc" / name).read_bytes()
    image = decrypt(container, key)
    assert parse_uimage(image)["payload_bytes"] + 64 == len(image)
    assert encrypt(image, key, container[:12]) == container


def test_bad_lengths_and_truncation_rejected(key):
    image = encrypt(b"payload", key, bytes(12))
    for bad in [image[:15], image[:-1], image[:12] + bytes(4) + image[16:], image + b"trailing"]:
        with pytest.raises(ValueError): decrypt(bad, key)


def test_inner_crc_catches_payload_modification():
    data = bytearray(make_uimage(b"test" * 1000, 0x80100000, 0x80101000))
    parse_uimage(data)
    data[-9] ^= 1
    with pytest.raises(ValueError, match="checksum"): parse_uimage(data)


def test_other_loader_version_is_not_silently_accepted():
    blob = bytearray((ROOT / "analysis/boot_crypto/tpl_lzma_unpacked.bin").read_bytes())
    blob[0x9CC98] ^= 1
    with pytest.raises(ValueError): recover_key(blob)
