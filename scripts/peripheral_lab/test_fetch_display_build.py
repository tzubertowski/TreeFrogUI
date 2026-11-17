import io
import json
from pathlib import Path
import struct
import sys
import tarfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_display_build import REQUIRED, check_archive, validate_display


def archive_with(names):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, kind in names:
            member = tarfile.TarInfo(name)
            member.type = kind
            archive.addfile(member, io.BytesIO())
    buffer.seek(0)
    return tarfile.open(fileobj=buffer)


def test_exact_flat_archive():
    with archive_with([(name, tarfile.REGTYPE) for name in REQUIRED]) as archive:
        check_archive(archive)


def test_audio_module_requires_explicit_archive_opt_in():
    rows = [(name, tarfile.REGTYPE) for name in REQUIRED | {"r36_hc16xx_i2s.ko"}]
    with archive_with(rows) as archive:
        with pytest.raises(ValueError, match="unexpected archive"):
            check_archive(archive)
    with archive_with(rows) as archive:
        check_archive(archive, audio=True)
    with archive_with([(name, tarfile.REGTYPE) for name in REQUIRED]) as archive:
        with pytest.raises(ValueError, match="missing build"):
            check_archive(archive, audio=True)


@pytest.mark.parametrize("extra,kind", [
    ("../escape", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE),
    ("surprise.py", tarfile.REGTYPE), ("init.elf", tarfile.SYMTYPE),
    ("init.elf", tarfile.REGTYPE),
])
def test_unexpected_or_duplicate_archive_rejected(extra, kind):
    with archive_with([(name, tarfile.REGTYPE) for name in REQUIRED] + [(extra, kind)]) as archive:
        with pytest.raises(ValueError):
            check_archive(archive)


def test_incomplete_archive_rejected():
    with archive_with([("init.elf", tarfile.REGTYPE)]) as archive:
        with pytest.raises(ValueError, match="missing build files"):
            check_archive(archive)


def test_oversize_archive_member_rejected():
    class Archive:
        def getmembers(self):
            member = tarfile.TarInfo("init.elf")
            member.size = 32 * 1024 * 1024 + 1
            return [member]
    with pytest.raises(ValueError, match="oversized"):
        check_archive(Archive())
