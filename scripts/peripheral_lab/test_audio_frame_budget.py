from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_last_partial_write_cannot_overshoot_target(tmp_path):
    source = (ROOT / 'scripts/peripheral_lab/audio_probe.h').read_text()
    begin = source.index('        snd_pcm_uframes_t remaining =')
    end = source.index('        if (clock_gettime', begin)
    declarations = source[begin:end]
    c = tmp_path / 'budget.c'
    c.write_text('''
#include <assert.h>
#include <stddef.h>
typedef unsigned long snd_pcm_uframes_t;
struct snd_xferi { long result; void *buf; snd_pcm_uframes_t frames; };
static short silence[1024];
int main(void) {
    long frames=0;
    unsigned count=0;
    while (frames < 24576) {
''' + declarations + '''
        unsigned amount = count++ % 3 ? 512 : 104;
        assert(transfer.frames <= 512 && transfer.frames <= (unsigned long)(24576-frames));
        transfer.result = amount < transfer.frames ? amount : transfer.frames;
        frames += transfer.result;
    }
    assert(frames == 24576);
    return 0;
}
''')
    output = tmp_path / 'budget.exe'
    subprocess.run(['gcc','-Wall','-Wextra','-Werror',str(c),'-o',str(output)],check=True,timeout=20)
    subprocess.run([str(output)],check=True,timeout=5)


def test_audio_uses_elapsed_time_not_busy_retry_count():
    text = (ROOT / 'scripts/peripheral_lab/audio_probe.h').read_text()
    assert 'i < 256' not in text
    assert 'current.tv_sec - started.tv_sec >= 5' in text
    assert 'usleep(1000)' in text
