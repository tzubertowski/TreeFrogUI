import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'boot_crypto'))
from peripheral_result import usb_cdc_result

RAW=(b'R36 USB CDC PROBE V1\nrun_id=fresh\nrelease=7.2.0-rc5-r36usb\n'
     b'gadget_rc=0 errno=0\nphase=bound\nudc=musb-hdrc.0.auto\n'
     b'received=114 sent=114 pings=3\nunbind_rc=0\nR36 USB CDC PROBE END\n')


def test_device_bind_never_substitutes_for_host_enumeration():
    r=usb_cdc_result(RAW,'fresh','7.2.0-rc5-r36usb')
    assert r['bind_unbind_verified'] and r['device_ping_replies']==3
    assert not r['host_enumeration_verified'] and not r['bidirectional_verified']
    assert r['host_report_required']


def test_stale_or_truncated_bind_not_accepted():
    for raw in (RAW.replace(b'run_id=fresh',b'run_id=stale'),RAW.replace(b'unbind_rc=0',b'unbind_rc=-1'),RAW+b'trailing\n'):
        assert not usb_cdc_result(raw,'fresh','7.2.0-rc5-r36usb')['bind_unbind_verified']
