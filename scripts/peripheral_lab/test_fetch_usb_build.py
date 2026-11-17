import io
from pathlib import Path
import sys
import tarfile

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from fetch_usb_build import FILES, check_archive


def make(names):
    data=io.BytesIO()
    with tarfile.open(fileobj=data,mode='w') as archive:
        for name in names:
            item=tarfile.TarInfo(name);archive.addfile(item,io.BytesIO())
    data.seek(0)
    return tarfile.open(fileobj=data)


def test_usb_archive_exact_allowlist():
    with make(FILES) as archive:check_archive(archive)


@pytest.mark.parametrize('extra', ['../escape','/escape','r36_hc16xx_i2s.ko','script.py','init.elf'])
def test_wrong_subsystem_path_or_duplicate_refused(extra):
    with make([*FILES,extra]) as archive:
        with pytest.raises(ValueError):check_archive(archive)


def test_missing_input_refused():
    with make(FILES-{'init.elf'}) as archive:
        with pytest.raises(ValueError):check_archive(archive)
