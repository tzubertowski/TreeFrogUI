#!/usr/bin/env python3
"""Create a ZIP whose paths are safe on case-insensitive filesystems."""
import os
import sys
import zipfile


def main() -> None:
    output, parent, entry = sys.argv[1:]
    root = os.path.join(parent, entry)
    selected = {}

    for directory, _, filenames in os.walk(root):
        for filename in filenames:
            path = os.path.join(directory, filename)
            relative = os.path.relpath(path, parent).replace(os.sep, "/")
            key = relative.casefold()
            current = selected.get(key)
            if current is None or os.stat(path).st_mtime_ns >= os.stat(current).st_mtime_ns:
                selected[key] = path

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(selected.values(), key=lambda item: os.path.relpath(item, parent).casefold()):
            archive.write(path, os.path.relpath(path, parent).replace(os.sep, "/"))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: pack_zip.py OUTPUT PARENT ENTRY")
    main()
