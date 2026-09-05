#!/usr/bin/env python3
"""check_maidr_html.py - static (and optional headless-browser) checks for a MAIDR-enabled HTML file.

Usage:
    python check_maidr_html.py FILE.html [--browser] [--json]

Exit codes: 0 = no errors (warnings allowed), 1 = errors found, 2 = usage or I/O problem.

Only the Python standard library is required. Two optional extras improve coverage:
    beautifulsoup4  -> counts how many elements each `selectors` CSS selector matches
    playwright      -> `--browser` loads the page headlessly and confirms maidr initialized

What is checked
    * maidr.js is loaded: a <script src> on jsDelivr/cdnjs/local disk, an inline loader chain,
      an inlined bundle, or a self-contained adapter bundle (Chart.js, amCharts).
    * Local script paths exist relative to the HTML file; maidr-math.css sits beside a local bundle.
    * Some attachment method exists: `maidr` / `maidr-data` attribute JSON, a `window.maidr`
      global, a Plotly chart (auto-detected by maidr), or an adapter bundle.
    * Every attribute JSON parses and follows the MAIDR schema: id, subplots grid, layers with
      id/type/data, axes as objects (not bare strings), known trace types, data shaped for the
      type, selectors resolving to one element per data point.
"""
from __future__ import annotations

import json
import os
import re
import sys
from html.parser import HTMLParser

MAIDR_VERSION = "4.6.0"

STABLE = {
    "bar", "box", "candlestick", "dodged_bar", "heat", "hist", "line", "pie", "point", "smooth",
    "stacked_bar", "stacked_normalized_bar", "step", "violin_box", "violin_kde",
}
EXPERIMENTAL = {
    "alluvial", "area", "boxen", "bump", "chord", "choropleth", "contour", "diverging_bar", "dot",
    "dumbbell", "error_bar", "forest", "funnel", "gantt", "gauge", "hexbin", "icicle", "lollipop",
    "manhattan", "mosaic", "network", "pack", "parallel_coordinates", "polar_area", "radar",
    "ridgeline", "sankey", "stacked_area", "stacked_normalized_area", "sunburst", "sunflower",
    "survival", "tree", "treemap", "volcano", "waterfall", "word_cloud",
}
KNOWN = STABLE | EXPERIMENTAL
# data container shape by trace type
NESTED = {"line", "step", "smooth", "dodged_bar", "stacked_bar", "stacked_normalized_bar",
          "violin_kde", "area", "stacked_area", "stacked_normalized_area"}
OBJECT = {"heat"}
# adapters whose bundle already contains the maidr core (their docs load no separate maidr.js)
SELF_CONTAINED_ADAPTERS = {"chartjs", "amcharts", "recharts", "victory", "react"}
ADAPTERS = {"d3", "chartjs", "highcharts", "echarts", "vegalite", "recharts", "victory", "amcharts",
            "anychart", "frappe", "google-charts", "observable", "tableau", "react"}


class Report:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, level: str, msg: str) -> None:
        self.items.append({"level": level, "message": msg})

    def error(self, msg: str) -> None: self.add("ERROR", msg)
    def warn(self, msg: str) -> None: self.add("WARN", msg)
    def info(self, msg: str) -> None: self.add("INFO", msg)

    @property
    def errors(self) -> int: return sum(1 for i in self.items if i["level"] == "ERROR")
    @property
    def warnings(self) -> int: return sum(1 for i in self.items if i["level"] == "WARN")


