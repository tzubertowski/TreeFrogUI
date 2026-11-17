"""Optional regressions against the real isolated USB build, no device access."""
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_usb_build import ROOT, sha, validate


@pytest.fixture
def candidate():
    value = os.environ.get('R36_USB_CANDIDATE')
    if not value:
        pytest.skip('set R36_USB_CANDIDATE to a completed isolated USB build')
    return Path(value)


def check(path):
    return validate(path, ROOT / 'analysis/driver_port/r36-usb-cdc-init-v1')


def test_real_usb_candidate(candidate):
    result = check(candidate)
    assert result['build_passed']
    assert not result['hardware_verified'] and not result['Windows_enumeration_verified']
    assert not result['bidirectional_verified']


def test_configuration_reintroduction_rejected_even_with_updated_digest(candidate, tmp_path):
    target = tmp_path / 'candidate'
    shutil.copytree(candidate, target)
    config = target / 'kernel.config'
    text = config.read_text()
    assert '# CONFIG_INPUT is not set' in text
    config.write_text(text.replace('# CONFIG_INPUT is not set', 'CONFIG_INPUT=y'))
    manifest = json.loads((target / 'manifest.json').read_text())
    manifest['sha256']['kernel.config'] = sha(config)
    (target / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='unexpected subsystem.*INPUT'):
        check(target)


def test_stale_init_rejected(candidate, tmp_path):
    stale = tmp_path / 'stale.elf'
    stale.write_bytes(b'not the accepted PID1')
    with pytest.raises(ValueError, match='stale USB init'):
        validate(candidate, stale)


def test_modified_dtb_rejected(candidate, tmp_path):
    target = tmp_path / 'candidate'
    shutil.copytree(candidate, target)
    dtb = target / 'r36-lab.dtb'
    data = bytearray(dtb.read_bytes()); data[-1] ^= 1
    dtb.write_bytes(data)
    with pytest.raises(ValueError, match='artifact digest mismatch'):
        check(target)
