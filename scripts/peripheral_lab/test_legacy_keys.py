from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_union_of_sources_releases_and_repeat(tmp_path):
    source = tmp_path / "keys.c"
    source.write_text('''
#include <assert.h>
#include "legacy_keys.h"
static struct r36_key_bridge s;
int main(void) {
    s.mapping[10] = 1u << 14;
    s.mapping[11] = 1u << 14;
    s.mapping[12] = 1u << 4;
    assert(!r36_key_event(&s, 0, 10, 1));
    assert(r36_key_word(&s) == (1u << 14));
    assert(!r36_key_event(&s, 1, 10, 1));
    assert(!r36_key_event(&s, 0, 10, 0));
    assert(r36_key_word(&s) == (1u << 14));
    assert(!r36_key_event(&s, 1, 11, 1));
    assert(!r36_key_event(&s, 1, 10, 0));
    assert(r36_key_word(&s) == (1u << 14));
    assert(!r36_key_event(&s, 1, 12, 1));
    assert(r36_key_word(&s) == ((1u << 14) | (1u << 4)));
    assert(!r36_key_event(&s, 1, 12, 2));
    r36_key_clear(&s, 1); assert(r36_key_word(&s) == 0);
    assert(r36_key_event(&s, 16, 10, 1) == -1);
    assert(r36_key_event(&s, 0, 768, 1) == -1);
    assert(r36_key_event(&s, 0, 10, -1) == -1);
    return 0;
}
''')
    binary = tmp_path / "keys.exe"
    subprocess.run(["gcc", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "scripts/peripheral_lab"), str(source), "-o", str(binary)], check=True, timeout=20)
    subprocess.run([str(binary)], check=True, timeout=5)


def test_input_profile_excludes_dangerous_output_pins():
    text = (ROOT / "scripts/kernel_lab/r36-display-input.dts").read_text()
    assert '#include "r36-display.dts"' in text
    assert "gpio-keys-polled" in text and "poll-interval = <16>" in text
    assert "GPIO_OPEN_DRAIN" in text
    for pin in (0, 1, 3, 4, 5, 6, 19):
        assert f"<&gpio {pin} " not in text
    for i in range(1, 13):
        assert f"BTN_TRIGGER_HAPPY{i}>" in text