class Collector(HTMLParser):
    """Collects scripts, ids, and elements carrying MAIDR attributes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: list[dict] = []
        self._script: dict | None = None
        self.maidr_elements: list[dict] = []
        self.marker_attrs = 0  # maidr="<uuid>" markers written by py-maidr; maidr.js ignores non-JSON values
        self.ids: set[str] = set()
        self.svg_count = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "svg":
            self.svg_count += 1
        if tag == "script":
            self._script = {"src": a.get("src"), "type": a.get("type"), "text": ""}
            self.scripts.append(self._script)
        for key in ("maidr", "maidr-data"):
            val = a.get(key)
            if val is None:
                continue
            if val.lstrip().startswith(("{", "[")):
                self.maidr_elements.append({"tag": tag, "id": a.get("id"), "attr": key, "json": val})
            else:
                self.marker_attrs += 1

    def handle_endtag(self, tag):
        if tag == "script":
            self._script = None

    def handle_data(self, data):
        if self._script is not None:
            self._script["text"] += data


def classify_src(src: str) -> str:
    s = src.lower()
    if "cdn.jsdelivr.net" in s:
        return "jsdelivr"
    if "cdnjs.cloudflare.com" in s:
        return "cdnjs"
    if s.startswith(("http://", "https://", "//")):
        return "other-cdn"
    return "local"


def check_scripts(col: Collector, html_dir: str, rep: Report) -> dict:
    found = {"core": [], "adapters": set(), "loader": False, "inlined": False, "plotly": False,
             "global_var": False}
    for sc in col.scripts:
        src, text = sc["src"], sc["text"]
        if src:
            base = os.path.basename(src.split("?")[0]).lower()
            kind = classify_src(src)
            if re.fullmatch(r"maidr(\.min)?\.js", base) or re.search(r"/npm/maidr(@[^/]*)?/dist/maidr(\.min)?\.js", src):
                found["core"].append((src, kind))
                if kind in ("jsdelivr", "cdnjs"):
                    m = re.search(r"maidr@([^/]+)/", src) or re.search(r"/libs/maidr/([^/]+)/", src)
                    ver = m.group(1) if m else None
                    if ver in (None, "latest") and kind == "jsdelivr":
                        rep.warn(f"maidr.js loaded unpinned ({src}); pin a version such as maidr@{MAIDR_VERSION} so the page does not change under the reader")
                    elif ver and ver not in ("latest", MAIDR_VERSION):
                        rep.info(f"maidr.js pinned to {ver}; this skill was written against {MAIDR_VERSION}")
                if kind == "local":
                    path = os.path.normpath(os.path.join(html_dir, src))
                    if not os.path.exists(path):
                        rep.error(f"local maidr.js not found at {path} (copy assets/maidr.js next to the HTML or use a CDN URL)")
                    else:
                        css = os.path.join(os.path.dirname(path), "maidr-math.css")
                        if not os.path.exists(css):
                            rep.info(f"no maidr-math.css beside {path}; only affects math formatting in AI-chat replies")
                if kind == "other-cdn":
                    rep.warn(f"maidr.js loaded from an unrecognized host ({src}); jsDelivr and cdnjs are the supported CDNs")
            m = re.search(r"/dist/(" + "|".join(re.escape(a) for a in ADAPTERS) + r")\.m?js", src)
            if m:
                found["adapters"].add(m.group(1))
                if kind == "cdnjs":
                    rep.error(f"adapter bundle {src} requested from cdnjs, which mirrors only the core maidr.js; load adapters from jsDelivr")
            if "plotly" in src.lower() or "plot.ly" in src.lower():
                found["plotly"] = True
        elif text:
            if "cdn.jsdelivr.net/npm/maidr@" in text or "cdnjs.cloudflare.com/ajax/libs/maidr/" in text:
                found["loader"] = True
            if len(text) > 200_000 and "maidr-figure" in text:
                found["inlined"] = True
            if re.search(r"Plotly\.(newPlot|react|plot)\s*\(", text):
                found["plotly"] = True
            if re.search(r"(?:^|[^\w.])(?:var|let|const)\s+maidr\s*=|window\.maidr\s*=", text):
                found["global_var"] = True
                found["global_text"] = text
    return found


def check_data_shape(layer_type: str, data, where: str, rep: Report) -> int:
    """Validate the data container and point fields for a layer. Returns the number of points."""
    if layer_type in OBJECT:
        if not isinstance(data, dict):
            rep.error(f"{where}: type '{layer_type}' expects data to be an object {{points, x, y}}")
            return 0
        pts, xs, ys = data.get("points"), data.get("x"), data.get("y")
        if not (isinstance(pts, list) and pts and all(isinstance(r, list) for r in pts)):
            rep.error(f"{where}: heat data.points must be a non-empty 2-D array")
            return 0
        if not isinstance(xs, list) or not isinstance(ys, list):
            rep.error(f"{where}: heat data.x and data.y must be arrays of labels")
            return 0
        if len(ys) != len(pts) or any(len(r) != len(xs) for r in pts):
            rep.error(f"{where}: heat dimensions disagree (points is {len(pts)}x{len(pts[0])}, x has {len(xs)}, y has {len(ys)})")
        return sum(len(r) for r in pts)

    if not isinstance(data, list) or not data:
        rep.error(f"{where}: data must be a non-empty array")
        return 0

    if layer_type in NESTED:
        if not all(isinstance(series, list) for series in data):
            rep.error(f"{where}: type '{layer_type}' expects nested data: one inner array per series, e.g. [[{{x,y}}, ...]]")
            return 0
        points = [p for series in data for p in series]
        for p in points[:50]:
            if not isinstance(p, dict) or "x" not in p or "y" not in p:
                rep.error(f"{where}: every point needs x and y (got {json.dumps(p)[:80]})")
                break
            if layer_type in ("dodged_bar", "stacked_bar", "stacked_normalized_bar") and not ("fill" in p or "z" in p):
                rep.warn(f"{where}: grouped bar points should carry a 'fill' (group name); got {json.dumps(p)[:80]}")
                break
        return len(points)

    if all(isinstance(series, list) for series in data):
        rep.error(f"{where}: type '{layer_type}' expects a flat array of points, but data is nested")
        return 0
    if not all(isinstance(p, dict) for p in data):
        rep.error(f"{where}: data points must be objects")
        return 0
    required = {
        "bar": {"x", "y"}, "pie": {"x", "y"}, "point": {"x", "y"}, "dot": {"x", "y"},
        "hist": {"x", "y", "xMin", "xMax"}, "box": {"min", "q1", "q2", "q3", "max"},
        "violin_box": {"min", "q1", "q2", "q3", "max"}, "candlestick": {"value", "open", "high", "low", "close"},
    }.get(layer_type, set())
    for p in data:
        missing = required - set(p)
        if missing:
            rep.error(f"{where}: point {json.dumps(p)[:80]} is missing {sorted(missing)}")
            break
    if layer_type == "pie":
        bad = [p for p in data if not isinstance(p.get("y"), (int, float))]
        if bad:
            rep.error(f"{where}: pie slice values (y) must be numbers; got {json.dumps(bad[0])[:80]}")
    if layer_type == "point":
        bad = [p for p in data if not isinstance(p.get("x"), (int, float)) or not isinstance(p.get("y"), (int, float))]
        if bad:
            rep.warn(f"{where}: scatter coordinates should be numeric; use xLabel/yLabel for category names (got {json.dumps(bad[0])[:80]})")
    return len(data)


NUMBER = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?", re.I)


def vertex_count(el):
    """Vertices maidr can highlight on a line element: (count, problem). count is None when unknown."""
    if el.name in ("polyline", "polygon"):
        return len(NUMBER.findall(el.get("points", ""))) // 2, None
    if el.name == "path":
        d = el.get("d", "")
        commands = set(re.findall(r"[A-Za-z]", d))
        if commands & set("CcQqSsTtAa"):
            return None, "curved"
        if commands & set("HhVv"):
            return None, "hv"
        return len(NUMBER.findall(d)) // 2, None
    return None, "not-a-path"


def drawn(elements):
    """Drop matches inside <defs> (markers, clip paths); they are definitions, not drawn marks."""
    return [e for e in elements if e.find_parent("defs") is None]


def check_line_selectors(selectors, data, where: str, soup, rep: Report) -> None:
    """One path per series, one straight-segment vertex per point: that is what maidr walks when highlighting a line."""
    series = [s for s in data if isinstance(s, list)] if isinstance(data, list) else []
    try:
        if isinstance(selectors, str):
            matched = drawn(soup.select(selectors))
        else:
            matched = [m[0] for m in (drawn(soup.select(s)) for s in selectors if isinstance(s, str)) if m]
    except Exception as exc:
        rep.error(f"{where}: selectors are not valid CSS ({exc})")
        return
    if len(matched) != len(series):
        rep.warn(f"{where}: selectors match {len(matched)} element(s) for {len(series)} series; a line needs one path (or polyline) per series, in order")
        return
    for i, (el, s) in enumerate(zip(matched, series)):
        count, problem = vertex_count(el)
        if problem == "curved":
            rep.warn(f"{where} series[{i}]: <path> uses curve commands; maidr highlights vertices, so draw straight M/L segments with one vertex per point")
        elif problem == "not-a-path":
            rep.warn(f"{where} series[{i}]: selector matched <{el.name}>, expected a <path> or <polyline>")
        elif count is not None and count != len(s):
            rep.warn(f"{where} series[{i}]: path has {count} vertices but the series has {len(s)} points; highlighting will drift from the announced point")


def check_selectors(selectors, n_points: int, layer_type: str, where: str, soup, rep: Report, data=None) -> None:
    if selectors is None:
        rep.info(f"{where}: no selectors; navigation works but nothing is highlighted visually")
        return
    # A one-element list is the same as a single selector string (r-maidr emits this form).
    if isinstance(selectors, list) and len(selectors) == 1 and isinstance(selectors[0], str):
        selectors = selectors[0]
    if layer_type == "line" and soup is not None and isinstance(selectors, (str, list)):
        check_line_selectors(selectors, data, where, soup, rep)
        return
    if isinstance(selectors, str):
        if soup is None or layer_type in NESTED:
            return
        try:
            matched = len(drawn(soup.select(selectors)))
        except Exception as exc:  # bad CSS
            rep.error(f"{where}: selectors '{selectors}' is not a valid CSS selector ({exc})")
            return
        if matched == 0:
            rep.error(f"{where}: selectors '{selectors}' matches no element in the document")
        elif matched != n_points:
            rep.error(f"{where}: selectors '{selectors}' matches {matched} elements but data has {n_points} points; highlighting would land on the wrong marks")
    elif isinstance(selectors, list):
        if layer_type in NESTED:
            return
        if len(selectors) != n_points:
            rep.warn(f"{where}: selectors list has {len(selectors)} entries for {n_points} data points")


def check_layer(layer, where: str, soup, rep: Report) -> None:
    if not isinstance(layer, dict):
        rep.error(f"{where}: layer must be an object")
        return
    if not layer.get("id"):
        rep.warn(f"{where}: layer has no id")
    t = layer.get("type")
    if not t:
        rep.error(f"{where}: layer has no type")
        return
    if t == "candlestick_delta":
        rep.error(f"{where}: 'candlestick_delta' is derived at runtime from a 'candlestick' layer and must not be declared")
        return
    if t == "scatter":
        rep.error(f"{where}: type 'scatter' does not exist; the scatter trace type is 'point'")
        return
    if t == "histogram":
        rep.error(f"{where}: type 'histogram' does not exist; use 'hist'")
        return
    if t == "heatmap":
        rep.error(f"{where}: type 'heatmap' does not exist; use 'heat'")
        return
    if t not in KNOWN:
        rep.error(f"{where}: unknown trace type '{t}'")
        return
    if t in EXPERIMENTAL:
        rep.warn(f"{where}: trace type '{t}' is experimental in maidr {MAIDR_VERSION}; its reading may change without notice")
    axes = layer.get("axes")
    if axes is not None:
        if not isinstance(axes, dict):
            rep.error(f"{where}: axes must be an object with x/y(/z) entries")
        else:
            for k, v in axes.items():
                if isinstance(v, str):
                    rep.error(f"{where}: axes.{k} is a bare string ('{v}'); use {{\"label\": \"{v}\"}}")
                elif isinstance(v, dict) and not v.get("label"):
                    rep.warn(f"{where}: axes.{k} has no label; it will be announced as the default axis name")
            if t not in ("pie",) and not ({"x", "y"} <= set(axes)):
                rep.warn(f"{where}: axes should name both x and y")
    else:
        rep.warn(f"{where}: no axes labels; readers will hear 'X' and 'Y'")
    if "data" not in layer:
        rep.error(f"{where}: layer has no data")
        return
    n = check_data_shape(t, layer["data"], where, rep)
    if n:
        check_selectors(layer.get("selectors"), n, t, where, soup, rep, layer["data"])


def check_json_blob(raw: str, el: dict, col: Collector, soup, rep: Report) -> None:
    where = f"<{el['tag']} id={el['id']!r} {el['attr']}>"
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        snippet = raw.strip()[:60].replace("\n", " ")
        rep.error(f"{where}: attribute is not valid JSON ({exc.msg} at char {exc.pos}); starts with: {snippet}")
        return
    if not isinstance(doc, dict):
        rep.error(f"{where}: MAIDR JSON must be a single object (one attribute per chart), not an array")
        return
    if not doc.get("id"):
        rep.error(f"{where}: top-level id is required")
    elif el["id"] and doc["id"] != el["id"]:
        rep.warn(f"{where}: JSON id '{doc['id']}' differs from the element id '{el['id']}'; keep them equal")
    if not (doc.get("title") or any(
            isinstance(l, dict) and l.get("title")
            for row in (doc.get("subplots") or []) if isinstance(row, list)
            for sp in row if isinstance(sp, dict)
            for l in (sp.get("layers") or []))):
        rep.warn(f"{where}: no title anywhere; add a figure or layer title so the chart is announced by name")
    sub = doc.get("subplots")
    if not (isinstance(sub, list) and sub and all(isinstance(row, list) and row for row in sub)):
        rep.error(f"{where}: subplots must be a non-empty 2-D array: [[{{layers: [...]}}]] for a single chart")
        return
    for r, row in enumerate(sub):
        for c, sp in enumerate(row):
            w = f"{where} subplot[{r}][{c}]"
            if not isinstance(sp, dict):
                rep.error(f"{w}: must be an object")
                continue
            layers = sp.get("layers")
            if not (isinstance(layers, list) and layers):
                rep.error(f"{w}: layers must be a non-empty array")
                continue
            for i, layer in enumerate(layers):
                check_layer(layer, f"{w} layer[{i}]", soup, rep)
    n_sub = sum(len(row) for row in sub)
    if n_sub > 1:
        rep.info(f"{where}: multi-panel figure with {n_sub} subplots in a {len(sub)}-row grid")


def browser_check(path: str, rep: Report) -> None:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        rep.warn("--browser requested but the playwright package is not installed (pip install playwright && playwright install chromium)")
        return
    url = "file:///" + os.path.abspath(path).replace("\\", "/")
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        try:
            page.wait_for_function("() => document.querySelector('[id^=\"maidr-figure\"], [id^=\"maidr-article\"], .js-plotly-plot [maidr-data]') !== null", timeout=8000)
            rep.info("browser: maidr initialized (a maidr-figure-* container wraps the chart)")
        except Exception:
            rep.error("browser: maidr did not initialize within 8 s (no maidr-figure-* container appeared); check the console errors and the JSON")
        for e in errors:
            rep.error(f"browser console: {e[:300]}")
        browser.close()


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    if len(args) != 1:
        print(__doc__)
        return 2
    path = args[0]
    if not os.path.isfile(path):
        print(f"not a file: {path}")
        return 2
    with open(path, encoding="utf-8", errors="replace") as fh:
        html = fh.read()
    rep = Report()
    col = Collector()
    col.feed(html)
    soup = None
    try:
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        rep.info("beautifulsoup4 not installed; selector counts were not verified (pip install beautifulsoup4)")

    found = check_scripts(col, os.path.dirname(os.path.abspath(path)), rep)
    self_contained = found["adapters"] & SELF_CONTAINED_ADAPTERS
    if not (found["core"] or found["loader"] or found["inlined"] or self_contained):
        rep.error("maidr.js is not loaded: add <script src=\"https://cdn.jsdelivr.net/npm/maidr@%s/dist/maidr.js\"></script> (or the cdnjs/local fallback)" % MAIDR_VERSION)
    else:
        srcs = ", ".join(f"{k}" for _, k in found["core"]) or ("inline loader" if found["loader"] else "inlined bundle" if found["inlined"] else "adapter bundle")
        rep.info(f"maidr.js source: {srcs}")
    if found["adapters"]:
        rep.info(f"adapter bundles: {', '.join(sorted(found['adapters']))}")
        thin = found["adapters"] - SELF_CONTAINED_ADAPTERS
        if thin and not (found["core"] or found["loader"] or found["inlined"]):
            rep.error(f"adapter(s) {sorted(thin)} need maidr.js loaded first")

    attached = bool(col.maidr_elements) or found["global_var"] or found["plotly"] or bool(found["adapters"])
    if col.marker_attrs and not attached:
        rep.error(f"{col.marker_attrs} element(s) carry a maidr attribute whose value is not JSON; maidr.js only reads values that start with '{{'")
    if not attached:
        rep.error("no chart is attached to maidr: add a maidr='{...}' attribute on the <svg>, an adapter bind call, or a Plotly chart")
    for el in col.maidr_elements:
        check_json_blob(el["json"], el, col, soup, rep)
    if found["global_var"]:
        m = re.search(r"""["']?id["']?\s*:\s*["']([^"']+)["']""", found.get("global_text", ""))
        if m and m.group(1) not in col.ids:
            rep.error(f"window.maidr.id is '{m.group(1)}' but no element has that id; with the global-variable method the ids must match")
        rep.info("window.maidr global detected; its object literal was not validated statically (prefer the maidr attribute)")
    if found["plotly"] and not col.maidr_elements:
        rep.info("Plotly chart detected; maidr auto-detects Plotly, no JSON needed")
    if col.svg_count == 0 and not found["plotly"] and not found["adapters"]:
        rep.warn("no <svg> in the document; maidr needs an SVG (or a supported library chart) to highlight")

    if "--browser" in flags:
        browser_check(path, rep)

    if "--json" in flags:
        print(json.dumps({"file": path, "errors": rep.errors, "warnings": rep.warnings, "items": rep.items}, indent=2))
    else:
        for item in rep.items:
            print(f"{item['level']:5} {item['message']}")
        print(f"\n{path}: {rep.errors} error(s), {rep.warnings} warning(s)")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
