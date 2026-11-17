from pathlib import Path
import subprocess
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_synthetic_roms import gameboy, nes

ROOT = Path(__file__).resolve().parents[2]


def test_synthetic_cartridges_have_valid_headers_and_entry_vectors():
    gb = gameboy()
    assert len(gb) == 32768 and gb[0x100:0x104] == bytes([0, 0xc3, 0x50, 1])
    value = 0
    for b in gb[0x134:0x14d]: value = (value - b - 1) & 255
    assert gb[0x14d] == value
    assert int.from_bytes(gb[0x14e:0x150], 'big') == (sum(gb[:0x14e]) + sum(gb[0x150:])) & 65535
    n = nes()
    assert len(n) == 16 + 16384 + 8192
    assert n[:6] == b'NES\x1a\x01\x01'
    assert n[16 + 0x3ffa:16 + 0x4000] == bytes([0, 0x80] * 3)
    assert gameboy() == gb and nes() == n


def test_all_legacy_joypad_buttons_and_chords(tmp_path):
    c = tmp_path / 'joy.c'
    c.write_text('''
#include <assert.h>
#include "legacy_joypad.h"
int main(void) {
    unsigned int i;
    const unsigned int bits[12] = {14,15,0,3,4,6,7,5,13,12,10,11};
    assert(r36_legacy_to_libretro(0)==0);
    for (i=0;i<12;i++) assert(r36_legacy_to_libretro(1u<<bits[i])==(1u<<i));
    assert(r36_legacy_to_libretro(0xffffffffu)==0xfff);
    assert(r36_legacy_to_libretro((1u<<13)|(1u<<4))==((1u<<8)|(1u<<4)));
    assert(r36_legacy_to_libretro(1u<<31)==0);
    return 0;
}
''')
    binary = tmp_path / 'joy.exe'
    subprocess.run(['gcc', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT / 'scripts/peripheral_lab'), str(c), '-o', str(binary)], check=True, timeout=20)
    subprocess.run([str(binary)], check=True, timeout=5)


def test_real_emulator_suite_preserves_strict_acceptance():
    harness = (ROOT / 'scripts/peripheral_lab/libretro_smoke.c').read_text()
    assert 'r36_legacy_to_libretro' in harness
    assert 'retro_serialize(snapshot, size)' in harness
    assert 'retro_unserialize(snapshot, size)' in harness
    assert 'press != (unsigned)!neutral' in harness
    assert '!audio_nonzero' in harness
    assert 'hardware_or_real_game_verified=0' in harness
