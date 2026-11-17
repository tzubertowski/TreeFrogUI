"""Explicit, bounded Windows CDC test. Never scans/opens unrelated serial ports.

Run only after the user connects the console and starts a diagnostic candidate.
Enumeration and bidirectional challenge proof are separate from Linux's bind.
"""
import argparse
import json
from pathlib import Path
import secrets
import time


def exchange(port, token, deadline, clock=time.monotonic):
    if len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
        raise ValueError('challenge must be 32 lowercase hex digits')
    expected = ('PONG ' + token).encode()
    request = ('PING ' + token + '\n').encode()
    if port.write(request) != len(request):
        raise ValueError('partial challenge write')
    buffer = bytearray()
    while clock() < deadline:
        block = port.read(128)
        if not block:
            continue
        buffer.extend(block)
        if len(buffer) > 4096:
            raise ValueError('oversized diagnostic response')
        while b'\n' in buffer:
            line, _, rest = buffer.partition(b'\n')
            buffer[:] = rest
            if line.rstrip(b'\r') == expected:
                return token
    raise TimeoutError('no matching CDC response before deadline')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True, help='explicit COM port of the diagnostic console')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir(): parser.error('output must be new with an existing parent')
    import serial
    from serial.tools import list_ports
    matches = [p for p in list_ports.comports() if p.device.lower() == args.port.lower()]
    if len(matches) != 1:
        raise RuntimeError('explicit diagnostic COM port is not currently enumerated')
    info = matches[0]
    if (info.vid, info.pid, info.serial_number) != (0x1d6b, 0x0104, 'R36LAB-CDC-DIAG'):
        raise RuntimeError('port descriptor identity is not this diagnostic')
    record = {'enumerated': True, 'bidirectional_verified': False, 'port': info.device,
              'vid': info.vid, 'pid': info.pid, 'serial': info.serial_number,
              'scope': 'one explicit CDC enumeration/challenge roundtrip, not MTP/host/OTG acceptance'}
    try:
        with serial.Serial(info.device, 115200, timeout=.1, write_timeout=.5) as port:
            port.reset_input_buffer()
            challenges = []
            for _ in range(3):
                token = secrets.token_hex(16)
                exchange(port, token, time.monotonic() + 1.5)
                challenges.append(token)
            record.update(bidirectional_verified=True, challenges=challenges)
    except Exception as error:
        record['error'] = str(error)
    with args.out.open('x', encoding='ascii') as handle:
        handle.write(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))
    if not record['bidirectional_verified']: raise SystemExit(1)


if __name__ == '__main__':
    main()
