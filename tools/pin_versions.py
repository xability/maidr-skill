#!/usr/bin/env python3
"""Rewrite the maidr.js version pins, and nothing else that names a version.

    python3 tools/pin_versions.py check VERSION
    python3 tools/pin_versions.py rewrite OLD NEW

tools/update-bundle.sh runs `rewrite` once it has vendored NEW. It used to replace every exact
match of OLD across the skill, README.md and AGENTS.md, which also moved the statements that say
when something arrived: "hoverMode needs maidr.js after 4.14.0" became "after 4.15.0" (a release
that already shipped it), and "4.x releases before 4.10.0 highlight nothing" read "before 4.15.0"
four refreshes later. So a version is rewritten only where it stands in one of the forms in PINS,
which name the vendored release by construction: a CDN URL, a constant, a heading.

Every other occurrence of the vendored version must be history, declared in HISTORY, or the
command refuses before it writes anything, so a new pin in an unknown form, or a history statement
that happens to name the vendored release, is a decision for a person rather than a guess. `check`
runs the same classification without writing; tests/test_pin_versions.py runs it on the tree and
fails when anything is left over.
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where pins live: the skill and the two top-level documents that name the vendored release.
SCAN = ("skills/maidr", "README.md", "AGENTS.md")
# Files that are the release itself, or that update-bundle.sh writes on its own.
SKIP_FILES = {"maidr.js", "maidr-math.css", "maidr-bundle.json"}
SKIP_DIRS = {"__pycache__"}

# Each form names the vendored release; "{v}" stands for the version. Add a form here when a new
# place pins the release, rather than writing the version where only a person can tell it apart.
PINS = (
    "maidr@{v}",                        # jsDelivr URLs (SKILL.md, references, assets)
    "/libs/maidr/{v}/",                 # cdnjs URLs
    'maidr-js-version: "{v}"',          # SKILL.md frontmatter
    'MAIDR_VERSION = "{v}"',            # scripts/check_maidr_html.py
    'MAIDR_JS_VERSION="{v}"',           # scripts/detect_env.sh
    '$MaidrJsVersion = "{v}"',          # scripts/detect_env.ps1
    'DEFAULT_VERSION = "{v}"',          # scripts/to_artifact.py
    "npm package `maidr` {v},",         # references/javascript.md, first line
    "with `{v}` replaced by",           # references/javascript.md, loading table
    "# MAIDR JSON schema (maidr {v})",  # references/schema.md title
    'set_cdn_version("{v}"',            # references/python.md
    "MAIDR_CDN_VERSION={v}|",           # references/python.md
    'a version such as `"{v}"`',        # references/r.md, maidr.cdn_version
    "vendored maidr.js {v} ",           # README.md layout
    "Current pins: maidr.js {v},",      # AGENTS.md
)

# Statements about a past release that name the vendored version, as (path, exact phrase). They
# are never rewritten. A phrase that names another version needs no entry: only the vendored
# version is ever rewritten. Prefer naming the release by what it is about ("after 4.14.0",
# "4.10.0 and later"), which does not change when the pin does.
HISTORY: tuple[tuple[str, str], ...] = ()


def _version_re(version: str) -> str:
    return r"(?<![0-9.])" + re.escape(version) + r"(?![0-9])(?!\.[0-9])"


def _pin_res(version: str) -> list[re.Pattern[str]]:
    out = []
    for form in PINS:
        before, after = form.split("{v}")
        out.append(re.compile(re.escape(before) + "(" + re.escape(version) + r")(?![0-9])(?!\.[0-9])"
                              + re.escape(after)))
    return out


def pin_spans(text: str, version: str) -> list[tuple[int, int]]:
    """Spans of `version` where it stands in a pin form."""
    spans = {m.span(1) for pattern in _pin_res(version) for m in pattern.finditer(text)}
    return sorted(spans)


def history_spans(text: str, rel: str, history=None) -> list[tuple[int, int]]:
    spans = []
    for path, phrase in (HISTORY if history is None else history):
        if path == rel:
            spans += [(m.start(), m.end()) for m in re.finditer(re.escape(phrase), text)]
    return spans


def unclassified(text: str, version: str, rel: str = "", history=None) -> list[int]:
    """Offsets of `version` that are neither a pin nor inside a declared history phrase."""
    pins = pin_spans(text, version)
    hist = history_spans(text, rel, history)
    out = []
    for m in re.finditer(_version_re(version), text):
        if m.span() in pins:
            continue
        if any(start <= m.start() and m.end() <= end for start, end in hist):
            continue
        out.append(m.start())
    return out


def rewrite_text(text: str, old: str, new: str) -> str:
    """`text` with the pinned `old` replaced by `new`, and nothing else changed."""
    for start, end in reversed(pin_spans(text, old)):
        text = text[:start] + new + text[end:]
    return text


def files(root: str = ROOT):
    """(relative path, absolute path) of every text file update-bundle.sh pins in."""
    for entry in SCAN:
        path = os.path.join(root, entry)
        if os.path.isfile(path):
            yield entry, path
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for name in sorted(filenames):
                if name in SKIP_FILES:
                    continue
                full = os.path.join(dirpath, name)
                yield os.path.relpath(full, root).replace(os.sep, "/"), full


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read()
    except UnicodeDecodeError:
        return None


def problems(version: str, root: str = ROOT, history=None) -> list[str]:
    """Every occurrence of `version` that is not a pin, and every declared phrase that is gone."""
    out = []
    history = HISTORY if history is None else history
    for rel, path in files(root):
        text = _read(path)
        if text is None:
            continue
        for offset in unclassified(text, version, rel, history):
            line = text.count("\n", 0, offset) + 1
            col = offset - (text.rfind("\n", 0, offset) + 1)
            snippet = text[max(0, offset - 50):offset + len(version) + 30].replace("\n", " ")
            out.append(f"{rel}:{line}:{col + 1}: {version} is neither a pin nor declared history: ...{snippet}...")
    for rel, phrase in history:
        path = os.path.join(root, rel)
        text = _read(path) if os.path.isfile(path) else None
        if text is None or phrase not in text:
            out.append(f"{rel}: declared history phrase not found: {phrase!r}")
        elif any(start <= p_start and p_end <= end
                 for start, end in history_spans(text, rel, ((rel, phrase),))
                 for p_start, p_end in pin_spans(text, version)):
            out.append(f"{rel}: declared history phrase contains a pin form, which would be rewritten: {phrase!r}")
    return out


def rewrite(old: str, new: str, root: str = ROOT) -> list[str]:
    """Rewrite the pins of `old` to `new` under `root`; return the files changed."""
    changed = []
    for rel, path in files(root):
        text = _read(path)
        if text is None:
            continue
        updated = rewrite_text(text, old, new)
        if updated != text:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(updated)
            changed.append(rel)
    return changed


HINT = ("Each place that names the vendored release must use a form in PINS (tools/pin_versions.py), "
        "and a statement about a past release that names this version must be declared in HISTORY "
        "there; otherwise a refresh would either miss the pin or rewrite the history.")


def main(argv: list[str]) -> int:
    version = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
    if len(argv) == 2 and argv[0] == "check" and version.match(argv[1]):
        found = problems(argv[1])
        print("\n".join(found) if found else f"every {argv[1]} is a pin or declared history")
        if found:
            print(HINT, file=sys.stderr)
        return 1 if found else 0
    if len(argv) == 3 and argv[0] == "rewrite" and version.match(argv[1]) and version.match(argv[2]):
        old, new = argv[1:]
        found = problems(old)
        if found:
            print("\n".join(found), file=sys.stderr)
            print(f"not rewriting {old}: {HINT}", file=sys.stderr)
            return 1
        if old != new:
            for rel in rewrite(old, new):
                print(f"pinned {new} in {rel}")
        return 0
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
