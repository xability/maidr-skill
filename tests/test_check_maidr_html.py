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
import json
import os
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


if __name__ == "__main__":
    unittest.main()
