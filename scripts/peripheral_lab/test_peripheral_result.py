import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "boot_crypto"))
from peripheral_result import avp_result


def report(marker, run="new", complete=True):
    return (b"run_id=" + run.encode() + b"\nR36 AVP TRANSPORT PROBE V1\n" + marker + b"\nprobe_rc=0\n" +
            (b"R36 AVP PROBE END\n" if complete else b""))


def test_kernel_pass_does_not_count_as_userspace():
    result = avp_result(report(b"kernel_transport=PASS"), "new")
    assert result["kernel_verified"] and not result["userspace_verified"]


def test_userspace_pass_does_not_count_as_kernel():
    result = avp_result(report(b"transport=PASS"), "new")
    assert result["userspace_verified"] and not result["kernel_verified"]


def test_stale_or_incomplete_report_does_not_pass():
    for raw in (report(b"transport=PASS", run="old"), report(b"transport=PASS", complete=False)):
        result = avp_result(raw, "new")
        assert not result["userspace_verified"] and not result["kernel_verified"]


def test_mixed_pass_reports_are_rejected():
    result = avp_result(report(b"transport=PASS\nkernel_transport=PASS"), "new")
    assert result["ambiguous"] and not result["userspace_verified"] and not result["kernel_verified"]
