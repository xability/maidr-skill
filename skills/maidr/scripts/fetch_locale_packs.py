#!/usr/bin/env python3
"""fetch_locale_packs.py - put maidr.js's locale packs beside a local copy of maidr.js, for offline pages.

Usage:
    python fetch_locale_packs.py [DEST] [--lang ko,ja] [--version X.Y.Z] [--from DIR] [--force] [--json]

    DEST       the directory holding the page's maidr.js (default: the current directory)
    --lang     comma-separated language codes to fetch (default: all of ko ja zh es de fr it hi)
    --version  the maidr.js release to fetch from (default: the vendored one in ../assets/maidr-bundle.json);
               it must be the release of the maidr.js in DEST
    --from     copy from a local directory instead of downloading, e.g. node_modules/maidr/dist
    --force    refetch packs that are already present
    --json     print a machine-readable summary instead of prose

Exit codes: 0 = every requested pack is in DEST, 1 = a pack could not be fetched or is not a locale pack,
2 = usage problem.

Why this exists
    Since 4.8.0 maidr.js speaks English on its own; every other language is a separate locale pack,
    dist/locale-<code>.js, which maidr.js fetches from the directory it was itself loaded from the moment
    the reader's language needs it. A page that loads ./maidr.js (the vendored assets/maidr.js copied
    beside it) therefore asks for ./locale-ko.js for a Korean reader, gets a 404, warns
    "[maidr] Could not load the locale pack at ...; announcements stay in English", and stays English.
    Run this against the directory holding that maidr.js and ship the packs with it. The skill does not
    vendor them: most pages need none, and a page that must work offline for a known language needs one.

    The packs are fetched from jsDelivr's copy of the npm release; each is checked to be the pack for its
    language before it is written. Only the Python standard library is used.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE_META = os.path.join(HERE, "..", "assets", "maidr-bundle.json")
# maidr.js's SUPPORTED_LOCALES minus the built-in English (tests/ ties this to the vendored bundle)
LOCALES = ("ko", "ja", "zh", "es", "de", "fr", "it", "hi")
TIMEOUT = 60


def vendored_version() -> str:
    with open(BUNDLE_META, encoding="utf-8") as fh:
        return json.load(fh)["version"]


def is_pack(data: bytes, code: str) -> bool:
    """A locale pack registers itself on globalThis.maidrLocales under its code; an error page does not."""
    text = data.decode("utf-8", errors="replace")
    return "maidrLocales" in text and f"`{code}`" in text


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "maidr-skill fetch_locale_packs"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def main(argv: list[str]) -> int:
    dest, source, version = ".", None, None
    langs = list(LOCALES)
    force = as_json = False
    args = iter(argv)
    try:
        for arg in args:
            if arg == "--force":
                force = True
            elif arg == "--json":
                as_json = True
            elif arg == "--lang":
                langs = [c.strip().lower() for c in next(args).split(",") if c.strip()]
            elif arg == "--version":
                version = next(args)
            elif arg == "--from":
                source = next(args)
            elif arg.startswith("-"):
                raise ValueError(arg)
            else:
                dest = arg
    except (StopIteration, ValueError):
        print(__doc__, file=sys.stderr)
        return 2
    unknown = [c for c in langs if c not in LOCALES]
    if unknown or not langs:
        print(f"unknown language code(s) {unknown or langs}; maidr.js ships {', '.join(LOCALES)} (English is built in)",
              file=sys.stderr)
        return 2
    version = version or vendored_version()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        print(f"not a maidr release version: {version!r}", file=sys.stderr)
        return 2
    base = f"https://cdn.jsdelivr.net/npm/maidr@{version}/dist/"

    os.makedirs(dest, exist_ok=True)
    fetched, kept, failures = [], [], []
    for code in langs:
        name = f"locale-{code}.js"
        target = os.path.join(dest, name)
        if not force and os.path.isfile(target):
            with open(target, "rb") as fh:
                if is_pack(fh.read(), code):
                    kept.append(name)
                    continue
        try:
            if source:
                with open(os.path.join(source, name), "rb") as fh:
                    data = fh.read()
            else:
                data = fetch(base + name)
        except OSError as exc:  # URLError and a missing --from file are both OSErrors
            failures.append(f"{name}: {exc}")
            continue
        if not is_pack(data, code):
            failures.append(f"{name}: not a maidr locale pack for '{code}'")
            continue
        partial = target + ".part"
        with open(partial, "wb") as fh:
            fh.write(data)
        os.replace(partial, target)
        fetched.append(name)

    ok = not failures
    if not os.path.isfile(os.path.join(dest, "maidr.js")) and not os.path.isfile(os.path.join(dest, "maidr.min.js")):
        note = f"no maidr.js in {os.path.abspath(dest)}; maidr.js looks for the packs in its own directory"
    else:
        note = None
    if as_json:
        print(json.dumps({"ok": ok, "dest": os.path.abspath(dest), "version": version,
                          "source": source or base, "fetched": fetched, "kept": kept,
                          "failures": failures, "note": note}, indent=2))
    else:
        for name in fetched:
            print(f"fetched     {name}")
        for name in kept:
            print(f"up to date  {name}")
        for failure in failures:
            print(f"FAILED      {failure}", file=sys.stderr)
        if note:
            print(f"note: {note}", file=sys.stderr)
        if ok:
            print(f"\nmaidr {version} locale packs are in {os.path.abspath(dest)}; "
                  "maidr.js loaded from that directory finds them with no further markup.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
