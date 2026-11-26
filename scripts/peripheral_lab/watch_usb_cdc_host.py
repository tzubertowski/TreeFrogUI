"""One bounded hardware-test watcher, exact diagnostic identity only.

Start immediately before a deliberate console watchdog boot. Does not open any
other COM port and never writes to the console filesystem or controls reset.
"""
import argparse
import json
from pathlib import Path
import secrets
import time

from usb_cdc_host import exchange


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=100)
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir() or not 1 <= args.seconds <= 180:
        parser.error('new output and duration1..180 required')
    import serial
    from serial.tools import list_ports
    end = time.monotonic() + args.seconds
    record = {'enumerated': False, 'bidirectional_verified': False,
              'scope': 'bounded exact-identity CDC watcher, not MTP/host/OTG acceptance'}
    attempts = []
    next_pnp_check = 0
    while time.monotonic() < end:
        matches = [p for p in list_ports.comports() if
                   (p.vid, p.pid, p.serial_number) == (0x1d6b, 0x0104, 'R36LAB-CDC-DIAG')]
        if len(matches) > 1:
            record['error'] = 'ambiguous diagnostic CDC identity'; break
        selected = matches[0].device if matches else None
        if not selected and time.monotonic() >= next_pnp_check:
            from usb_windows_identity import present_ports
            try:
                pnp = present_ports()
                if pnp:
                    selected = pnp[0]
                    record['identity_source'] = 'present exact PnP instance'
            except (RuntimeError, ValueError, OSError) as error:
                attempts.append(str(error))
            next_pnp_check = time.monotonic() + 1
        if selected:
            record.update(enumerated=True, port=selected, serial='R36LAB-CDC-DIAG')
            try:
                challenges = []
                with serial.Serial(selected,115200,timeout=.1,write_timeout=.5) as port:
                    port.reset_input_buffer()
                    for _ in range(3):
                        token = secrets.token_hex(16)
                        exchange(port,token,min(end,time.monotonic()+1.5))
                        challenges.append(token)
                record.update(bidirectional_verified=True,challenges=challenges)
                break
            except (OSError, serial.SerialException, TimeoutError, ValueError) as error:
                attempts.append(str(error))
        time.sleep(.2)
    record['attempt_errors'] = attempts[-20:]
    if not record['enumerated']: record['error'] = 'diagnostic CDC did not enumerate before deadline'
    with args.out.open('x') as handle: handle.write(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))
    if not record['bidirectional_verified']: raise SystemExit(1)


if __name__ == '__main__': main()
