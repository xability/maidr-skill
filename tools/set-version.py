#!/usr/bin/env python3
"""Write one release version into every place the plugin declares it.

semantic-release runs this in its prepare step (see .releaserc.json); CI checks
that the three places agree. Usage: python3 tools/set-version.py 1.2.3
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFESTS = [ROOT / ".claude-plugin" / "plugin.json", ROOT / "plugin.json"]
SKILL = ROOT / "skills" / "maidr" / "SKILL.md"


def main() -> None:
    if len(sys.argv) != 2 or not re.fullmatch(r"\d+\.\d+\.\d+", sys.argv[1]):
        sys.exit("usage: set-version.py X.Y.Z")
    version = sys.argv[1]

    for path in MANIFESTS:
        text = path.read_text(encoding="utf-8")
        new, count = re.subn(r'("version":\s*)"[^"]*"', rf'\g<1>"{version}"', text, count=1)
        if count != 1:
            sys.exit(f"{path.relative_to(ROOT)}: no \"version\" field to update")
        json.loads(new)
        path.write_text(new, encoding="utf-8")

    text = SKILL.read_text(encoding="utf-8")
    # The frontmatter's metadata.version, not maidr-js-version.
    new, count = re.subn(r'(?m)^(  version:\s*)"[^"]*"', rf'\g<1>"{version}"', text, count=1)
    if count != 1:
        sys.exit("skills/maidr/SKILL.md: no metadata.version to update")
    SKILL.write_text(new, encoding="utf-8")

    print(f"version {version} written")


if __name__ == "__main__":
    main()
