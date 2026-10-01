"""Regression tests for scripts/to_artifact.py.

py-maidr's Plotly and Bokeh pages put their maidr.js loader inside the script that also carries the chart, so
replacing every loader with a <script src> tag deleted those charts; only a bare loader may go. Those pages
also load their library from cdn.plot.ly or cdn.bokeh.org, which chat sandboxes block, so the script moves it
to the same file on jsDelivr. And --visualize must produce what ChatGPT Work's visualize surface takes: a
fragment with no document shell, one root element with an id, resources only from the hosts that surface's
CSP admits, under 1 MB, plus the visualize{...} line the reply carries.

Run from the repository root:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

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
        with open(dest, encoding="utf-8") as fh:
            return proc, dest, fh.read()

    def test_the_fragment_has_no_shell_and_one_root(self):
        proc, _, out = self.run_script(fixture("box.html"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for shell in ("<!doctype", "<html", "<head", "<body", "<title"):
            self.assertNotIn(shell, out.lower())
        self.assertTrue(out.startswith('<div id="maidr-revenue-by-quarter">'))
        self.assertTrue(out.rstrip().endswith("</div>"))
        self.assertIn("#maidr-revenue-by-quarter svg[maidr]", out)   # the SVG scales down with the frame
        self.assertEqual(len(CORE_TAG.findall(out)), 1)

    def test_it_prints_the_line_the_reply_carries(self):
        proc, dest, _ = self.run_script(fixture("box.html"))
        lines = [line for line in proc.stdout.splitlines() if line.startswith("visualize{")]
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0][len("visualize"):]), {"path": os.path.abspath(dest)})

    def test_plotly_and_bokeh_pass(self):
        for name, chart in (("plotly_bar.html", "maidrSchema"), ("bokeh_bar.html", "embed_item")):
            with self.subTest(fixture=name):
                proc, _, out = self.run_script(fixture(name))
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn(chart, out)

    def test_a_host_the_csp_blocks_fails(self):
        page = fixture("box.html").replace("</head>", '<script src="https://example.com/x.js"></script></head>')
        proc, _, _ = self.run_script(page)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("example.com", proc.stderr)
        self.assertNotIn("visualize{", proc.stdout)

    def test_a_fragment_of_1_mb_fails(self):
        page = fixture("box.html").replace("</svg>", "<!--" + "x" * 1_000_000 + "--></svg>", 1)
        proc, _, _ = self.run_script(page)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("1,000,000", proc.stderr)

    def test_the_checker_passes_the_fragment(self):
        _, dest, _ = self.run_script(fixture("box.html"))
        proc = subprocess.run([sys.executable, CHECKER, dest], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
