#!/usr/bin/env python3
"""Rewrite the maidr.js version pins, and nothing else that names a version.

    python3 tools/pin_versions.py check VERSION [NEXT]
    python3 tools/pin_versions.py rewrite OLD NEW

tools/update-bundle.sh runs `rewrite` once it has vendored NEW. It used to replace every exact
match of OLD across the skill, README.md and AGENTS.md, which also moved the statements that say
when something arrived: "hoverMode needs maidr.js after 4.14.0" became "after 4.15.0" (a release
that already shipped it), and "4.x releases before 4.10.0 highlight nothing" read "before 4.15.0"
four refreshes later. So a version is rewritten only where it stands in one of the forms in PINS,
which name the vendored release by construction: a CDN URL, a constant, a heading.

Every other occurrence of the vendored version must be history, declared in HISTORY, or the
command refuses before it writes anything, so a new pin in an unknown form, or a history statement
that happens to name the vendored release, is a decision for a person rather than a guess.

A version newer than the vendored one must be declared too. "newKey (maidr.js 4.16.0 and later)",
written while 4.15.0 is vendored, names no pin and passes the rule above, but once 4.16.0 is
vendored it is an undeclared mention of the pin: the tests fail on main, the weekly release that
waits on them stops, and the next refresh refuses to run. So it is reported now, while the person
who wrote it can declare it. `check VERSION NEXT`, which update-bundle.sh runs before it fetches
NEXT, also reports every NEXT that is neither a pin form nor declared. That covers a move to a
newer release. A rollback (NEXT older than VERSION) leaves more: every version between the two
that the tree names becomes newer than the vendored release, and `check VERSION NEXT` does not
report those; `check NEXT`, which the tests run on the tree once NEXT is vendored, does.

`check` runs the same classification without writing; tests/test_pin_versions.py runs it on the
tree and fails when anything is left over.
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where pins live: the skill and the two top-level documents that name the vendored release.
SCAN = ("skills/maidr", "README.md", "AGENTS.md")
# Files that are the release itself, or that update-bundle.sh writes on its own (dotpad-sdk.json is
# the release's copy, and names the DotPad SDK's versions, which are no business of this check).
SKIP_FILES = {"maidr.js", "maidr-math.css", "maidr-bundle.json", "dotpad-sdk.json"}
SKIP_DIRS = {"__pycache__"}

# Each form names the vendored release; "{v}" stands for the version. Add a form here when a new
# place pins the release, rather than writing the version where only a person can tell it apart.
PINS = (
    "npm/maidr@{v}/",                   # jsDelivr URLs (SKILL.md, references, assets); not a bare
                                        # "maidr@{v}", which a sentence about a release can use too
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

# Statements that name the vendored version, or a version newer than it, as (path, exact phrase).
# They are never rewritten, so an entry naming a future release keeps it once that release is
# vendored. A phrase that names an older version needs no entry: only the vendored version is
# ever rewritten. Prefer naming the release by what it is about ("after 4.14.0", "4.10.0 and
# later"), which does not change when the pin does. A feature not yet released needs an entry
# however it is written: while 4.N is vendored, "after 4.N" names the vendored release and
# "4.N+1 and later" a newer one. Prefer "after 4.N", which stays true whichever release ships the
# feature, where "4.N+1 and later" is wrong if the feature slips to a later one. A newer version
# that is not maidr.js's (a browser's, say) is declared here as well, since the check cannot tell
# them apart.
HISTORY: tuple[tuple[str, str], ...] = ()

ANY_VERSION = re.compile(r"(?<![0-9.])[0-9]+\.[0-9]+\.[0-9]+(?![0-9])(?!\.[0-9])")


def _key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


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


def _declared(start: int, end: int, hist: list[tuple[int, int]]) -> bool:
    return any(h_start <= start and end <= h_end for h_start, h_end in hist)


def newer(text: str, version: str, rel: str = "", history=None) -> list[int]:
    """Offsets of versions newer than `version` that are not inside a declared history phrase.

    A pin form does not excuse one: a pin names the vendored release, never a newer one.
    """
    hist = history_spans(text, rel, history)
    return [m.start() for m in ANY_VERSION.finditer(text)
            if _key(m.group()) > _key(version) and not _declared(*m.span(), hist)]


def unclassified(text: str, version: str, rel: str = "", history=None) -> list[int]:
    """Offsets of `version` that are neither a pin nor inside a declared history phrase."""
    pins = pin_spans(text, version)
    hist = history_spans(text, rel, history)
    out = []
    for m in re.finditer(_version_re(version), text):
        if m.span() in pins:
            continue
        if _declared(*m.span(), hist):
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


def problems(version: str, root: str = ROOT, history=None, target: str | None = None) -> list[str]:
    """Every occurrence of `version` that is not a pin, every undeclared version newer than it,
    every undeclared non-pin `target` (the release a refresh is about to vendor), and every
    declared phrase that is gone."""
    out = []
    history = HISTORY if history is None else history

    def report(rel: str, text: str, offset: int, found: str, why: str) -> None:
        line = text.count("\n", 0, offset) + 1
        col = offset - (text.rfind("\n", 0, offset) + 1)
        snippet = text[max(0, offset - 50):offset + len(found) + 30].replace("\n", " ")
        out.append(f"{rel}:{line}:{col + 1}: {found} {why}: ...{snippet}...")

    for rel, path in files(root):
        text = _read(path)
        if text is None:
            continue
        seen = set()
        for offset in unclassified(text, version, rel, history):
            seen.add(offset)
            report(rel, text, offset, version, "is neither a pin nor declared history")
        for offset in newer(text, version, rel, history):
            seen.add(offset)
            found = ANY_VERSION.match(text, offset).group()
            report(rel, text, offset, found, f"is newer than the vendored {version} and not declared history")
        if target is not None and target != version:
            for offset in unclassified(text, target, rel, history):
                if offset not in seen:
                    report(rel, text, offset, target,
                           "is the release being vendored, and is neither a pin nor declared history")
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
        "and a statement that names this version, or a newer one, must be declared in HISTORY "
        "there; otherwise a refresh would either miss the pin or rewrite the history.")


def main(argv: list[str]) -> int:
    version = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
    if len(argv) in (2, 3) and argv[0] == "check" and all(version.match(v) for v in argv[1:]):
        found = problems(argv[1], target=argv[2] if len(argv) == 3 else None)
        print("\n".join(found) if found else
              f"every {' and '.join(dict.fromkeys(argv[1:]))} is a pin or declared history, "
              f"and no newer version is undeclared")
        if found:
            print(HINT, file=sys.stderr)
        return 1 if found else 0
    if len(argv) == 3 and argv[0] == "rewrite" and version.match(argv[1]) and version.match(argv[2]):
        old, new = argv[1:]
        found = problems(old, target=new)
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
