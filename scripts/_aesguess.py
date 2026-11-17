import itertools
S=[0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76]
# full sbox generated from the standard algorithm to avoid typing errors
def gen_sbox():
    p=1;q=1;sbox=[0]*256
    while True:
        p = p ^ ((p<<1)&0xff) ^ (0x1b if p&0x80 else 0)
        q ^= q<<1; q ^= q<<2; q ^= q<<4; q &= 0xff
        if q&0x80: q ^= 0x09
        x = q ^ ((q<<1)|(q>>7)) ^ ((q<<2)|(q>>6)) ^ ((q<<3)|(q>>5)) ^ ((q<<4)|(q>>4))
        sbox[p] = (x ^ 0x63) & 0xff
        if p==1: break
    sbox[0]=0x63
    return sbox
SB=gen_sbox()
def xt(a): return ((a<<1)^0x1b)&0xff if a&0x80 else a<<1
def expand(key):
    nk=len(key)//4; nr=nk+6
    w=[list(key[4*i:4*i+4]) for i in range(nk)]
    rcon=1
    for i in range(nk,4*(nr+1)):
        t=list(w[i-1])
        if i%nk==0:
            t=t[1:]+t[:1]
            t=[SB[b] for b in t]
            t[0]^=rcon
            rcon=xt(rcon)
        elif nk>6 and i%nk==4:
            t=[SB[b] for b in t]
        w.append([w[i-nk][j]^t[j] for j in range(4)])
    return w,nr
def enc(key,block):
    w,nr=expand(key)
    s=[block[i]^w[i//4][i%4] for i in range(16)]
    for r in range(1,nr+1):
        s=[SB[b] for b in s]
        s=[s[(i+4*(i%4))%16] for i in range(16)]
        if r!=nr:
            for c in range(4):
                a=s[4*c:4*c+4]
                s[4*c+0]=xt(a[0])^xt(a[1])^a[1]^a[2]^a[3]
                s[4*c+1]=a[0]^xt(a[1])^xt(a[2])^a[2]^a[3]
                s[4*c+2]=a[0]^a[1]^xt(a[2])^xt(a[3])^a[3]
                s[4*c+3]=xt(a[0])^a[0]^a[1]^a[2]^xt(a[3])
        s=[s[i]^w[4*r+i//4][i%4] for i in range(16)]
    return bytes(s)
c=open(r'D:\r36s-\analysis\card2_files\cubegm_enc\driver.so','rb').read()
q=open(r'D:\r36s-\dumpcard\dump_out\file_driver.so','rb').read()
nonce=c[:12]; size=int.from_bytes(c[12:16],'little'); ct=c[16:]; pt=q
ks0=bytes(a^b for a,b in zip(ct[:16],pt[:16]))
print('target ks0',ks0.hex())
ivs={
 'n+BE0':nonce+b'\0\0\0\0',
 'n+LE0':nonce+b'\0\0\0\0',
 'n+sizeLE':nonce+size.to_bytes(4,'little'),
 'n+sizeBE':nonce+size.to_bytes(4,'big'),
 '0000+n':b'\0\0\0\0'+nonce,
 'n+1BE':nonce+b'\0\0\0\1',
 'c0_16':c[:16],
}
words=['','hichip','Hichip','HICHIP','hichip,dsc','hc16xx','HC16E3100V20','cubegm','SF3000','sf3000','r36sx','rkgame','H.OS','hicorp','hichip2000','hichipdsc','HC1600','hc1600','R36S','r36s','game','Game','hongchips','HC']
keys=[]
for w in words:
    b=w.encode()
    for n in (16,24,32):
        for mode in ('zpad','rep'):
            if not b:
                k=b'\0'*n
            elif mode=='zpad': k=(b+b'\0'*n)[:n]
            else: k=(b*((n//len(b))+1))[:n]
            keys.append((f'{w or "zero"}/{n}/{mode}',k))
for kk in (b'\0'*16,b'\0'*24,b'\0'*32,b'\xff'*16,b'\xff'*32,b'\x01'*16):
    keys.append(('const'+kk.hex()[:8],kk))
seen=set(); keys=[x for x in keys if not (x in seen or seen.add(x))]
hit=False
for name,key in keys:
    for ivn,iv in ivs.items():
        if enc(key,iv)==ks0:
            print('MATCH key=%s iv=%s'%(name,ivn)); hit=True
print('done, hit=',hit,'tested',len(keys)*len(ivs))
