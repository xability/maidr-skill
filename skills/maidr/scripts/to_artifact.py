#!/usr/bin/env python3
"""to_artifact.py - turn a maidr-enabled HTML file (py-maidr output or any page) into chat-artifact content.

Usage:
    python to_artifact.py chart.html [-o artifact.html] [--cdn jsdelivr|cdnjs] [--fragment] [--title NAME]
    python to_artifact.py chart.html --fragment -o chart-fragment.html          # Claude native show_widget
    python to_artifact.py chart.html --visualize -o /workspace/<title>.html     # ChatGPT Work

The default and --fragment paths retain pinned CDN scripts. Use --fragment for Claude's
native HTML renderer (show_widget), which receives supplied HTML; it is not Work's
visualize surface. --visualize is only for ChatGPT Work and instead embeds the verified
vendored runtime as gzip/base64, decoded with DecompressionStream and run as an inline
script. It requires no browser network or blob URLs, uses English and private in-memory
settings, and includes math layout CSS without large embedded fonts. Other external
dependencies are rejected: prefer a matplotlib/seaborn SVG. Source resize/redraw handlers
are rejected: materialize SVG marks with intrinsic width/height and a viewBox, then let
CSS scale the whole chart without changing mark geometry after MAIDR initializes. The
Work fragment must remain strictly under 1,000,000 UTF-8 bytes.

Only the standard library is used. Run scripts/check_maidr_html.py on the result afterwards.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import zlib
from pathlib import Path
from html.parser import HTMLParser
import html as _html
import json
import math
import os
import re
import sys
from urllib.parse import urlsplit

DEFAULT_VERSION = "4.16.0"
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
# The observed Work CSP allows inline/blob scripts, not third-party CDNs.
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
# Conservative source guard, not a JavaScript parser. MAIDR's hidden mark clones retain
# author classes, and their geometry is cached. Redrawing on resize can either mutate
# those clones or leave them stale even when a selector excludes data-maidr-owned.
SOURCE_RESIZE = re.compile(
    r"\bResizeObserver\b|\baddEventListener\s*\(\s*['\"`]resize['\"`]\s*,"
    r"|\bonresize\s*=|\[\s*['\"]onresize['\"]\s*\]\s*="
)
STATIC_SVG_GUIDANCE = (
    "source resize/redraw code is unsafe in visualize: MAIDR keeps hidden mark clones "
    "and cached highlight geometry, so redraws can corrupt or misalign highlights even "
    "when owned clones are filtered out. Materialize a static SVG with intrinsic width/height "
    "and viewBox; scale the whole SVG with CSS without changing mark geometry after "
    "MAIDR initializes, or regenerate it with matplotlib/seaborn."
)


def source_resize_problems(html: str) -> list[str]:
    """Only executable author code is checked, never encoded runtime/JSON data islands."""
    for attrs, code in SCRIPT.findall(html):
        kind = SCRIPT_TYPE.search(attrs)
        if re.search(r"\bsrc\s*=", attrs, re.I) or (kind and kind.group(1).lower() not in JS_TYPES):
            continue
        if SOURCE_RESIZE.search(code):
            return [STATIC_SVG_GUIDANCE]
    # onresize="..." on body/window is an executable handler, too. Script bodies have
    # been emptied so a quoted HTML example inside a script is not mistaken for markup.
    class ResizeAttributes(HTMLParser):
        found = False
        def handle_starttag(self, name, attrs):
            if any(attr == "onresize" and value for attr, value in attrs):
                self.found = True
        handle_startendtag = handle_starttag
    attributes = ResizeAttributes()
    attributes.feed(BODY.sub(r"\1\3", html))
    return [STATIC_SVG_GUIDANCE] if attributes.found else []


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


BUNDLE_MARKER = "maidr-visualize-gzip-v1"
ASSETS = Path(__file__).resolve().parent.parent / "assets"
BOOTSTRAP = r'''(async function () {
  const boot = document.currentScript;
  const root = boot.parentElement;
  const status = root.querySelector('[data-maidr-status]');
  try {
    if (typeof DecompressionStream !== 'function') throw new Error('This browser lacks gzip decompression.');
    const payload = JSON.parse(root.querySelector('[data-maidr-payload]').textContent);
    async function unpack(part) {
      const bytes = Uint8Array.from(atob(part.gzip), c => c.charCodeAt(0));
      const raw = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
      if (raw.byteLength !== part.bytes) throw new Error('Bundled resource size mismatch.');
      return new TextDecoder('utf-8', {fatal: true}).decode(raw);
    }
    const css = document.createElement('style');
    css.textContent = await unpack(payload.css);
    root.appendChild(css);
    // MAIDR recognizes this sentinel and does not try to load its math stylesheet.
    const math = document.createElement('link');
    math.setAttribute('data-maidr-math', '');
    root.appendChild(math);
    const runtime = document.createElement('script');
    // A lexical, in-memory storage shim only for the bundled runtime. No page globals
    // or persisted user preferences are changed, even in an opaque-origin frame.
    runtime.textContent = '(function(){const values = new Map([["maidr-settings", \'{"general":{"language":"en"}}\']]);' +
      'const localStorage = {getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,String(v)),removeItem:k=>values.delete(k)};\n' +
      await unpack(payload.runtime) + '\n})();';
    root.appendChild(runtime);
    const deadline = Date.now() + 10000;
    while (!root.querySelector('article[id^="maidr-article-"] [tabindex="0"]')) {
      if (Date.now() > deadline) throw new Error('MAIDR did not attach to the chart.');
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    root.dataset.maidrState = 'ready';
    status.remove();
  } catch (error) {
    root.dataset.maidrState = 'error';
    status.setAttribute('role', 'alert');
    status.textContent = 'Accessible chart could not start: ' + error.message +
      ' Open the standalone MAIDR HTML in a current browser; the static picture is not keyboard-accessible.';
  }
})();'''


def bundled_payload() -> dict:
    """Read only verified, vendored assets. Conversion never downloads executable code."""
    try:
        manifest = json.loads((ASSETS / "maidr-bundle.json").read_text(encoding="utf-8"))
        payload = {"format": BUNDLE_MARKER, "version": manifest["version"]}
        for key, filename in (("runtime", "maidr.js"), ("css", "maidr-math.css")):
            raw = (ASSETS / filename).read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            expected = manifest["files"][filename]
            if not raw or len(raw) != expected["bytes"] or digest != expected["sha256"]:
                raise ValueError(f"vendored {filename} does not match maidr-bundle.json; reinstall the skill")
            text = raw.decode("utf-8")
            if key == "css" and any(not (u or v).startswith("data:") for u, v in CSS_URL.findall(text)):
                raise ValueError("vendored math CSS has external dependencies; reinstall the skill")
            if key == "css":
                # KaTeX font payloads exceed the Work budget; retain layout CSS.
                raw = re.sub(r"@font-face\s*\{[^}]*\}", "", text).encode("utf-8")
                digest = hashlib.sha256(raw).hexdigest()
            payload[key] = {"bytes": len(raw), "sha256": digest,
                            "gzip": base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii")}
        return payload
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read vendored MAIDR assets: {exc}; reinstall the skill") from exc


def validate_bundle(payload_text: str, bootstrap_text: str) -> dict:
    """Validate the actual encoded resources AND exact loader, never just a marker."""
    if bootstrap_text.strip() != BOOTSTRAP:
        raise ValueError("missing or modified MAIDR gzip bootstrap")
    try:
        payload = json.loads(payload_text)
        expected = bundled_payload()
        if payload["format"] != BUNDLE_MARKER or payload["version"] != expected["version"]:
            raise ValueError("unsupported MAIDR gzip bundle format/version")
        for key in ("runtime", "css"):
            part = payload[key]
            reference = expected[key]
            if part["bytes"] != reference["bytes"] or part["sha256"] != reference["sha256"]:
                raise ValueError(f"MAIDR bundled {key} metadata does not match vendored assets")
            packed = base64.b64decode(part["gzip"], validate=True)
            with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
                raw = stream.read(reference["bytes"] + 1)
            if len(raw) != reference["bytes"] or hashlib.sha256(raw).hexdigest() != reference["sha256"]:
                raise ValueError(f"MAIDR bundled {key} payload is corrupt")
        return payload
    except (KeyError, TypeError, OSError, EOFError, ValueError, zlib.error) as exc:
        raise ValueError(f"invalid MAIDR gzip bundle: {exc}") from exc


def normalize_svg_size(html: str) -> str:
    """Give chart SVGs missing intrinsic dimensions the positive viewBox dimensions.

    MAIDR wraps the chart with fit-content; a percentage-only SVG without intrinsic
    dimensions can otherwise shrink to the browser's 300px default. Existing authored
    dimensions and all other markup remain byte-for-byte unchanged.
    """
    offsets = [0] + [m.end() for m in re.finditer("\n", html)]
    insertions = []
    class IntrinsicSize(HTMLParser):
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag != "svg" or not any(key in a for key in ("maidr", "maidr-data")):
                return
            parts = re.split(r"[\s,]+", (a.get("viewbox") or "").strip())
            number = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
            if len(parts) != 4 or not all(re.fullmatch(number, value) for value in parts):
                return
            try:
                numbers = [float(value) for value in parts]
            except ValueError:
                return
            if not all(math.isfinite(value) for value in numbers) or min(numbers[2:]) <= 0:
                return
            additions = "".join(f' {key}="{parts[index]}"'
                                for key, index in (("width", 2), ("height", 3)) if key not in a)
            if additions:
                raw = self.get_starttag_text()
                line, column = self.getpos()
                pos = offsets[line - 1] + column + len(raw) - (2 if raw.endswith("/>") else 1)
                insertions.append((pos, additions))
        handle_startendtag = handle_starttag
    parser = IntrinsicSize()
    parser.feed(html)
    for pos, additions in reversed(insertions):
        html = html[:pos] + additions + html[pos:]
    return html


def visualize(html: str, root_id: str) -> tuple[str, list[str]]:
    """Self-contained Work fragment. Claude's converter/fragment paths are unchanged."""
    html = normalize_svg_size(html)
    # Check before extracting the body: fragment() intentionally drops head <link>s.
    html = CORE_SRC.sub("", html)
    html = re.sub(r'<link\b[^>]*href=["\'][^"\']*maidr-math\.css["\'][^>]*>', '', html, flags=re.I)
    problems = visualize_problems(html)
    body = re.sub(r"<title\b[^>]*>.*?</title>\s*", "", fragment(html), flags=re.S | re.I)
    style = (f"<style>#{root_id} svg[maidr], #{root_id} svg[maidr-data] "
             "{ max-width: 100%; height: auto; }</style>")
    try:
        payload = bundled_payload()
    except ValueError as exc:
        return "", problems + [str(exc)]
    out = (f'<div id="{_html.escape(root_id, quote=True)}">\n{style}\n{body}'
           '<p data-maidr-status role="status">Loading accessible chart...</p>\n'
           f'<script type="application/json" data-maidr-payload="{BUNDLE_MARKER}">'
           + json.dumps(payload, separators=(",", ":")) + '</script>\n'
           f'<script data-maidr-bootstrap="{BUNDLE_MARKER}">{BOOTSTRAP}</script>\n</div>\n')
    if len(out.encode("utf-8")) >= VISUALIZE_LIMIT:
        problems.append(f"the visualize surface takes fragments under {VISUALIZE_LIMIT:,} bytes; plot fewer points, "
                        "or set plt.rcParams['svg.fonttype'] = 'none' before drawing")
    return out, problems


