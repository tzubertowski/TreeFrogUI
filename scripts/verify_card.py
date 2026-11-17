import sys, hashlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'D:\r36s-\scripts')
from fat32img import Fat32
R=r'D:\r36s-\dumpcard\verify_card_result.txt'
def say(m):
    open(R,'a',encoding='utf-8').write(m+'\n'); print(m)
open(R,'w').close()
try:
    fs=Fat32(r'\\.\PhysicalDrive2')
    def rd(p): e=fs.find(p); return fs.read_clusters(e['cl'], e['size'])
    checks=[('/CUBEGM/SETTING.XML',r'D:\r36s-\dumpcard\setting.xml.new'),
            ('/CUBEGM/CORES/libemu_md.so',r'D:\r36s-\dumpcard\libemu_md.so.new'),
            ('/CUBEGM/zhijack.sh',r'D:\r36s-\dumpcard\zhijack.sh'),
            ('/MD/dummy.md',r'D:\r36s-\dumpcard\dummy.md')]
    allok=True
    for p,lf in checks:
        got=rd(p); want=open(lf,'rb').read(); ok=got==want; allok&=ok
        say(f'{"OK " if ok else "FAIL"} {p} card={len(got)}b local={len(want)}b {hashlib.md5(got).hexdigest()[:10]}')
    so=rd('/CUBEGM/CORES/libemu_md.so'); say(f'  md.so ELF={so[:4]==b"\\x7fELF"} machine={so[18]}(8=MIPS)')
    import re
    s=rd('/CUBEGM/SETTING.XML'); m=re.search(rb'<autorun[^>]*>',s); say('  autorun on card: '+m.group(0).decode())
    n=sum(1 for _ in fs.walk()); say(f'  tree walk on card OK: {n} entries')
    say('CARD VERIFIED OK' if allok else 'CARD VERIFY FAILED')
    open(r'D:\r36s-\dumpcard\verify_DONE','w').write('OK' if allok else 'FAIL')
except Exception as e:
    say('ERROR: '+repr(e)); open(r'D:\r36s-\dumpcard\verify_DONE','w').write('ERROR')
