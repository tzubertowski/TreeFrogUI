from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/boot_crypto"))
import run_restored_cold_trial as trial

TRIAL_SOURCE = (ROOT / "scripts/boot_crypto/run_restored_cold_trial.py").read_text()
BACKUP_SOURCE = (ROOT / "scripts/boot_crypto/backup_cubegm.py").read_text()


class GoneTransport:
    """Probe succeeds, the poweroff command drops the link, the device is gone."""

    def __init__(self, probe_code=0):
        self.probe_code = probe_code
        self.commands = []

    def run(self, command, timeout=None):
        self.commands.append(command)
        if command == "command -v poweroff":
            return self.probe_code, b"/sbin/poweroff\n" if self.probe_code == 0 else b""
        if command in ("poweroff", "reboot -p"):
            raise RuntimeError("device disconnected while powering off")
        if command == "true":
            raise RuntimeError("R36S not found")
        raise AssertionError("unexpected command " + command)


class VanishedTransport:
    """The device is already unreachable when poweroff is requested."""

    def run(self, command, timeout=None):
        raise RuntimeError("R36S not found: put the console in USB (MTP) mode")


def test_trial_exposes_tests_only_poweroff_flags():
    assert '"--poweroff-on-completion"' in TRIAL_SOURCE
    assert '"--poweroff-after"' in TRIAL_SOURCE
    assert "default=0" in TRIAL_SOURCE
    assert "def poweroff_console(" in TRIAL_SOURCE
    assert 'record["poweroff_verified"]' in TRIAL_SOURCE
    assert "args.poweroff_on_completion or args.poweroff_after > 0" in TRIAL_SOURCE


def test_poweroff_immediate_records_method_and_verification(monkeypatch):
    monkeypatch.setattr(trial.time, "sleep", lambda _seconds: None)
    record = {"poweroff_requested": False}
    transport = GoneTransport()
    trial.poweroff_console(transport, record, started=trial.time.monotonic(), after_minutes=0)
    assert record["poweroff_requested"] is True
    assert record["poweroff_method"] == "poweroff"
    assert record["poweroff_verified"] is True
    assert "poweroff" in transport.commands


def test_poweroff_falls_back_when_poweroff_applet_missing(monkeypatch):
    monkeypatch.setattr(trial.time, "sleep", lambda _seconds: None)
    record = {"poweroff_requested": False}
    transport = GoneTransport(probe_code=1)
    trial.poweroff_console(transport, record, started=trial.time.monotonic(), after_minutes=0)
    assert record["poweroff_method"] == "reboot -p"
    assert "reboot -p" in transport.commands
    assert record["poweroff_verified"] is True


def test_poweroff_records_error_when_device_unreachable(monkeypatch):
    monkeypatch.setattr(trial.time, "sleep", lambda _seconds: None)
    record = {"poweroff_requested": False}
    trial.poweroff_console(VanishedTransport(), record, started=trial.time.monotonic(), after_minutes=0)
    assert record["poweroff_method"] is None
    assert record["poweroff_verified"] is False
    assert "not found" in record["poweroff_error"]


def test_poweroff_after_waits_until_deadline(monkeypatch):
    slept = []
    monkeypatch.setattr(trial.time, "sleep", slept.append)
    record = {"poweroff_requested": False}
    started = trial.time.monotonic()
    trial.poweroff_console(GoneTransport(), record, started=started, after_minutes=1)
    deadline_sleeps = [value for value in slept if value > 1]
    assert deadline_sleeps, "deadline wait did not sleep"
    assert abs(deadline_sleeps[0] - 60) < 5
    assert record["poweroff_verified"] is True


def test_poweroff_absent_from_accepted_payload_and_driver():
    for relative in ("payload/kernel_ready/tools/acceptance.py",
                     "payload/kernel_ready/tools/device_worker.py",
                     "payload/kernel_ready/START.py",
                     "scripts/peripheral_lab/video_drm_backend.c"):
        text = (ROOT / relative).read_text()
        assert "poweroff" not in text, relative


def test_backup_never_writes_to_the_console():
    assert "transport.put" not in BACKUP_SOURCE
    assert not re.search(r"\b(rm|dd|mv|swapoff|mount)\b", BACKUP_SOURCE)
    assert ">" not in backup_list_command()


def backup_list_command():
    return re.search(r'LIST_COMMAND = "([^"]+)"', BACKUP_SOURCE).group(1)
