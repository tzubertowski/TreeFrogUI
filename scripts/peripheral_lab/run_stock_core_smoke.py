"""Run only original synthetic ROMs on stock console with its existing libraries.

Uploads uniquely named diagnostic tools; does not alter UI/boot/core binaries or
open physical display/audio/input. A successful run is STOCK acceptance only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/kernel_lab'))
from acceptance import WorkerTransport, INSPECT, inspect, require_run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--harness',type=Path,default=ROOT/'analysis/driver_port/libretro-smoke-console-v2')
    args=parser.parse_args()
    args.out.mkdir(exist_ok=False)
    t=WorkerTransport(); identity=inspect(require_run(t,INSPECT))
    if identity['loader_loaded']:raise RuntimeError('unexpected RAM loader')
    prefix='r36-core-smoke-'+str(time.time_ns())
    files={'harness':args.harness,
           'test.gb':ROOT/'analysis/driver_port/synthetic_roms_v1/input_test.gb',
           'test.nes':ROOT/'analysis/driver_port/synthetic_roms_v1/input_test.nes'}
    remote={}
    for name,path in files.items():
        dest=prefix+'-'+name;remote[name]='/mnt/sdcard/cubegm/'+dest
        t.put(path,'/cubegm/'+dest)
        got=require_run(t,'md5sum '+remote[name]).split()[0].decode()
        if got!=hashlib.md5(path.read_bytes()).hexdigest():raise ValueError('upload hash mismatch')
    records=[]
    for core,extension in [('gambatte','gb'),('fceumm','nes')]:
        # Only these cores and synthetic content. All incidental generated files
        # go to a new RAM directory, never actual save/BIOS folders.
        work='/tmp/'+prefix+'-'+core
        command='mkdir '+shlex.quote(work)+' && cd '+shlex.quote(work)+' && env LD_LIBRARY_PATH=/mnt/sdcard/cubegm/lib:/lib:/usr/lib '+remote['harness']+' /mnt/sdcard/cubegm/cores/'+core+'_libretro.so '+remote['test.'+extension]
        code,raw=t.run(command,timeout=25)
        (args.out/(core+'.txt')).write_bytes(raw)
        record={'core':core,'exit':code,'passed':code==0 and b'LIBRETRO_SYNTHETIC_EXECUTION=PASS' in raw,
                'scope':'stock4.4 actual CPU and existing console glibc, synthetic content, headless callbacks only'}
        records.append(record);print(json.dumps(record),flush=True)
        if not record['passed']:break
    result={'stock_runtime_verified':len(records)==2 and all(r['passed'] for r in records),
            'identity':identity,'cases':records,'new_kernel_verified':False,'full_UI_verified':False,
            'physical_video_audio_input_verified':False,'user_saves_modified':False}
    (args.out/'suite.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if not result['stock_runtime_verified']:raise SystemExit(1)


if __name__=='__main__':main()
