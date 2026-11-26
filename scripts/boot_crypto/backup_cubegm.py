"""Read-only host-side backup of the console SD folder /cubegm.

Regular files are listed with ls -laR, downloaded over the stock transport in
batched tar streams, hashed with sha256, and recorded in a manifest. The
script never writes to the console; the active swap file pagefile.sys is
skipped. Rerun with the same --dest to resume an interrupted backup.
"""
import argparse
import hashlib
import io
import json
import runpy
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REMOTE_ROOT = "/mnt/sdcard/cubegm"
SKIP = {"pagefile.sys": "active swap file; not user data"}
LIST_COMMAND = "ls -laR /mnt/sdcard/cubegm"
LIST_TIMEOUT = 300
MAX_BATCH_FILES = 60
MAX_BATCH_BYTES = 16 << 20
MAX_BATCH_CMD = 6000
TAR_TIMEOUT_BASE = 120
TAR_TIMEOUT_PER_MB = 30
RETRY_ATTEMPTS = 3
RETRY_DELAY = 10.0


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_rel(path):
    prefix = REMOTE_ROOT + "/"
    if not path.startswith(prefix):
        raise ValueError("unexpected remote path: " + path)
    rel = path[len(prefix):]
    parts = rel.split("/")
    if not rel or any(part in ("", ".", "..") for part in parts):
        raise ValueError("unsafe remote path: " + path)
    return rel


def should_skip(rel):
    return SKIP.get(rel)


def shell_quote(path):
    return "'" + path.replace("'", "'\\''") + "'"


def tar_command(rels):
    quoted = " ".join(shell_quote(rel) for rel in rels)
    return "tar -C " + REMOTE_ROOT + " -cf - " + quoted + " 2>/dev/null"


def parse_listing(raw):
    sizes = {}
    current = None
    for line in raw.decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        if line.startswith("/"):
            current = line.rstrip(":").strip()
            continue
        if current is None or line.startswith(("total ", "d")):
            continue
        if not line.startswith("-"):
            continue
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        rel = safe_rel(current.rstrip("/") + "/" + parts[8])
        sizes[rel] = int(parts[4])
    if not sizes:
        raise RuntimeError("remote file listing is empty")
    return sizes


def make_batches(rels, sizes):
    batches = []
    current = []
    current_bytes = 0
    current_cmd = len(tar_command([]))
    for rel in rels:
        size = sizes.get(rel, 0)
        extra = len(shell_quote(rel)) + 1
        if current and (len(current) >= MAX_BATCH_FILES or
                        current_bytes + size > MAX_BATCH_BYTES or
                        current_cmd + extra > MAX_BATCH_CMD):
            batches.append(current)
            current, current_bytes, current_cmd = [], 0, len(tar_command([]))
        current.append(rel)
        current_bytes += size
        current_cmd += extra
        if size >= MAX_BATCH_BYTES:
            batches.append(current)
            current, current_bytes, current_cmd = [], 0, len(tar_command([]))
    if current:
        batches.append(current)
    return batches


def extract_batch(data, dest, sizes, manifest, rels_expected):
    seen = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                rel = member.name
                if rel not in rels_expected:
                    raise RuntimeError("unexpected tar member: " + rel)
                expected = sizes.get(rel)
                if expected is not None and member.size != expected:
                    raise RuntimeError("size mismatch for %s: %d != %d" %
                                       (rel, member.size, expected))
                handle = tar.extractfile(member)
                content = handle.read() if handle else b""
                if expected is not None and len(content) != expected:
                    raise RuntimeError("truncated member " + rel)
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                manifest["files"][rel] = {"bytes": len(content),
                                          "sha256": sha256(content)}
                seen.add(rel)
    except tarfile.TarError as error:
        raise RuntimeError("tar stream damaged: %s" % error)
    missing = [rel for rel in rels_expected if rel not in seen]
    if missing:
        raise RuntimeError("batch missing %d file(s), first: %s" %
                           (len(missing), missing[0]))


def fetch_batch(transport, batch, sizes, dest, manifest, log=print):
    command = tar_command(batch)
    expected = sum(sizes.get(rel, 0) for rel in batch)
    timeout = TAR_TIMEOUT_BASE + (expected >> 20) * TAR_TIMEOUT_PER_MB
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            code, data = transport.run(command, timeout=timeout)
            if not data:
                raise RuntimeError("empty tar stream (rc=%s)" % code)
            if code:
                log("tar rc=%s for batch of %d, validating stream" %
                    (code, len(batch)))
            extract_batch(data, dest, sizes, manifest, batch)
            return
        except Exception as error:
            if attempt == RETRY_ATTEMPTS:
                raise
            log("batch attempt %d/%d failed (%s); retrying in %.0fs" %
                (attempt, RETRY_ATTEMPTS, error, RETRY_DELAY))
            time.sleep(RETRY_DELAY)


