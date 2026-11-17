import io
import shlex
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/boot_crypto"))
import backup_cubegm as backup


def build_tar(rels, files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for rel in rels:
            body = files[rel]
            info = tarfile.TarInfo(rel)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


class FakeTransport:
    def __init__(self, files):
        self.files = dict(files)
        self.tar_calls = []

    def run(self, command, timeout=None):
        if command.startswith("tar -C ") and " -cf - " in command:
            body = command[len("tar -C "):]
            _, rest = body.split(" -cf - ", 1)
            assert rest.endswith(" 2>/dev/null")
            rels = shlex.split(rest[: -len(" 2>/dev/null")])
            self.tar_calls.append(rels)
            present = [rel for rel in rels if rel in self.files]
            missing = [rel for rel in rels if rel not in self.files]
            return (1 if missing else 0), build_tar(present, self.files)
        if command.startswith("sh /mnt/sdcard/cubegm/r36_keepawake.sh"):
            return 0, b"ok"
        return 1, b"unexpected command: " + command.encode("utf-8")


def test_skip_is_only_the_active_swap_file():
    assert backup.should_skip("pagefile.sys")
    assert backup.should_skip("saves/pagefile.sys") is None
    assert backup.should_skip("setting.xml") is None


def test_safe_rel_rejects_traversal_and_foreign_paths():
    assert backup.safe_rel("/mnt/sdcard/cubegm/saves/x.srm") == "saves/x.srm"
    for bad in ("/mnt/sdcard/cubegm/../evil", "/mnt/sdcard/cubegm//x", "/media/mmc/x"):
        try:
            backup.safe_rel(bad)
        except ValueError:
            continue
        raise AssertionError("accepted unsafe path " + bad)


def test_commands_carry_no_shell_redirect():
    assert ">" not in backup.LIST_COMMAND
    command = backup.tar_command(["a b.txt"])
    assert command.endswith(" 2>/dev/null")
    assert ">" not in command[: -len(" 2>/dev/null")]


def test_parse_listing_reads_sizes():
    raw = (b"/mnt/sdcard/cubegm:\n"
           b"total 10\n"
           b"drwxrwxrwx    2 root     root        32768 Jan  1  1970 .\n"
           b"drwxrwxrwx    2 root     root        32768 Jan  1  1970 ..\n"
           b"-rwxrwxrwx    1 root     root           650 Apr  8  2026 AcXtrnal\n"
           b"drwxrwxrwx    2 root     root        32768 Jan  1  1970 saves\n"
           b"\n"
           b"/mnt/sdcard/cubegm/saves:\n"
           b"total 40\n"
           b"-rw-r--r--    1 root     root         1234 Jan  1  2026 foo bar.srm\n"
           b"-rw-r--r--    1 root     root     134217728 Jan  1  2026 pagefile.sys\n")
    sizes = backup.parse_listing(raw)
    assert sizes == {"AcXtrnal": 650, "saves/foo bar.srm": 1234,
                     "saves/pagefile.sys": 134217728}
    try:
        backup.parse_listing(b"")
    except RuntimeError:
        pass
    else:
        raise AssertionError("empty listing was accepted")


def test_make_batches_respects_limits():
    sizes = {}
    rels = []
    for index in range(200):
        rel = "f%03d.bin" % index
        rels.append(rel)
        sizes[rel] = 1000
    batches = backup.make_batches(rels, sizes)
    assert sum(len(batch) for batch in batches) == 200
    for batch in batches:
        assert len(batch) <= backup.MAX_BATCH_FILES
        assert sum(sizes[rel] for rel in batch) <= backup.MAX_BATCH_BYTES
    sizes = {"big%02d.bin" % index: 5 << 20 for index in range(10)}
    batches = backup.make_batches(sorted(sizes), sizes)
    for batch in batches:
        total = sum(sizes[rel] for rel in batch)
        assert total <= backup.MAX_BATCH_BYTES or len(batch) == 1
    sizes = {"huge.bin": 40 << 20, "a.txt": 1}
    assert backup.make_batches(["huge.bin", "a.txt"], sizes) == [["huge.bin"], ["a.txt"]]


def test_download_writes_files_and_manifest(tmp_path):
    files = {"a.txt": b"hello", "sub/b.bin": bytes(range(256))}
    transport = FakeTransport(files)
    sizes = {"a.txt": 5, "sub/b.bin": 256, "pagefile.sys": 100}
    manifest = backup.download(transport, sorted(sizes), sizes, tmp_path,
                               resume=False, log=lambda *_: None)
    assert manifest["complete"] is True
    assert manifest["skipped"] == {"pagefile.sys": backup.SKIP["pagefile.sys"]}
    assert (tmp_path / "a.txt").read_bytes() == b"hello"
    assert (tmp_path / "sub/b.bin").read_bytes() == bytes(range(256))
    assert manifest["files"]["a.txt"] == {"bytes": 5,
                                          "sha256": backup.sha256(b"hello")}
    assert sorted(sum(transport.tar_calls, [])) == ["a.txt", "sub/b.bin"]


def test_download_resume_keeps_verified_files(tmp_path):
    files = {"a.txt": b"hello"}
    sizes = {"a.txt": 5}
    first = FakeTransport(files)
    backup.download(first, sorted(sizes), sizes, tmp_path,
                    resume=False, log=lambda *_: None)
    second = FakeTransport(files)
    manifest = backup.download(second, sorted(sizes), sizes, tmp_path,
                               resume=True, log=lambda *_: None)
    assert second.tar_calls == []
    assert manifest["totals"]["kept"] == 1
    assert manifest["complete"] is True


def test_download_reports_missing_files(tmp_path):
    delay = backup.RETRY_DELAY
    backup.RETRY_DELAY = 0
    try:
        sizes = {"missing.txt": 4}
        try:
            backup.download(FakeTransport({}), ["missing.txt"], sizes, tmp_path,
                            resume=False, log=lambda *_: None)
        except RuntimeError as error:
            assert "missing.txt" in str(error)
            return
        raise AssertionError("missing file was not reported")
    finally:
        backup.RETRY_DELAY = delay


def test_fetch_batch_retries_after_transport_error(tmp_path):
    delay = backup.RETRY_DELAY
    backup.RETRY_DELAY = 0

    class Flaky(FakeTransport):
        def __init__(self, files):
            super().__init__(files)
            self.failures = 1

        def run(self, command, timeout=None):
            if command.startswith("tar -C ") and self.failures:
                self.failures -= 1
                raise RuntimeError("mtp glitch")
            return super().run(command, timeout)

    try:
        transport = Flaky({"a.txt": b"hello"})
        manifest = {"files": {}}
        backup.fetch_batch(transport, ["a.txt"], {"a.txt": 5}, tmp_path,
                           manifest, log=lambda *_: None)
        assert (tmp_path / "a.txt").read_bytes() == b"hello"
        assert transport.failures == 0
        assert manifest["files"]["a.txt"]["bytes"] == 5
    finally:
        backup.RETRY_DELAY = delay
