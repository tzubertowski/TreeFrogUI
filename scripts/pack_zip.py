#!/usr/bin/env python3
"""Create a ZIP whose paths are safe on case-insensitive filesystems."""
import os
import sys
import zipfile


def files_by_casefolded_path(root):
    selected = {}
    for directory, _, filenames in os.walk(root):
        for filename in filenames:
            path = os.path.join(directory, filename)
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            key = relative.casefold()
            current = selected.get(key)
            if current is None or os.stat(path).st_mtime_ns >= os.stat(current).st_mtime_ns:
                selected[key] = path
    return selected


def normalize_tree(root) -> None:
    selected = files_by_casefolded_path(root)
    for directory, _, filenames in os.walk(root):
        for filename in filenames:
            path = os.path.join(directory, filename)
            if selected[os.path.relpath(path, root).casefold()] != path:
                os.unlink(path)


def main() -> None:
    output, parent, entry = sys.argv[1:]
    root = os.path.join(parent, entry)
    archive_base = root if entry == "." else parent
    selected = files_by_casefolded_path(root)

    with zipfile.ZipFile(
        output, "w", zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=False
    ) as archive:
        # ZIP files do not retain directories automatically.  Keep every
        # directory entry, including empty ROM folders, so a fresh SD install
        # has the complete system layout before the user copies any games.
        directories = []
        for directory, dirnames, _ in os.walk(root):
            dirnames.sort()
            if directory == root:
                continue
            relative = os.path.relpath(directory, archive_base).replace(os.sep, "/")
            directories.append(relative.rstrip("/") + "/")
        for relative in sorted(directories, key=str.casefold):
            info = zipfile.ZipInfo(relative)
            info.external_attr = (0o40755 << 16) | 0x10
            archive.writestr(info, b"")
        for path in sorted(selected.values(), key=lambda item: os.path.relpath(item, parent).casefold()):
            archive.write(path, os.path.relpath(path, archive_base).replace(os.sep, "/"))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--normalize-tree":
        normalize_tree(sys.argv[2])
        raise SystemExit(0)
    if len(sys.argv) != 4:
        raise SystemExit("usage: pack_zip.py OUTPUT PARENT ENTRY (use ENTRY '.' to zip its contents)")
    main()
