"""Stage a narrowly patched dosfstools for RAM-only boot checks in a NEW directory.

The downloaded archive is never imported as Python. No tool is built or executed
by this script. Original GPL notices and sources remain with the staged tree.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

ARCHIVE_SHA = "64926eebf90092dca21b14259a5301b7b98e7b1943e8a201c7d726084809b527"
ROOT = Path(__file__).resolve().parents[2]


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError("source fingerprint differs: " + before[:80])
    return text.replace(before, after, 1)


def stage(archive, output):
    archive, output = Path(archive), Path(output)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError("unexpected upstream archive hash")
    output.mkdir(exist_ok=False)
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            parts = Path(member.name).parts
            if not parts or parts[0] != "dosfstools-4.2" or ".." in parts or member.issym() or member.islnk():
                raise ValueError("unsafe archive member")
        bundle.extractall(output, filter="data")
    source = output / "dosfstools-4.2"
    charconv = source / "src/charconv.c"
    text = charconv.read_text()
    begin = text.index("static const wchar_t cp850_table[128] = {")
    end = text.index("};", begin) + 2
    table = "static const wchar_t cp437_table[128] = {\n"
    for offset in range(0x80, 0x100, 8):
        table += "    " + ", ".join(f"0x{ord(bytes([i]).decode('cp437')):04x}" for i in range(offset, offset + 8)) + ",\n"
    table += "};"
    text = text[:begin] + table + text[end:]
    text = text.replace("cp850", "cp437").replace("CP850", "CP437").replace("== 850", "== 437")
    text = text.replace("only codepage 850 is supported", "only codepage 437 is supported")
    # Transliterated diagnostics are not filesystem data. Avoid CP850-specific
    # transliterations after replacing the actual lossless conversion table.
    begin = text.index("static const char *const cp437_translit_table[128] = {")
    end = text.index("};", begin) + 2
    text = text[:begin] + 'static const char *const cp437_translit_table[128] = {\n' + ',\n'.join(
        '    ' + ', '.join('"?"' for _ in range(8)) for _ in range(16)) + '\n};' + text[end:]
    text = once(text, "unsigned i, j;\n    for", "unsigned i, j;\n    if (!out_size) return 0;\n    for")
    # Upstream's fallback takes byte capacity, as the iconv path does. Convert
    # bytes to wchar_t elements instead of treating it as an element count.
    text = once(text, "unsigned i;\n    for (i = 0; i < out_size-1", "unsigned i;\n    out_size /= sizeof(*out);\n    if (!out_size) return 0;\n    for (i = 0; i < out_size-1")
    text = once(text, "*(*p++) = c;", "*(*p)++ = c;")
    charconv.write_text(text, encoding="utf-8")
    header = source / "src/charconv.h"
    header.write_text(once(header.read_text(), "#define DEFAULT_DOS_CODEPAGE 850", "#define DEFAULT_DOS_CODEPAGE 437"), encoding="utf-8")
    common = source / "src/common.c"
    text = common.read_text()
    # Fatal I/O/memory failures must not share 'changes found' exit status 1.
    if text.count("exit(1);") != 3:
        raise ValueError("unexpected fatal status source")
    common.write_text(text.replace("exit(1);", "exit(8);"), encoding="utf-8")
    io = source / "src/io.c"
    text = io.read_text()
    start, end = text.index("static void fs_flush(void)"), text.index("int fs_close(int write)")
    flush = '''static void fs_flush(void)
{
    CHANGE *this;
    while (changes) {
        this = changes;
        changes = changes->next;
        if (lseek(fd, this->pos, 0) != this->pos)
            pdie("r36 fs_flush seek");
        if (write(fd, this->data, this->size) != this->size)
            pdie("r36 fs_flush write");
        free(this->data);
        free(this);
    }
}

'''
    text = text[:start] + flush + text[end:]
    text = once(text, '    if (close(fd) < 0)\n\tpdie("closing filesystem");',
                '    if (write && fsync(fd) < 0)\n        pdie("syncing filesystem");\n    if (close(fd) < 0)\n\tpdie("closing filesystem");')
    io.write_text(text, encoding="utf-8")
    main = source / "src/fsck.fat.c"
    text = once(main.read_text(), '    return fs_close(rw) ? 1 : 0;', '''    c = fs_close(rw) ? 1 : 0;
    printf("R36_FSCK_COMPLETE_V1 mode=%s status=%d\\n", rw ? "repair" : "check", c);
    if (fflush(stdout) || ferror(stdout)) return 8;
    return c;''')
    main.write_text(text, encoding="utf-8")
    receipt = {"upstream": "dosfstools 4.2", "archive_sha256": ARCHIVE_SHA,
               "codepage": 437, "build_requires": "--without-iconv; _FILE_OFFSET_BITS=64",
               "normal_exit": {"0": "no changes", "1": "check completed, changes detected or written"},
               "fatal_exit": 8, "completion_marker": "R36_FSCK_COMPLETE_V1 after fs_close/fsync",
               "hardware_verified": False, "production_enabled": False,
               "patches": {name: hashlib.sha256((source / 'src' / name).read_bytes()).hexdigest()
                           for name in ('charconv.c', 'charconv.h', 'common.c', 'io.c', 'fsck.fat.c')}}
    (output / "patch_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT / "modbuild/dosfstools-4.2.tar.gz")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.archive, args.out), indent=2))
