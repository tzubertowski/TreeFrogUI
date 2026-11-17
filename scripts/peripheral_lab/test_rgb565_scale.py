from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_real_scale_padding_letterbox_and_invalid_inputs(tmp_path):
    c = tmp_path / "scale.c"
    c.write_text('''
#include <assert.h>
#include <stdlib.h>
#include "rgb565_scale.h"
static unsigned char out[1344 * 480 + 32];
int main(void) {
    unsigned char src[8 * 4];
    unsigned int y;
    memset(src, 0xa5, sizeof(src));
    for (y=0;y<4;y++) { src[y*8]=0x34; src[y*8+1]=0x12; src[y*8+2]=0xcd; src[y*8+3]=0xab; }
    memset(out,0x77,sizeof(out));
    assert(!r36_scale565(out,1344,src,2,4,8));
    assert(out[0]==0 && out[1]==0); /* portrait input letterboxed */
    assert(out[200*2]==0x34 && out[200*2+1]==0x12);
    assert(out[320*2]==0xcd && out[320*2+1]==0xab);
    for (y=0;y<480;y++) assert(out[y*1344+1280]==0x77);
    assert(out[1344*480]==0x77);
    assert(r36_scale565(out,1280,src,0,4,8)==-1);
    assert(r36_scale565(out,1280,src,2,4,3)==-1);
    assert(r36_scale565(out,1279,src,2,4,8)==-1);
    assert(r36_scale565(out,1280,NULL,2,4,8)==-1);
    return 0;
}
''')
    out = tmp_path / "scale.exe"
    subprocess.run(["gcc", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "scripts/peripheral_lab"), str(c), "-o", str(out)], check=True, timeout=20)
    subprocess.run([str(out)], check=True, timeout=5)
