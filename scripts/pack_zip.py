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
    selected = files_by_casefolded_path(root)

    with zipfile.ZipFile(
        output, "w", zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=False
    ) as archive:
        for path in sorted(selected.values(), key=lambda item: os.path.relpath(item, parent).casefold()):
            archive.write(path, os.path.relpath(path, parent).replace(os.sep, "/"))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--normalize-tree":
        normalize_tree(sys.argv[2])
        raise SystemExit(0)
    if len(sys.argv) != 4:
        raise SystemExit("usage: pack_zip.py OUTPUT PARENT ENTRY")
    main()