def run_command(transport, command, timeout, log=print):
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return transport.run(command, timeout=timeout)
        except Exception as error:
            if attempt == RETRY_ATTEMPTS:
                raise
            log("run attempt %d/%d failed (%s); retrying in %.0fs" %
                (attempt, RETRY_ATTEMPTS, error, RETRY_DELAY))
            time.sleep(RETRY_DELAY)


def save_manifest(dest, manifest):
    (dest / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def download(transport, rels, sizes, dest, *, limit=0, resume=True, log=print):
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(),
                "source": REMOTE_ROOT, "files": {}, "skipped": {},
                "complete": False,
                "transport": "stock shell run/tar batches"}
    manifest_path = dest / "manifest.json"
    prior = {}
    if resume and manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        prior = old.get("files", {})
    dest.mkdir(parents=True, exist_ok=True)
    selected = list(rels)
    if limit:
        selected = selected[:limit]
    kept = 0
    pending = []
    for rel in selected:
        reason = should_skip(rel)
        if reason:
            manifest["skipped"][rel] = reason
            continue
        target = dest / rel
        before = prior.get(rel)
        if (resume and before and target.exists() and
                target.stat().st_size == before["bytes"] and
                sha256_file(target) == before["sha256"]):
            manifest["files"][rel] = before
            kept += 1
            continue
        pending.append(rel)
    batches = make_batches(pending, sizes)
    started = time.monotonic()
    fetched = 0
    fetched_bytes = 0
    log("resume kept %d file(s); %d to fetch in %d batch(es)" %
        (kept, len(pending), len(batches)))
    for index, batch in enumerate(batches, 1):
        fetch_batch(transport, batch, sizes, dest, manifest, log=log)
        fetched += len(batch)
        fetched_bytes += sum(manifest["files"][rel]["bytes"] for rel in batch)
        save_manifest(dest, manifest)
        elapsed = time.monotonic() - started
        total_bytes = sum(entry["bytes"] for entry in manifest["files"].values())
        log("[batch %d/%d] +%d files (+%.1f MB) | %d fetched, %d kept | "
            "%.1f MB total, %.2f MB/s" %
            (index, len(batches), len(batch), fetched_bytes / 1e6,
             fetched, kept, total_bytes / 1e6,
             (fetched_bytes / 1e6 / elapsed) if elapsed else 0.0))
    manifest["complete"] = (limit == 0 and
                            len(manifest["files"]) + len(manifest["skipped"]) ==
                            len(rels))
    manifest["totals"] = {"files": len(manifest["files"]),
                          "bytes": sum(entry["bytes"]
                                       for entry in manifest["files"].values()),
                          "fetched": fetched, "kept": kept,
                          "skipped": len(manifest["skipped"]),
                          "batches": len(batches)}
    save_manifest(dest, manifest)
    return manifest


def keepawake(transport, action, log=print):
    command = "sh " + REMOTE_ROOT + "/r36_keepawake.sh " + action
    try:
        code, data = transport.run(command, timeout=30)
    except Exception as error:
        log("keepawake %s failed: %s" % (action, error))
        return
    log("keepawake %s: rc=%s %s" %
        (action, code, data.decode("utf-8", "replace").strip()))


def connect():
    runpy.run_path(str(ROOT / "payload/kernel_ready/START.py"),
                   run_name="backup_cubegm")
    return sys.modules["acceptance"].WorkerTransport()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=None,
                        help="backup directory "
                             "(default analysis/boot_crypto/backups/<UTC>_cubegm)")
    parser.add_argument("--limit", type=int, default=0,
                        help="only the first N files; for smoke runs (0=all)")
    args = parser.parse_args()
    if args.limit < 0:
        raise SystemExit("--limit must be zero or positive")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = args.dest or (ROOT / "analysis/boot_crypto/backups" /
                         (stamp + "_cubegm"))
    if dest.exists() and any(dest.iterdir()) and not (dest / "manifest.json").exists():
        raise SystemExit("destination exists without a manifest: " + str(dest))
    transport = connect()
    keepawake(transport, "start")
    try:
        code, raw = run_command(transport, LIST_COMMAND, LIST_TIMEOUT)
        if code:
            raise SystemExit("remote listing failed rc=%s" % code)
        sizes = parse_listing(raw)
        rels = sorted(sizes)
        print("remote files: %d (%.1f MB)" %
              (len(rels), sum(sizes.values()) / 1e6))
        manifest = download(transport, rels, sizes, dest, limit=args.limit)
        print(json.dumps({"dest": str(dest),
                          "complete": manifest["complete"],
                          "totals": manifest["totals"],
                          "skipped": manifest["skipped"]}, indent=2))
        if not manifest["complete"] and args.limit == 0:
            raise SystemExit("backup incomplete; rerun with the same --dest "
                             "to resume")
    finally:
        keepawake(transport, "stop")


if __name__ == "__main__":
    main()