def visualize_problems(fragment_html: str) -> list[str]:
    """What in a fragment the visualize surface would not load: other hosts, local files, requests."""
    urls = []
    problems = set(source_resize_problems(fragment_html))
    markup = BODY.sub(r"\1\3", fragment_html)
    class Resources(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.styles = []
        def handle_starttag(self, name, attrs):
            for attr, value in attrs:
                if not value:
                    continue
                if attr == "style":
                    self.styles.append(value)
                if name == "a":
                    continue
                if (name == "script" and attr == "src") or (name == "link" and attr == "href"):
                    problems.add(f"external script/style dependency {value} cannot run in visualize; use a self-contained matplotlib/seaborn SVG instead")
                if attr == "srcset":
                    urls.extend(c.split()[0] for c in value.split(",") if c.strip())
                elif attr in ("src", "href", "xlink:href", "poster", "data"):
                    urls.append(value)
        handle_startendtag = handle_starttag
    resources = Resources()
    resources.feed(markup)
    css = STYLE_BLOCK.findall(fragment_html) + resources.styles
    urls += [first or second for block in css for first, second in CSS_URL.findall(block)]
    for url in (u.strip() for u in urls):
        if not url or url.startswith(("#", "data:", "blob:", "about:")):
            continue                              # in-page references and inline data load nothing from a host
        parts = urlsplit("https:" + url if url.startswith("//") else url)
        if parts.scheme in ("http", "https"):
            host = (parts.hostname or "").lower()
            if host:
                problems.add(f"{host} is blocked by the visualize CSP, so {url} will not load there; use a self-contained matplotlib/seaborn SVG instead")
        else:
            problems.add(f"{url} is a local path, and the visualize surface has no files beside the fragment")
    for attrs, code in SCRIPT.findall(fragment_html):
        kind = SCRIPT_TYPE.search(attrs)
        if re.search(r"\bsrc\s*=", attrs, re.I) or (kind and kind.group(1).lower() not in JS_TYPES):
            continue
        for api in REQUEST_API.findall(code):
            problems.add(f"an inline script uses {api}, which the visualize surface blocks")
        if re.search(r"\bimport\s*(?:\(|[\w*{])|\bimportScripts\s*\(", code):
            problems.add("module imports cannot load under the visualize CSP; use a self-contained matplotlib/seaborn SVG instead")
        if re.search(r"createElement\s*\(\s*['\"](?:script|link)['\"]", code):
            # Only this module's exact bootstrap is allowed to inject its encoded resources.
            if code.strip() != BOOTSTRAP:
                problems.add("dynamic script/style dependencies cannot be bundled; use a self-contained matplotlib/seaborn SVG instead")
    return sorted(problems)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("-o", "--output", help="output path (default: <source>-artifact.html)")
    ap.add_argument("--cdn", choices=["jsdelivr", "cdnjs"], default="jsdelivr")
    ap.add_argument("--fragment", action="store_true", help="emit title/style/script/body content only (Claude native show_widget: CDN-backed supplied HTML)")
    ap.add_argument("--visualize", action="store_true",
                    help="ChatGPT Work only: bundled fragment for its visualize surface; write it to /workspace/<title>.html")
    ap.add_argument("--title", help="artifact name; default: the page's <title>, else the chart title from the MAIDR JSON")
    a = ap.parse_args(argv)
    try:
        with open(a.source, encoding="utf-8") as fh:
            html = fh.read()
    except (OSError, UnicodeError) as exc:
        print(f"error: cannot read source {a.source}: {exc}", file=sys.stderr)
        return 1
    # Inspect the source before convert() removes its bare CDN loader. Otherwise a
    # resize callback colocated in that loader could disappear before validation.
    if a.visualize:
        source_problems = source_resize_problems(html)
        if source_problems:
            for problem in source_problems:
                print(f"error: {problem}", file=sys.stderr)
            return 1
    out, version = convert(html, a.cdn, a.title)
    dest = a.output or re.sub(r"\.html?$", "", a.source) + "-artifact.html"
    problems: list[str] = []
    if a.visualize:
        stem = os.path.splitext(os.path.basename(dest))[0].lower()
        out, problems = visualize(out, "maidr-" + (re.sub(r"[^a-z0-9]+", "-", stem).strip("-") or "chart"))
    elif a.fragment:
        out = fragment(out)
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(out)
    size = os.path.getsize(dest)
    kind = "visualize fragment" if a.visualize else "fragment" if a.fragment else "full document"
    origin = "vendored gzip/base64 (offline, English)" if a.visualize else a.cdn
    if a.visualize:
        version = bundled_payload()["version"]
    print(f"wrote {dest} ({size:,} bytes; maidr.js {version} from {origin}, {kind})")
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
