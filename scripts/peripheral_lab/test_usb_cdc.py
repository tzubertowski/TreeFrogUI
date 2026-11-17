from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from usb_cdc_host import exchange

ROOT = Path(__file__).resolve().parents[2]
TOKEN = '1234567890abcdef1234567890abcdef'


class Port:
    def __init__(self, blocks, partial=False):
        self.blocks = list(blocks); self.partial = partial; self.written = None
    def write(self, data): self.written = data; return len(data) - int(self.partial)
    def read(self, size): return self.blocks.pop(0) if self.blocks else b''


class Clock:
    def __init__(self): self.t = 0
    def __call__(self): self.t += .05; return self.t


def test_partial_lines_and_matching_challenge():
    port = Port([b'PONG stale\nPO', ('NG ' + TOKEN[:5]).encode(), (TOKEN[5:] + '\n').encode()])
    assert exchange(port, TOKEN, 1, Clock()) == TOKEN
    assert port.written == ('PING ' + TOKEN + '\n').encode()


def test_stale_response_partial_write_or_unbounded_data_never_pass():
    with pytest.raises(TimeoutError): exchange(Port([b'PONG ' + b'0' * 32 + b'\n']), TOKEN, .5, Clock())
    with pytest.raises(ValueError, match='partial'): exchange(Port([], True), TOKEN, 1, Clock())
    with pytest.raises(ValueError, match='oversized'): exchange(Port([b'x' * 4097]), TOKEN, 1, Clock())
    with pytest.raises(ValueError, match='challenge'): exchange(Port([]), 'bad', 1, Clock())


def test_usb_diag_isolated_and_no_watchdog_feed_or_writable_lun():
    text = (ROOT / 'scripts/peripheral_lab/usb_cdc_init.c').read_text()
    assert 'functions/acm.GS0' in text
    assert 'HOST_REPORT_REQUIRED' in text
    assert 'end = now_ms() + 12000' in text
    assert 'count > 1' in text
    assert '0x18818500' not in text and 'functions/mass_storage' not in text
    assert 'reboot(' not in text and 'system(' not in text
    dt = (ROOT / 'scripts/kernel_lab/r36-usb-cdc.dts').read_text()
    assert '&usb0 { status = "okay"; dr_mode = "peripheral"; };' in dt
    assert '&usb1 { status = "disabled"; };' in dt
    build = (ROOT / 'scripts/peripheral_lab/vm_build_kernel.sh').read_text()
    assert '--enable EXPERT --disable VT --disable VT_CONSOLE' in build
    assert build.index('USB isolation failed:') < build.index('make -C "$SRC" -j1')
