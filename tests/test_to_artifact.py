"""Regression tests for scripts/to_artifact.py.

py-maidr's Plotly and Bokeh pages put their maidr.js loader inside the script that also carries the chart, so
replacing every loader with a <script src> tag deleted those charts; only a bare loader may go. Those pages
also load their library from cdn.plot.ly or cdn.bokeh.org, which chat sandboxes block, so the script moves it
to the same file on jsDelivr. And --visualize must produce what ChatGPT Work's visualize surface takes: a
fragment with no document shell, one root element with an id, a bundled runtime with no external dependencies, under 1 MB, plus the visualize{...} line the reply carries.

Run from the repository root:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import base64
import gzip
import hashlib
from pathlib import Path
from unittest.mock import patch
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "maidr", "scripts")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "py-maidr")
TO_ARTIFACT = os.path.join(SCRIPTS, "to_artifact.py")
CHECKER = os.path.join(SCRIPTS, "check_maidr_html.py")
CORE_TAG = re.compile(r'<script src="https://cdn\.jsdelivr\.net/npm/maidr@[^"]+/dist/maidr\.js"></script>')

spec = importlib.util.spec_from_file_location("to_artifact", TO_ARTIFACT)
to_artifact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(to_artifact)


def fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


class LoaderTest(unittest.TestCase):
    def test_a_bare_loader_becomes_one_tag(self):
        out, _ = to_artifact.convert(fixture("box.html"), "jsdelivr", None)
        self.assertEqual(len(CORE_TAG.findall(out)), 1)
        self.assertNotIn("lib/maidr", out)

    def test_a_loader_inside_the_chart_script_keeps_the_chart(self):
        # The script is kept and the tag goes ahead of it: its own loader then finds the tag on the page.
        for name, chart in (("plotly_bar.html", "maidrSchema"), ("bokeh_bar.html", "embed_item")):
            with self.subTest(fixture=name):
                out, _ = to_artifact.convert(fixture(name), "jsdelivr", None)
                self.assertIn(chart, out)
                self.assertEqual(len(CORE_TAG.findall(out)), 1)
                self.assertLess(CORE_TAG.search(out).start(), out.index(chart))

    def test_a_kept_loader_looks_for_the_tag_on_either_cdn(self):
        # Its `existing` check queries the URL it would load; naming another one would load maidr.js twice.
        for host in ("jsdelivr", "cdnjs"):
            for name in ("plotly_bar.html", "bokeh_bar.html"):
                with self.subTest(host=host, fixture=name):
                    out, version = to_artifact.convert(fixture(name), host, None)
                    urls = set(re.findall(r"https://[^'\"\s]+/maidr(?:\.min)?\.js", out))
                    self.assertEqual(urls, {to_artifact.cdn_url(host, version)})

    def test_plotly_and_bokeh_move_to_jsdelivr(self):
        # Artifact sandboxes admit jsDelivr's /npm/ paths but not cdn.plot.ly or cdn.bokeh.org.
        plotly, _ = to_artifact.convert(fixture("plotly_bar.html"), "jsdelivr", None)
        self.assertNotIn("cdn.plot.ly", plotly)
        self.assertRegex(plotly, r'src="https://cdn\.jsdelivr\.net/npm/plotly\.js-dist-min@\d+\.\d+\.\d+/plotly\.min\.js"')
        bokeh, _ = to_artifact.convert(fixture("bokeh_bar.html"), "jsdelivr", None)
        self.assertNotIn("cdn.bokeh.org", bokeh)
        self.assertRegex(bokeh, r'src="https://cdn\.jsdelivr\.net/npm/@bokeh/bokehjs@\d+\.\d+\.\d+/build/js/bokeh\.min\.js"')


class VisualizeTest(unittest.TestCase):
    def run_script(self, page: str, out_name: str = "revenue-by-quarter.html"):
        tmp = tempfile.mkdtemp()
        source = os.path.join(tmp, "chart.html")
        with open(source, "w", encoding="utf-8") as fh:
            fh.write(page)
        dest = os.path.join(tmp, out_name)
        proc = subprocess.run([sys.executable, TO_ARTIFACT, source, "--visualize", "-o", dest],
                              capture_output=True, text=True)
        return proc, dest, Path(dest).read_text(encoding="utf-8") if Path(dest).exists() else ""

    def test_the_fragment_has_no_shell_and_one_root(self):
        proc, _, out = self.run_script(fixture("box.html"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for shell in ("<!doctype", "<html", "<head", "<body", "<title"):
            self.assertNotIn(shell, out.lower())
        self.assertTrue(out.startswith('<div id="maidr-revenue-by-quarter">'))
        self.assertTrue(out.rstrip().endswith("</div>"))
        self.assertIn("#maidr-revenue-by-quarter svg[maidr]", out)   # the SVG scales down with the frame
        self.assertEqual(len(CORE_TAG.findall(out)), 0)
        self.assertIn(to_artifact.BUNDLE_MARKER, out)
        self.assertLess(len(out.encode("utf-8")), 1_000_000)

    def test_it_prints_the_line_the_reply_carries(self):
        proc, dest, _ = self.run_script(fixture("box.html"))
        lines = [line for line in proc.stdout.splitlines() if line.startswith("visualize{")]
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0][len("visualize"):]), {"path": os.path.abspath(dest)})

    def test_plotly_and_bokeh_fail_actionably(self):
        for name, chart in (("plotly_bar.html", "maidrSchema"), ("bokeh_bar.html", "embed_item")):
            with self.subTest(fixture=name):
                proc, _, out = self.run_script(fixture(name))
                self.assertEqual(proc.returncode, 1, proc.stderr)
                self.assertIn("matplotlib/seaborn", proc.stderr)
                self.assertNotIn("visualize{", proc.stdout)

    def test_a_host_the_csp_blocks_fails(self):
        page = fixture("box.html").replace("</head>", '<script src="https://example.com/x.js"></script></head>')
        proc, _, _ = self.run_script(page)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("example.com", proc.stderr)
        self.assertNotIn("visualize{", proc.stdout)

    def test_every_way_of_loading_from_a_blocked_host_fails(self):
        cases = {
            "css @import": '<style>@import url("https://blocked.example/chart.css");</style>',
            "css url()": '<div style="background: url(https://blocked.example/bg.png)"></div>',
            "srcset": '<img srcset="https://cdn.jsdelivr.net/npm/x/a.png 1x, https://blocked.example/b.png 2x">',
            "svg image": '<svg><image href="https://blocked.example/i.png"/></svg>',
            "unquoted CDN": '<script src=https://cdn.jsdelivr.net/npm/d3></script>',
            "protocol-relative": '<script src="//blocked.example/x.js"></script>',
        }
        for form, snippet in cases.items():
            with self.subTest(form=form):
                proc, _, _ = self.run_script(fixture("box.html").replace("</body>", snippet + "</body>"))
                self.assertEqual(proc.returncode, 1)
                self.assertIn("cdn.jsdelivr.net" if form == "unquoted CDN" else "blocked.example", proc.stderr)
                self.assertNotIn("visualize{", proc.stdout)

    def test_requests_and_local_files_fail(self):
        cases = {
            "fetch": ("<script>fetch('/data.json')</script>", "fetch"),
            "XMLHttpRequest": ("<script>new XMLHttpRequest()</script>", "XMLHttpRequest"),
            "WebSocket": ("<script>new WebSocket('wss://blocked.example')</script>", "WebSocket"),
            "local file": ('<script src="./chart-data.js"></script>', "./chart-data.js"),
        }
        for form, (snippet, needle) in cases.items():
            with self.subTest(form=form):
                proc, _, _ = self.run_script(fixture("box.html").replace("</body>", snippet + "</body>"))
                self.assertEqual(proc.returncode, 1)
                self.assertIn(needle, proc.stderr)

    def test_links_and_in_page_references_pass(self):
        # A link navigates rather than loads, and xlink:href="#id" points inside the page, as matplotlib's do.
        page = fixture("box.html").replace(
            "</body>", '<a href="https://example.com/about">About</a><svg><use xlink:href="#m1"/></svg></body>')
        proc, _, _ = self.run_script(page)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_data_and_strings_inside_scripts_pass(self):
        # A JSON data island is not code, and markup quoted inside a script is not a tag on the page.
        snippet = ('<script type="application/json" id="d">{"step": "fetch the logs"}</script>'
                   "<script>var tip = '<img src=\"https://example.com/i.png\">';</script>"
                   '<img data-src="https://example.com/lazy.png" alt="">')
        proc, _, _ = self.run_script(fixture("box.html").replace("</body>", snippet + "</body>"))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_a_fragment_of_1_mb_fails(self):
        page = fixture("box.html").replace("</svg>", "<!--" + "x" * 1_000_000 + "--></svg>", 1)
        proc, _, _ = self.run_script(page)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("1,000,000", proc.stderr)

    def test_the_checker_passes_the_fragment(self):
        _, dest, _ = self.run_script(fixture("box.html"))
        proc = subprocess.run([sys.executable, CHECKER, dest], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class BundleTest(unittest.TestCase):
    def test_decoded_runtime_is_exactly_vendored_and_under_cap(self):
        payload = to_artifact.bundled_payload()
        raw = gzip.decompress(base64.b64decode(payload["runtime"]["gzip"], validate=True))
        self.assertEqual(raw, (to_artifact.ASSETS / "maidr.js").read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), payload["runtime"]["sha256"])
        self.assertNotIn(b"@font-face", gzip.decompress(base64.b64decode(payload["css"]["gzip"])))
        to_artifact.validate_bundle(json.dumps(payload), to_artifact.BOOTSTRAP)
        out, issues = to_artifact.visualize(to_artifact.convert(fixture("box.html"), "jsdelivr", None)[0], "maidr-test")
        self.assertEqual(issues, [])
        self.assertLess(len(out.encode("utf-8")), to_artifact.VISUALIZE_LIMIT)
        self.assertNotRegex(out, r"<script[^>]+src=")
        self.assertNotRegex(to_artifact.BOOTSTRAP, to_artifact.REQUEST_API)
        self.assertEqual(to_artifact.visualize_problems(out), [])

    def test_corruption_and_missing_bootstrap_are_rejected(self):
        payload = to_artifact.bundled_payload()
        with self.assertRaisesRegex(ValueError, "bootstrap"):
            to_artifact.validate_bundle(json.dumps(payload), "")
        payload["runtime"]["gzip"] = "not base64!"
        with self.assertRaisesRegex(ValueError, "invalid MAIDR gzip bundle"):
            to_artifact.validate_bundle(json.dumps(payload), to_artifact.BOOTSTRAP)
        with self.assertRaises(ValueError):
            to_artifact.validate_bundle("{}", to_artifact.BOOTSTRAP)

    def test_missing_or_modified_vendored_source_is_precise(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(to_artifact, "ASSETS", Path(tmp)):
            with self.assertRaisesRegex(ValueError, "cannot read vendored"):
                to_artifact.bundled_payload()
        with patch.object(Path, "read_bytes", return_value=b"broken"):
            with self.assertRaisesRegex(ValueError, "does not match"):
                to_artifact.bundled_payload()

    def test_missing_input_is_not_a_traceback(self):
        proc = subprocess.run([sys.executable, TO_ARTIFACT, "missing-source-12345.html", "--visualize"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("cannot read source", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_checker_rejects_tampered_bootstrap_and_keeps_schema_checks(self):
        out, _ = to_artifact.visualize(to_artifact.convert(fixture("box.html"), "jsdelivr", None)[0], "maidr-test")
        for page, needle in ((out.replace("async function ()", "async function (bad)"), "bootstrap"),
                             (out.replace('maidr=', 'maidr-data=', 1).replace('&quot;box&quot;', '&quot;not-a-type&quot;'), "not-a-type")):
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "chart.html"
                dest.write_text(page, encoding="utf-8")
                proc = subprocess.run([sys.executable, CHECKER, str(dest)], capture_output=True, text=True)
                self.assertEqual(proc.returncode, 1, proc.stdout)
                self.assertIn(needle, proc.stdout)


if __name__ == "__main__":
    unittest.main()
