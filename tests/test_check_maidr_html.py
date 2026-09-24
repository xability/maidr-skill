"""Regression tests for skills/maidr/scripts/check_maidr_html.py.

The checker is only useful while it agrees with the maidr.js release the skill
vendors: an ERROR on a payload maidr reads correctly sends an agent to "fix"
working output, and a pass on one maidr declines hides a lost highlight. Each
case here is a payload whose reading was confirmed in maidr's source (the
comment names where) or real binding output under tests/fixtures/.

Run from the repository root:

    python -m unittest discover -s tests -v

Selector checks need beautifulsoup4 and are skipped without it; CI installs it.
"""
from __future__ import annotations

import html
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKER = os.path.join(ROOT, "skills", "maidr", "scripts", "check_maidr_html.py")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
CDN = "https://cdn.jsdelivr.net/npm/maidr@4.10.0/dist/maidr.js"

try:
    import bs4  # noqa: F401
    HAVE_BS4 = True
except ImportError:
    HAVE_BS4 = False


def run(path: str) -> dict:
    out = subprocess.run([sys.executable, CHECKER, path, "--json"], capture_output=True, text=True)
    result = json.loads(out.stdout)
    result["exit"] = out.returncode
    return result


def messages(result: dict, level: str) -> list[str]:
    return [i["message"] for i in result["items"] if i["level"] == level]


def layer(type_: str, data, **extra) -> dict:
    return {"id": "l0", "type": type_, "title": "T",
            "axes": {"x": {"label": "x"}, "y": {"label": "y"}}, "data": data, **extra}


def figure(*subplot_rows) -> dict:
    return {"id": "c", "title": "T", "subplots": [list(row) for row in subplot_rows]}


class CheckerCase(unittest.TestCase):
    def check_doc(self, doc: dict, svg_body: str = "") -> dict:
        page = (f'<!DOCTYPE html><html><head><script src="{CDN}"></script></head><body>'
                f'<svg id="c" maidr="{html.escape(json.dumps(doc))}">{svg_body}</svg></body></html>')
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
            fh.write(page)
        try:
            return run(fh.name)
        finally:
            os.unlink(fh.name)

    def assertClean(self, result: dict) -> None:
        self.assertEqual(result["exit"], 0, messages(result, "ERROR"))
        self.assertEqual(messages(result, "ERROR"), [])

    def assertErrorMentions(self, result: dict, needle: str) -> None:
        self.assertEqual(result["exit"], 1)
        self.assertTrue(any(needle in m for m in messages(result, "ERROR")),
                        f"no ERROR mentions {needle!r}: {messages(result, 'ERROR')}")


BAR = layer("bar", [{"x": "A", "y": 1}])


class TemplateTest(CheckerCase):
    def test_template_is_clean(self):
        result = run(os.path.join(ROOT, "skills", "maidr", "assets", "template.html"))
        self.assertClean(result)
        self.assertEqual(messages(result, "WARN"), [])


class EmptySubplotTest(CheckerCase):
    """maidr/src/model/plot.ts: a subplot with `layers: []` is a supported, navigable empty cell."""

    def test_empty_middle_cell_is_accepted(self):
        result = self.check_doc(figure([{"layers": [BAR]}, {"layers": []}, {"layers": [BAR]}]))
        self.assertClean(result)
        self.assertTrue(any("empty subplot" in m for m in messages(result, "INFO")))

    def test_missing_layers_is_a_warning(self):
        # Figure warns in the console and reads the cell as empty; it does not fail.
        result = self.check_doc(figure([{"layers": [BAR]}, {"id": "p1"}]))
        self.assertClean(result)
        self.assertTrue(any("no layers array" in m for m in messages(result, "WARN")))

    def test_all_empty_is_a_warning(self):
        result = self.check_doc(figure([{"layers": []}]))
        self.assertClean(result)
        self.assertTrue(any("every subplot is empty" in m for m in messages(result, "WARN")))

    def test_py_maidr_empty_panel(self):
        result = run(os.path.join(FIXTURES, "py-maidr", "empty_panel.html"))
        self.assertClean(result)


def load_checker():
    spec = importlib.util.spec_from_file_location("check_maidr_html", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TraceTypeTest(CheckerCase):
    def test_known_types_match_the_vendored_bundle(self):
        # The checker's list drifted once already (roc and rug, read since 4.9.0, were rejected
        # as unknown); tie it to the TraceType enum inside the maidr.js the skill vendors.
        with open(os.path.join(ROOT, "skills", "maidr", "assets", "maidr.js"), encoding="utf-8") as fh:
            bundle = fh.read()
        # A TypeScript string enum compiles to function(e){return e.AREA=`area`,...,e}({}).
        enums = re.finditer(r"function\((\w)\)\{return ((?:\1\.\w+=`[^`]*`,)+)\1\}", bundle)
        body = next((m.group(2) for m in enums if "CANDLESTICK_DELTA=" in m.group(2)), None)
        self.assertIsNotNone(body, "TraceType enum not found in the vendored maidr.js")
        core = set(re.findall(r"=`([^`]*)`", body))
        self.assertIn("candlestick_delta", core)
        self.assertEqual(load_checker().KNOWN, core - {"candlestick_delta"})

    def test_roc(self):
        data = [[{"x": 0, "y": 0}, {"x": 0.5, "y": 0.8}, {"x": 1, "y": 1}]]
        self.assertClean(self.check_doc(figure([{"layers": [layer("roc", data)]}])))

    def test_rug(self):
        self.assertClean(self.check_doc(figure([{"layers": [layer("rug", [{"x": 1.5}, {"x": 2.5}])]}])))
        horizontal = layer("rug", [{"y": 1.5}], orientation="horz")
        self.assertClean(self.check_doc(figure([{"layers": [horizontal]}])))
        self.assertErrorMentions(self.check_doc(figure([{"layers": [layer("rug", [{"v": 1}])]}])),
                                 "neither x nor y")

    def test_candlestick_delta_is_still_rejected(self):
        result = self.check_doc(figure([{"layers": [layer("candlestick_delta", [])]}]))
        self.assertErrorMentions(result, "derived at runtime")

    def test_py_maidr_roc(self):
        self.assertClean(run(os.path.join(FIXTURES, "py-maidr", "roc.html")))


if __name__ == "__main__":
    unittest.main()
