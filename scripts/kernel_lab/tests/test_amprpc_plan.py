from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emulate_amprpc import DO_MSG, RELEASE, ROOT

ISR_DIGEST = "246faca5f691e5160502c6893bb1768f51ca78c69c2b852479952024e5e5e6d4"


@pytest.fixture(scope="module")
def stock():
    # Keep Unicorn's native Windows exception handlers out of the pytest process.
    # Produce the reference by executing real code, not by trusting an old report.
    import json
    script = '''
import json
from emulate_amprpc import ROOT, suite, run_case
image = (ROOT / "analysis/kmem/kernel_80000000.bin").read_bytes()
report = suite(image)
comparisons = []
for index in range(8):
    for config in (0, 3, 0x80000002):
        statuses = [0] * 8
        statuses[index] = config | (0x10000 if index < 4 else 0x100)
        comparisons.append([index, config, run_case(image, statuses)])
print(json.dumps({"suite": report, "comparisons": comparisons}))
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT / "scripts/kernel_lab",
                            check=True, capture_output=True, text=True, timeout=60)
    assert "Windows fatal exception" not in result.stderr, result.stderr
    report = json.loads(result.stdout)
    assert report["suite"]["isr_sha256"] == ISR_DIGEST
    return report


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    gcc = shutil.which("gcc")
    if gcc is None:
        pytest.skip("host GCC is required for the portable C planner")
    out = tmp_path_factory.mktemp("amprpc_c") / "plan.exe"
    subprocess.run([gcc, "-std=c99", "-Wall", "-Wextra", "-Werror",
                    str(Path(__file__).with_name("amprpc_plan_harness.c")), "-o", str(out)],
                   check=True, capture_output=True, timeout=30)
    return out


def plan(harness, index, status, payload):
    result = subprocess.run([str(harness), str(index), hex(status), hex(payload)],
                            check=True, capture_output=True, text=True, timeout=5)
    return list(map(int, result.stdout.split()))


def test_actual_stock_isr_cases(stock):
    result = stock["suite"]
    assert result["passed"]
    assert len(result["cases"]) == 13
    assert result["isr_sha256"] == ISR_DIGEST


@pytest.mark.parametrize("index", range(8))
@pytest.mark.parametrize("config", [0, 3, 0x80000002])
def test_c_plan_matches_actual_stock_isr(harness, stock, index, config):
    pending = 0x10000 if index < 4 else 0x100
    status = [0] * 8
    status[index] = config | pending
    result = next(r for i, c, r in stock["comparisons"] if i == index and c == config)
    payload = 0xA2200000 + max(0, index - 4) * 0x1000
    action, argument, acknowledge, clear, release = plan(harness, index, status[index], payload)
    assert result["returned"]
    assert result["acknowledgements"] == [{"mailbox": index, "write": acknowledge}]
    assert result["queued"] == [{"function": hex(RELEASE if index < 4 else DO_MSG),
                                 "argument": hex(argument)}]
    if index < 4:
        assert action == 1 and argument == index and clear == release == 0
    else:
        assert action == 2 and argument == payload and clear == release == 1
        assert {"address": hex(0x18866800 + index * 0x20 + 12), "value": 0} in result["writes"]
        assert {"address": hex(0x18800800 + index * 0x20 + 4), "value": 1} in result["writes"]


@pytest.mark.parametrize("index", range(8))
def test_unexpected_bits_fail_closed(harness, index):
    wrong = 0x100 if index < 4 else 0x10000
    assert plan(harness, index, wrong, 0xDEADBEEF) == [4, 0, 0, 0, 0]
    assert plan(harness, index, 0x10100, 0xDEADBEEF) == [4, 0, 0, 0, 0]


def test_idle_and_invalid_indices(harness):
    for index in range(8):
        assert plan(harness, index, 3, 0) == [0, 0, 0, 0, 0]
    assert plan(harness, 8, 0x100, 0) == [3, 0, 0, 0, 0]
