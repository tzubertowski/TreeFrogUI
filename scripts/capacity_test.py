import sys, os, struct, random
R=r'D:\r36s-\card2_backup\capacity_result.txt'
def say(m):
    open(R,'a',encoding='utf-8').write(str(m)+'\n'); print(m)
open(R,'w').close()
DEV=r'\\.\PhysicalDrive2'
SIZE=62914560000
BS=4096
MAGIC=b'FAKECAP1'
runid=random.getrandbits(32)
# probe offsets (4K-aligned): low anchors + dense high scan. Skip first 1 GB (FS metadata).
offsets=[]
for gb in [1,2,4,8,12,14,15,16]:
    offsets.append(int(gb*1024*1024*1024))
g=16.0
while g < SIZE/1024/1024/1024 - 0.1:
    g+=2.0; offsets.append(int(g*1024*1024*1024))
offsets.append(SIZE - BS)   # last block
offsets=sorted(set(o - (o % BS) for o in offsets if 0 < o <= SIZE-BS))
def block(off):
    rec=MAGIC+struct.pack('<QI', off, runid)   # 20 bytes
    return (rec*(BS//len(rec)+1))[:BS]
try:
    f=open(DEV,'r+b', buffering=0)
    say(f'device {DEV} claimed {SIZE} bytes ({SIZE/1024/1024/1024:.2f} GiB), runid={runid:#010x}')
    say(f'writing {len(offsets)} probe blocks...')
    for o in offsets:
        f.seek(o); f.write(block(o));
    f.flush(); os.fsync(f.fileno())
    # reopen to defeat any read cache
    f.close(); f=open(DEV,'rb', buffering=0)
    say('reading back...')
    good=[]; bad=[]
    for o in offsets:
        f.seek(o); d=f.read(BS)
        exp=block(o)
        if d==exp:
            good.append(o)
        else:
            # decode what we actually got
            got=''
            if d[:8]==MAGIC:
                go,gr=struct.unpack('<QI', d[8:20])
                got=f'aliased->off={go}({go/1024/1024/1024:.1f}G) runid={gr:#010x}'
            else:
                got='garbage/zero'
            bad.append((o,got))
    say(f'GOOD {len(good)}/{len(offsets)}   BAD {len(bad)}')
    for o,g in bad:
        say(f'  BAD at {o} ({o/1024/1024/1024:.2f} GiB): {g}')
    if good:
        say(f'highest VERIFIED offset: {max(good)} = {max(good)/1024/1024/1024:.2f} GiB')
    if bad:
        firstbad=min(o for o,_ in bad)
        say(f'first BAD offset: {firstbad} = {firstbad/1024/1024/1024:.2f} GiB')
        say(f'VERDICT: FAKE capacity — real flash is roughly <= {firstbad/1024/1024/1024:.1f} GiB (claimed {SIZE/1024/1024/1024:.1f})')
    else:
        say('VERDICT: all probes verified — capacity looks GENUINE (no wraparound detected at probe points)')
    f.close()
    open(r'D:\r36s-\card2_backup\capacity_DONE','w').write('OK')
except Exception as e:
    say('ERROR: '+repr(e)); open(r'D:\r36s-\card2_backup\capacity_DONE','w').write('ERR')
