#!/usr/bin/env python3
"""Zip the plugin the way the OpenAI plugin directory takes it as an upload.

semantic-release runs this in its prepare step, after tools/set-version.py, and
attaches the result to the GitHub release. Only what an installed plugin reads
goes in: the portable manifest, its listing assets, the skill, README and
LICENSE; tests, evals, CI and tools stay out.
Usage: python3 tools/package-plugin.py dist/maidr-plugin-1.2.3.zip
"""
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
INCLUDE = ["plugin.json", "assets", "skills", "README.md", "LICENSE"]
SKIP_DIRS = {"__pycache__"}


def files():
    for name in INCLUDE:
        path = ROOT / name
        if path.is_file():
            yield path
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and not SKIP_DIRS.intersection(child.relative_to(ROOT).parts):
                    yield child
        else:
            sys.exit(f"{name} is missing")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: package-plugin.py OUT.zip")
    out = pathlib.Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files():
            zf.write(path, path.relative_to(ROOT).as_posix())
            count += 1
    print(f"{out}: {count} files")


if __name__ == "__main__":
    main()
