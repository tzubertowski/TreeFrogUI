"""Bounded stock-only passive audio capture; no clock/DMA/GPIO writes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/kernel_lab'))
from acceptance import WorkerTransport, inspect, INSPECT, require_run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    args.out.mkdir(exist_ok=False)
    transport=WorkerTransport()
    identity=inspect(require_run(transport,INSPECT))
    if identity['loader_loaded']: raise RuntimeError('unexpected active RAM loader')
    tool=ROOT/'analysis/driver_port/r36-audio-passive-v1'
    remote='r36-audio-passive-'+str(time.time_ns())
    transport.put(tool,'/cubegm/'+remote)
    expected=hashlib.md5(tool.read_bytes()).hexdigest()
    hashes=require_run(transport,'md5sum /mnt/sdcard/cubegm/'+remote).decode()
    if hashes.split()[0]!=expected:raise ValueError('passive tool delivery mismatch')
    raw=require_run(transport,'/mnt/sdcard/cubegm/'+remote,timeout=15)
    (args.out/'audio.txt').write_bytes(raw)
    report={'identity':identity,'tool_sha256':hashlib.sha256(tool.read_bytes()).hexdigest(),
            'scope':'stock SND0/SYS selected registers read-only, no exclusive ownership proof',
            'audio_hardware_verified':False,'exclusive_ownership_proven':False}
    (args.out/'capture.json').write_text(json.dumps(report,indent=2)+'\n')
    print(raw.decode('ascii','replace'));print(json.dumps(report,indent=2))


if __name__=='__main__':main()
