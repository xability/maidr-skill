#!/usr/bin/env python3
"""to_artifact.py - turn a maidr-enabled HTML file (py-maidr output or any page) into chat-artifact content.

Usage:
    python to_artifact.py chart.html [-o artifact.html] [--cdn jsdelivr|cdnjs] [--fragment] [--title NAME]
    python to_artifact.py chart.html --visualize -o /workspace/<title>.html     # ChatGPT Work

Chat products that render HTML (claude.ai and Claude Code artifacts, ChatGPT Work's visualize surface) allow
scripts only from a few CDN hosts and cannot read local files. This script makes a page depend on exactly one
pinned maidr.js <script src>:

  * py-maidr's inline loader block (which injects the jsDelivr URL, plus a lib/ fallback in "auto" mode) is
    replaced by a plain <script src> tag; any remaining lib/ references are dropped.
  * plotly.js and BokehJS move from their own CDNs, which those sandboxes block, to the same files on
    jsDelivr's npm mirror.
  * --cdn cdnjs switches that tag to cdnjs (only the core file is mirrored there, which is all a py-maidr or
    hand-authored page needs); the default keeps jsDelivr. cdnjs carries no locale packs yet
    (cdnjs/packages#2205), so on cdnjs every reader hears English; keep jsDelivr unless only cdnjs is allowed.
  * --fragment emits only <title>, <style>, <script> and the body content, for hosts that wrap content in
    their own document shell (the Claude Code Artifact tool). Without it a full document is kept, which is
    what a claude.ai chat artifact takes.
  * --visualize emits the fragment ChatGPT Work's visualize surface takes: no <title>, everything inside one
    root element with an id, the chart scaled down to the frame's width. It fails when the fragment would
    load something from a host outside that surface's CSP or from a local path, when an inline script makes
    a request (fetch, XHR, WebSocket), or when the fragment reaches 1 MB, and otherwise prints the
    visualize{...} line the reply carries where the chart should appear.

Only the standard library is used. Run scripts/check_maidr_html.py on the result afterwards.
"""
from __future__ import annotations

import argparse
import html as _html
import json
import os
import re
import sys
from urllib.parse import urlsplit

