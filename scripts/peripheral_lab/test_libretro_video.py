from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_formats_pitch_bounds_and_conversion(tmp_path):
    source = tmp_path / 'convert.c'
    source.write_text('''
#include <assert.h>
#include "libretro_video.h"
int main(void) {
    uint16_t out[4]={0}, in1555[2]={0x7c00,0x03e0}, in565[2]={0x1234,0xabcd};
    uint32_t in8888[2]={0x00ff0000,0x0000ff00};
    assert(!r36_libretro_to565(out,sizeof(out),in1555,2,1,4,0));
    assert(out[0]==0xf800 && out[1]==0x07e0);
    assert(!r36_libretro_to565(out,sizeof(out),in8888,2,1,8,1));
    assert(out[0]==0xf800 && out[1]==0x07e0);
    assert(!r36_libretro_to565(out,sizeof(out),in565,2,1,4,2));
    assert(out[0]==0x1234 && out[1]==0xabcd);
    assert(r36_libretro_to565(out,2,in8888,2,1,8,1)==-1);
    assert(r36_libretro_to565(out,8,in8888,2,1,7,1)==-1);
    assert(r36_libretro_to565(out,8,in8888,2,1,8,3)==-1);
    assert(r36_libretro_to565(NULL,8,in8888,2,1,8,1)==-1);
    for (unsigned int n=0;n<32768;n++) {
        uint16_t color=(uint16_t)n, value=0;
        unsigned int red=(n>>10)&31, green=(n>>5)&31, blue=n&31;
        uint16_t expected=(uint16_t)((red<<11)|((green*2+green/16)<<5)|blue);
        assert(!r36_libretro_to565(&value,2,&color,1,1,2,0));
        assert(value==expected);
    }
    return 0;
}
''')
    binary = tmp_path / 'convert.exe'
    subprocess.run(['gcc','-Wall','-Wextra','-Werror','-I',str(ROOT/'scripts/peripheral_lab'),str(source),'-o',str(binary)],check=True,timeout=20)
    subprocess.run([str(binary)],check=True,timeout=5)
