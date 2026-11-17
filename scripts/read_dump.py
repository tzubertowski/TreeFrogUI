import sys, os, struct, hashlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'D:\r36s-\scripts')
from fat32img import Fat32
R=r'D:\r36s-\dumpcard\read_dump_result.txt'
OUT=r'D:\r36s-\dumpcard\dump_out'
os.makedirs(OUT, exist_ok=True)
def say(m):
    open(R,'a',encoding='utf-8').write(str(m)+'\n'); print(m)
open(R,'w').close()
MACH={8:'MIPS',40:'ARM',183:'AArch64',62:'x86-64',3:'x86'}
try:
    fs=Fat32(r'\\.\PhysicalDrive2')
    # find /dump dir
    try:
        d=fs.find('/dump')
    except FileNotFoundError:
        d=None
    if not d or not d['dir']:
        say('NO /dump FOLDER ON CARD — the dumper did not run (or wrote elsewhere).')
        # show root listing to see what happened
        say('root entries:')
        for e in fs.readdir(fs.rootc):
            say(f"  {'D' if e['dir'] else 'F'} {e['size']:>10} {e['name']}")
        open(r'D:\r36s-\dumpcard\read_DONE','w').write('NODUMP')
        sys.exit()
    say('=== /dump contents ===')
    files=[e for e in fs.readdir(d['cl']) if not e['dir']]
    for e in files:
        data=fs.read_clusters(e['cl'], e['size'])
        safe=e['name'].replace('/','_')
        open(os.path.join(OUT,safe),'wb').write(data)
        tag=''
        if data[:4]==b'\x7fELF':
            cls=32 if data[4]==1 else 64; mach=struct.unpack('<H',data[18:20])[0]
            tag=f'  <-- ELF{cls} {MACH.get(mach,mach)} (DECRYPTED!)'
        say(f"  {e['name']:28} {e['size']:>9}  {hashlib.md5(data).hexdigest()[:12]}{tag}")
    # print text logs
    for e in files:
        if e['name'].lower().endswith(('.txt','.log')) or e['name'] in ('dump.log',):
            data=fs.read_clusters(e['cl'], e['size'])
            say(f"\n----- {e['name']} -----")
            say(data.decode('utf-8','replace')[:4000])
    open(r'D:\r36s-\dumpcard\read_DONE','w').write('OK')
except Exception as ex:
    say('ERROR: '+repr(ex)); open(r'D:\r36s-\dumpcard\read_DONE','w').write('ERROR')
