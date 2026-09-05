#!/usr/bin/env python3
"""to_artifact.py - turn a maidr-enabled HTML file (py-maidr output or any page) into chat-artifact content.

Usage:
    python to_artifact.py chart.html [-o artifact.html] [--cdn jsdelivr|cdnjs] [--fragment] [--title NAME]

Chat products that render HTML (claude.ai and Claude Code artifacts) allow scripts only from a few CDN hosts
and cannot read local files. This script makes a page depend on exactly one pinned maidr.js <script src>:

  * py-maidr's inline loader block (which injects the jsDelivr URL, plus a lib/ fallback in "auto" mode) is
    replaced by a plain <script src> tag; any remaining lib/ references are dropped.
  * --cdn cdnjs switches that tag to cdnjs (only the core file is mirrored there, which is all a py-maidr or
    hand-authored page needs); the default keeps jsDelivr.
  * --fragment emits only <title>, <style>, <script> and the body content, for hosts that wrap content in
    their own document shell (the Claude Code Artifact tool). Without it a full document is kept, which is
    what a claude.ai chat artifact takes.

Only the standard library is used. Run scripts/check_maidr_html.py on the result afterwards.
"""
from __future__ import annotations

import argparse
import html as _html
import json
import os
import re
import sys

DEFAULT_VERSION = "4.6.0"
LOADER = re.compile(r"<script\b[^>]*>(?:(?!</script>).)*?cdn\.jsdelivr\.net/npm/maidr@(?:(?!</script>).)*?</script>", re.S | re.I)
CORE_SRC = re.compile(r"<script\b[^>]*\bsrc=[\"'][^\"']*maidr(?:\.min)?\.js[\"'][^>]*>\s*</script>", re.I)
LIB_REFS = re.compile(r"<(?:link|script)\b[^>]*(?:href|src)=[\"'][^\"']*lib/maidr[^\"']*[\"'][^>]*>(?:\s*</script>)?", re.I)


def cdn_url(host: str, version: str) -> str:
    if host == "cdnjs":
        return f"https://cdnjs.cloudflare.com/ajax/libs/maidr/{version}/maidr.min.js"
    return f"https://cdn.jsdelivr.net/npm/maidr@{version}/dist/maidr.js"


def chart_title(html: str) -> str | None:
    """Figure or first layer title from the embedded MAIDR JSON, for pages that have no <title>."""
    m = re.search(r"\smaidr(?:-data)?=(\"[^\"]*\"|'[^']*')", html)
    if not m:
        return None
    try:
        doc = json.loads(_html.unescape(m.group(1)[1:-1]))
    except ValueError:
        return None
    if doc.get("title"):
        return str(doc["title"])
    for row in doc.get("subplots") or []:
        for sp in row or []:
            for layer in (sp or {}).get("layers") or []:
                if layer.get("title"):
                    return str(layer["title"])
    return None


def convert(html: str, host: str, title: str | None) -> tuple[str, str]:
    m = re.search(r"maidr@(\d+\.\d+\.\d+)", html) or re.search(r"/libs/maidr/(\d+\.\d+\.\d+)/", html)
    version = m.group(1) if m else DEFAULT_VERSION
    tag = f'<script src="{cdn_url(host, version)}"></script>'
    html = CORE_SRC.sub("", html)                 # drop static core tags first; one pinned tag is added below
    html, n_loader = LOADER.subn(tag, html, count=1)
    html = LOADER.sub("", html)                   # any further loader copies would double-load
    if n_loader == 0:
        idx = html.lower().find("<svg")           # no loader to replace: put the tag before the first <svg>
        html = html[:idx] + tag + "\n" + html[idx:] if idx >= 0 else tag + "\n" + html
    html = LIB_REFS.sub("", html)
    if not re.search(r"<title\b", html, re.I):
        name = title or chart_title(html)
        if name:
            title_tag = f"<title>{_html.escape(name)}</title>"
            head = re.search(r"<head\b[^>]*>", html, re.I)
            html = html[:head.end()] + "\n" + title_tag + html[head.end():] if head else title_tag + "\n" + html
    return html, version


def fragment(html: str) -> str:
    head = re.search(r"<head\b[^>]*>(.*?)</head>", html, re.S | re.I)
    body = re.search(r"<body\b[^>]*>(.*)</body>", html, re.S | re.I)
    head_html = head.group(1) if head else ""
    body_html = body.group(1) if body else html
    keep = []
    keep += re.findall(r"<title\b[^>]*>.*?</title>", head_html, re.S | re.I)
    keep += re.findall(r"<style\b[^>]*>.*?</style>", head_html, re.S | re.I)
    keep += re.findall(r"<script\b[^>]*>.*?</script>", head_html, re.S | re.I)
    return "\n".join(k.strip() for k in keep) + "\n" + body_html.strip() + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("-o", "--output", help="output path (default: <source>-artifact.html)")
    ap.add_argument("--cdn", choices=["jsdelivr", "cdnjs"], default="jsdelivr")
    ap.add_argument("--fragment", action="store_true", help="emit title/style/script/body content only")
    ap.add_argument("--title", help="artifact name; default: the page's <title>, else the chart title from the MAIDR JSON")
    a = ap.parse_args(argv)
    with open(a.source, encoding="utf-8") as fh:
        html = fh.read()
    out, version = convert(html, a.cdn, a.title)
    if a.fragment:
        out = fragment(out)
    dest = a.output or re.sub(r"\.html?$", "", a.source) + "-artifact.html"
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(out)
    print(f"wrote {dest} ({os.path.getsize(dest):,} bytes; maidr.js {version} from {a.cdn}"
          f"{', fragment' if a.fragment else ', full document'})")
    print(f"next: python {os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check_maidr_html.py')} {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
