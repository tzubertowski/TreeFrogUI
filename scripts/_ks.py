d=r'D:\r36s-\analysis\card2_files\cubegm_enc\driver.so'
p=r'D:\r36s-\dumpcard\dump_out\file_driver.so'
c=open(d,'rb').read(); q=open(p,'rb').read()
nonce=c[:12]; size=int.from_bytes(c[12:16],'little'); ct=c[16:]
print('nonce',nonce.hex(),'size',size,'ct',len(ct),'pt',len(q))
ks=bytes(a^b for a,b in zip(ct,q))
print('ks head',ks[:64].hex())
# check periods
for per in (1,2,4,8,12,16,20,24,32,40,48,64,96,128,256):
    n=min(len(ks),4096)
    ok=all(ks[i]==ks[i%per] for i in range(n))
    if ok: print('PERIOD',per)
# entropy of ks
import math,collections
cnt=collections.Counter(ks); H=-sum(v/len(ks)*math.log2(v/len(ks)) for v in cnt.values())
print('ks entropy %.3f unique %d'%(H,len(cnt)))
# check if ks blocks repeat anywhere
blocks=[ks[i:i+16] for i in range(0,min(len(ks),1600),16)]
print('distinct 16B blocks',len(set(blocks)),'of',len(blocks))
