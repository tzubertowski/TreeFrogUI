import importlib.util
from pathlib import Path
import shlex
import struct
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/boot_crypto"))
from capture_dtb import patch_property, prepare, properties
from test_stream_hypotheses import block


def test_preserves_all_nodes_and_unrelated_properties():
    original = (ROOT / "analysis/card2_files/cubegm_enc/dtb.bin").read_bytes()
    candidate, args, command = prepare(original)
    old, new = properties(original), properties(candidate)
    assert old.keys() == new.keys()
    changed = [(path, key) for path in old for key in old[path] if old[path][key] != new[path][key]]
    assert changed == [("/chosen", "bootargs")]
    assert shlex.split(args)[-3:] == ["--", "-c", command]
    assert command.endswith("exec /init") and "sdcard" not in command
    assert struct.unpack_from(">I", candidate, 4)[0] == len(candidate)


def test_duplicate_capture_is_rejected():
    original = (ROOT / "analysis/card2_files/cubegm_enc/dtb.bin").read_bytes()
    candidate, _, _ = prepare(original)
    with pytest.raises(ValueError, match="already overrides"):
        prepare(candidate)


def test_missing_property_is_rejected():
    original = (ROOT / "analysis/card2_files/cubegm_enc/dtb.bin").read_bytes()
    with pytest.raises(ValueError, match="one existing"):
        patch_property(original, "/chosen", "absent", b"x\0")


def test_chacha_reference_agrees_with_pycryptodome():
    from Crypto.Cipher import ChaCha20
    key = bytes(range(32)); nonce = bytes(range(12))
    for counter in (0, 1, 17):
        cipher = ChaCha20.new(key=key, nonce=nonce)
        cipher.seek(counter * 64)
        assert block(key, struct.pack("<I", counter) + nonce) == cipher.encrypt(bytes(64))
