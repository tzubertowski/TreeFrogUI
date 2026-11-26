import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from patch_diagnostic_init import patch

ROOT=Path(__file__).resolve().parents[2]


def test_actual_audio_patch_changes_only_initramfs_and_keeps_module(tmp_path):
    source=ROOT/'payload/kernel_audio_silent_active_v2'
    init=ROOT/'analysis/driver_port/r36-display-audio-silent-probe-v4'
    output=tmp_path/'new'
    original=hashlib.sha256((source/'vmlinux.bin').read_bytes()).hexdigest()
    result=patch(source,init,output)
    assert result['passed'] and not result['kernel_code_changed']
    assert hashlib.sha256((source/'vmlinux.bin').read_bytes()).hexdigest()==original
    assert (output/'r36_hc16xx_i2s.ko').read_bytes()==(source/'r36_hc16xx_i2s.ko').read_bytes()
    assert (output/'r36-lab.dtb').read_bytes()==(source/'r36-lab.dtb').read_bytes()
    assert (output/'init.elf').read_bytes()==init.read_bytes()
    assert json.loads((output/'manifest.json').read_text())['extra_device_files']==['r36_hc16xx_i2s.ko']
    with pytest.raises(ValueError,match='must be new'):patch(source,init,output)
