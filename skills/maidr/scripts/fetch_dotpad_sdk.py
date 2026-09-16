#!/usr/bin/env python3
"""fetch_dotpad_sdk.py - download the DotPad tactile-display SDK that maidr.js is pinned to, for offline pages.

Usage:
    python fetch_dotpad_sdk.py [DEST] [--force] [--json]

    DEST      directory to write into (default: ./dotpad-sdk, beside the page you are building)
    --force   refetch files that are already present and correct
    --json    print a machine-readable summary instead of prose

Exit codes: 0 = the directory holds a verified copy, 1 = a file could not be fetched or verified,
2 = usage problem.

Why this exists
    maidr.js can draw a chart onto a Dot Pad (a refreshable pin display) through the vendor's SDK.
    It does not bundle that SDK: its braille engine is a 14 MB liblouis build, so by default maidr.js
    imports the vendor's published copy from jsDelivr, pinned to a commit, the first time a DotPad is
    connected. That is the one network request an otherwise offline page still makes. Dot Inc. permit
    MAIDR to redistribute the SDK, so an air-gapped page can carry its own copy: run this, ship the
    directory beside the page, and declare where it is before maidr.js loads:

        <script>
          window.MAIDR_DOTPAD_SDK_URL = "./dotpad-sdk/DotPadSDK-<version>.js";
          window.MAIDR_DOTPAD_ASSET_BASE_URL = "./dotpad-sdk/lib/";
        </script>

    <version> is the one named in ../assets/dotpad-sdk.json (for example 3.0.3); the script prints the two
    lines with the real file names when it finishes.

    py-maidr (`maidr.download_dotpad_sdk()`) and the maidr R package (`maidr_download_dotpad_sdk()`) do
    the same for their own output; this script is for hand-authored maidr.js pages.

What is fetched
    Every file listed in ../assets/dotpad-sdk.json, the pin maidr.js is built against (tools/update-bundle.sh
    refreshes it from the maidr.js package's dist/dotpad-sdk.json): the SDK module, the liblouis build (js, wasm, data),
    and the LGPL-2.1 licence text and wrapper sources the vendor asks redistributors to keep beside the
    engine. Each is verified against its recorded size and SHA-256 before it is written; a manifest.json
    naming the commit is written last, so a copy found later can be traced. A second run finds the
    files in place and fetches nothing. Only the Python standard library is used.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "..", "assets", "dotpad-sdk.json")
DEFAULT_DEST = "dotpad-sdk"
TIMEOUT = 120


def load_manifest() -> dict:
    with open(MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


def mismatch(data: bytes, expected: dict) -> str | None:
    """Why *data* is not the file described, or None when it is. Size first: the corruption this pin
    guards against was a file arriving 7,685 bytes short, and a size says so where a digest only says
    'different'."""
    if len(data) != expected["bytes"]:
        return f"expected {expected['bytes']} bytes, got {len(data)}"
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected["sha256"]:
        return f"expected sha256 {expected['sha256']}, got {digest}"
    return None


def existing_is_valid(path: str, expected: dict) -> bool:
    try:
        with open(path, "rb") as fh:
            return mismatch(fh.read(), expected) is None
    except OSError:
        return False


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "maidr-skill fetch_dotpad_sdk"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def main(argv: list[str]) -> int:
    dest = DEFAULT_DEST
    force = False
    as_json = False
    for arg in argv:
        if arg == "--force":
            force = True
        elif arg == "--json":
            as_json = True
        elif arg.startswith("-"):
            print(__doc__, file=sys.stderr)
            return 2
        else:
            dest = arg

    manifest = load_manifest()
    os.makedirs(dest, exist_ok=True)
    fetched, kept, failures = [], [], []

    for relative, expected in manifest["files"].items():
        target = os.path.join(dest, *relative.split("/"))
        if not force and existing_is_valid(target, expected):
            kept.append(relative)
            continue
        url = manifest["baseUrl"] + relative
        try:
            data = fetch(url)
        except OSError as exc:  # URLError is an OSError; so is a connection reset
            failures.append(f"{relative}: {exc}")
            continue
        problem = mismatch(data, expected)
        if problem is not None:
            failures.append(f"{relative}: {problem}")
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        partial = target + ".part"
        with open(partial, "wb") as fh:
            fh.write(data)
        os.replace(partial, target)
        fetched.append(relative)

    ok = not failures
    if ok:
        record = dict(manifest)
        with open(os.path.join(dest, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2)
            fh.write("\n")

    module_url = f"./{os.path.basename(os.path.normpath(dest))}/{manifest['module']}"
    asset_url = f"./{os.path.basename(os.path.normpath(dest))}/{manifest['assetDir']}"
    if as_json:
        print(json.dumps({
            "ok": ok, "dest": os.path.abspath(dest), "version": manifest["version"],
            "commit": manifest["commit"], "fetched": fetched, "kept": kept, "failures": failures,
            "globals": {"MAIDR_DOTPAD_SDK_URL": module_url, "MAIDR_DOTPAD_ASSET_BASE_URL": asset_url},
        }, indent=2))
    else:
        for name in fetched:
            print(f"fetched     {name}")
        for name in kept:
            print(f"up to date  {name}")
        for failure in failures:
            print(f"FAILED      {failure}", file=sys.stderr)
        if ok:
            print(f"\nDotPad SDK {manifest['version']} ({manifest['commit'][:7]}) is in {os.path.abspath(dest)}")
            print("Declare it before maidr.js loads (adjust the path to where the page is served from):")
            print(f'  <script>window.MAIDR_DOTPAD_SDK_URL = "{module_url}";')
            print(f'          window.MAIDR_DOTPAD_ASSET_BASE_URL = "{asset_url}";</script>')
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
