"""Regression tests for scripts/to_artifact.py.

py-maidr's Plotly and Bokeh pages put their maidr.js loader inside the script that also carries the chart, so
replacing every loader with a <script src> tag deleted those charts; only a bare loader may go. Those pages
also load their library from cdn.plot.ly or cdn.bokeh.org, which chat sandboxes block, so the script moves it
to the same file on jsDelivr.

Run from the repository root:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import importlib.util
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "maidr", "scripts")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "py-maidr")
TO_ARTIFACT = os.path.join(SCRIPTS, "to_artifact.py")
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

    def test_plotly_and_bokeh_move_to_jsdelivr(self):
        # Artifact sandboxes admit jsDelivr's /npm/ paths but not cdn.plot.ly or cdn.bokeh.org.
        plotly, _ = to_artifact.convert(fixture("plotly_bar.html"), "jsdelivr", None)
        self.assertNotIn("cdn.plot.ly", plotly)
        self.assertRegex(plotly, r'src="https://cdn\.jsdelivr\.net/npm/plotly\.js-dist-min@\d+\.\d+\.\d+/plotly\.min\.js"')
        bokeh, _ = to_artifact.convert(fixture("bokeh_bar.html"), "jsdelivr", None)
        self.assertNotIn("cdn.bokeh.org", bokeh)
        self.assertRegex(bokeh, r'src="https://cdn\.jsdelivr\.net/npm/@bokeh/bokehjs@\d+\.\d+\.\d+/build/js/bokeh\.min\.js"')


if __name__ == "__main__":
    unittest.main()
