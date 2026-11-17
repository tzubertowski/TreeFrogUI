"""Host tests of the RAM guard's actual process orchestration; no block devices."""
from pathlib import Path
import shutil
import subprocess

import pytest

LAB = Path(__file__).resolve().parents[1]


@pytest.fixture
def guard(tmp_path):
    compiler = shutil.which("gcc")
    if not compiler:
        pytest.skip("host GCC unavailable")
    # The production helper needs Linux proc/MMIO headers; exercise its policy
    # without compiling any hardware access on the Windows host.
    program = tmp_path / "check.c"
    program.write_text('''
#include <assert.h>
#include "fat_boot_policy.h"
int main(void) {
    int i;
    assert(r36_fat_after_check(0,0) == R36_FAT_BOOT);
    assert(r36_fat_after_check(1,0) == R36_FAT_REPAIR);
    for (i=-2;i<256;i++) {
        if (i != 0 && i != 1) assert(r36_fat_after_check(i,0) == R36_FAT_STOP);
        assert(r36_fat_after_check(i,1) == R36_FAT_STOP);
        assert(!r36_fat_repair_may_verify(i,1));
        assert(!r36_fat_verified(i,1));
        assert(r36_fat_verified(i,0) == (i == 0));
        assert(r36_fat_repair_may_verify(i,0) == (i == 0 || i == 1));
    }
    return 0;
}
''')
    output = tmp_path / "policy.exe"
    subprocess.run([compiler, "-Wall", "-Wextra", "-Werror", "-I", str(LAB), str(program), "-o", str(output)],
                   check=True, capture_output=True, timeout=20)
    return output


def test_fail_closed_exit_policy(guard):
    subprocess.run([str(guard)], check=True, timeout=5)


def test_repair_has_no_immediate_write_or_forced_child_kill():
    source = (LAB / "fat_boot_guard.c").read_text()
    assert '"-a", "-f", device' in source
    assert '"-w"' not in source
    assert "SIGKILL" not in source and "SIGTERM" not in source
    assert '"-n", device' in source
    assert "metadata_snapshot(device)" in source
    assert "block_is_offline(device)" in source
    assert 'R36_FAT_ENABLE_REPAIR 0' in source
    assert 'matches != 1 || strcmp(last, expected)' in source
    assert source.index('pause_watchdog())') > source.index('case R36_FAT_REPAIR:')