DEFAULT_VERSION = "4.12.0"
# the script that loads the bundle, not a maidrLocaleBaseUrl or maidrMathStylesheetUrl declaration naming its directory
LOADER = re.compile(r"<script\b[^>]*>(?:(?!</script>).)*?cdn\.jsdelivr\.net/npm/maidr@[^/\s\"']+/dist/maidr(?:\.min)?\.js(?:(?!</script>).)*?</script>", re.S | re.I)
CORE_SRC = re.compile(r"<script\b[^>]*\bsrc=[\"'][^\"']*maidr(?:\.min)?\.js[\"'][^>]*>\s*</script>", re.I)
JSDELIVR_CORE = re.compile(r"https://cdn\.jsdelivr\.net/npm/maidr@[^/\s\"']+/dist/maidr(?:\.min)?\.js")
LIB_REFS = re.compile(r"<(?:link|script)\b[^>]*(?:href|src)=[\"'][^\"']*lib/maidr[^\"']*[\"'][^>]*>(?:\s*</script>)?", re.I)
# py-maidr's Plotly and Bokeh pages load the library from its own CDN, which the chat sandboxes block: claude.ai and
# Claude Code artifacts admit jsDelivr's /npm/ paths but not cdn.plot.ly or cdn.bokeh.org. jsDelivr's npm mirror
# serves the same files byte for byte (compared for plotly.js 3.5.0 and BokehJS 3.9.2, including the widgets,
# tables, gl, mathjax and api extensions).
MIRRORS = (
    (re.compile(r"https://cdn\.plot\.ly/plotly-(\d+\.\d+\.\d+)\.min\.js"),
     r"https://cdn.jsdelivr.net/npm/plotly.js-dist-min@\1/plotly.min.js"),
    (re.compile(r"https://cdn\.bokeh\.org/bokeh/release/bokeh((?:-[a-z]+)?)-(\d+\.\d+\.\d+)\.min\.js"),
     r"https://cdn.jsdelivr.net/npm/@bokeh/bokehjs@\2/build/js/bokeh\1.min.js"),
)
# ChatGPT Work's visualize skill: "The CSP allows only cdnjs.cloudflare.com, esm.sh, cdn.jsdelivr.net,
# unpkg.com, fonts.googleapis.com, fonts.gstatic.com, and fonts.bunny.net. Other origins are blocked and fail
# silently", and "Keep visualizations under 1 MB".
VISUALIZE_HOSTS = frozenset({
    "cdnjs.cloudflare.com", "esm.sh", "cdn.jsdelivr.net", "unpkg.com",
    "fonts.googleapis.com", "fonts.gstatic.com", "fonts.bunny.net",
})
VISUALIZE_LIMIT = 1_000_000
# Everywhere a fragment can name something for the frame to load: a resource attribute on any element but <a>,
# which navigates rather than loads; each candidate in a srcset; url() and @import in CSS, in <style> or a style
# attribute. Inline code is checked for the request APIs the skill rules out ("Never use fetch, XHR,
# WebSocket, or other API calls"). Script and style bodies are not markup, so tags are read with them emptied,
# and a script whose type is not JavaScript (a JSON data island) is not code.
TAG = re.compile(r"<([a-zA-Z][\w:-]*)\b([^>]*)>")
BODY = re.compile(r"(<(script|style)\b[^>]*>).*?(</\2>)", re.S | re.I)
SCRIPT = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.S | re.I)
SCRIPT_TYPE = re.compile(r"""\btype\s*=\s*["']?\s*([^"'\s>]+)""", re.I)
JS_TYPES = frozenset({"module", "text/javascript", "application/javascript", "text/ecmascript"})
RESOURCE_ATTR = re.compile(r"""(?<![\w:-])(src|href|xlink:href|srcset|poster|data)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style>", re.S | re.I)
STYLE_ATTR = re.compile(r"""(?<![\w:-])style\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
CSS_URL = re.compile(r"""url\(\s*['"]?([^'")\s]+)|@import\s+['"]([^'"]+)""", re.I)
REQUEST_API = re.compile(r"\b(fetch(?=\s*\()|XMLHttpRequest|WebSocket|EventSource|sendBeacon)\b")


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
    for pattern, repl in MIRRORS:
        html = pattern.sub(repl, html)
    html = CORE_SRC.sub("", html)                 # drop static core tags first; one pinned tag is added below
    # py-maidr's Plotly and Bokeh pages put their loader inside the script that also carries the chart and its
    # MAIDR JSON, so replacing that script would delete the chart. It is kept, with the tag ahead of it and its
    # own URL switched to the tag's: its loader looks for a script with that URL, finds the tag on the page,
    # and loads nothing. A loader that is only a loader carries no JSON object.
    parts, pos, n_loader = [], 0, 0
    for m in LOADER.finditer(html):
        parts.append(html[pos:m.start()])
        carries_chart = '{"' in m.group(0)
        if n_loader == 0:
            parts.append(tag + "\n" if carries_chart else tag)
        if carries_chart:                         # a further bare loader is dropped: it would double-load
            parts.append(JSDELIVR_CORE.sub(cdn_url(host, version), m.group(0)))
        n_loader += 1
        pos = m.end()
    html = "".join(parts) + html[pos:]
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


def visualize(html: str, root_id: str) -> tuple[str, list[str]]:
    """The fragment ChatGPT Work's visualize surface takes, and the hosts its CSP would still block.

    That surface's contract asks for a fragment with no <title> and one root element with an id, sized to a
    frame from 320px wide up. A matplotlib SVG has a fixed width, so it is allowed to scale down with the
    frame; its viewBox keeps maidr's highlighting on the right marks.
    """
    body = re.sub(r"<title\b[^>]*>.*?</title>\s*", "", fragment(html), flags=re.S | re.I)
    style = (f"<style>#{root_id} svg[maidr], #{root_id} svg[maidr-data] "
             "{ max-width: 100%; height: auto; }</style>")
    out = f'<div id="{root_id}">\n{style}\n{body}</div>\n'
    return out, visualize_problems(out)


def visualize_problems(fragment_html: str) -> list[str]:
    """What in a fragment the visualize surface would not load: other hosts, local files, requests."""
    urls = []
    markup = BODY.sub(r"\1\3", fragment_html)
    for name, attrs in TAG.findall(markup):
        if name.lower() == "a":
            continue
        for attr, double, single in RESOURCE_ATTR.findall(attrs):
            value = double or single
            if attr.lower() == "srcset":
                urls += [candidate.split()[0] for candidate in value.split(",") if candidate.strip()]
            else:
                urls.append(value)
    css = STYLE_BLOCK.findall(fragment_html) + [d or s for d, s in STYLE_ATTR.findall(markup)]
    urls += [first or second for block in css for first, second in CSS_URL.findall(block)]
    problems = set()
    for url in (u.strip() for u in urls):
        if not url or url.startswith(("#", "data:", "blob:", "about:")):
            continue                              # in-page references and inline data load nothing from a host
        parts = urlsplit("https:" + url if url.startswith("//") else url)
        if parts.scheme in ("http", "https"):
            host = (parts.hostname or "").lower()
            if host not in VISUALIZE_HOSTS:
                problems.add(f"{host} is outside the visualize CSP, so {url} will not load there")
        else:
            problems.add(f"{url} is a local path, and the visualize surface has no files beside the fragment")
    for attrs, code in SCRIPT.findall(fragment_html):
        kind = SCRIPT_TYPE.search(attrs)
        if re.search(r"\bsrc\s*=", attrs, re.I) or (kind and kind.group(1).lower() not in JS_TYPES):
            continue
        for api in REQUEST_API.findall(code):
            problems.add(f"an inline script uses {api}, which the visualize surface blocks")
    return sorted(problems)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("-o", "--output", help="output path (default: <source>-artifact.html)")
    ap.add_argument("--cdn", choices=["jsdelivr", "cdnjs"], default="jsdelivr")
    ap.add_argument("--fragment", action="store_true", help="emit title/style/script/body content only")
    ap.add_argument("--visualize", action="store_true",
                    help="ChatGPT Work: a fragment for its visualize surface; write it to /workspace/<title>.html")
    ap.add_argument("--title", help="artifact name; default: the page's <title>, else the chart title from the MAIDR JSON")
    a = ap.parse_args(argv)
    with open(a.source, encoding="utf-8") as fh:
        html = fh.read()
    out, version = convert(html, a.cdn, a.title)
    dest = a.output or re.sub(r"\.html?$", "", a.source) + "-artifact.html"
    problems: list[str] = []
    if a.visualize:
        stem = os.path.splitext(os.path.basename(dest))[0].lower()
        out, problems = visualize(out, "maidr-" + (re.sub(r"[^a-z0-9]+", "-", stem).strip("-") or "chart"))
    elif a.fragment:
        out = fragment(out)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(out)
    size = os.path.getsize(dest)
    kind = "visualize fragment" if a.visualize else "fragment" if a.fragment else "full document"
    print(f"wrote {dest} ({size:,} bytes; maidr.js {version} from {a.cdn}, {kind})")
    print(f"next: python {os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check_maidr_html.py')} {dest}")
    if not a.visualize:
        return 0
    if size >= VISUALIZE_LIMIT:
        problems.append(f"the visualize surface takes fragments under {VISUALIZE_LIMIT:,} bytes; plot fewer points, "
                        "or set plt.rcParams['svg.fonttype'] = 'none' before drawing")
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if problems:
        return 1
    print("put this line, on its own, where the chart belongs in the reply:")
    print("visualize" + json.dumps({"path": os.path.abspath(dest)}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
