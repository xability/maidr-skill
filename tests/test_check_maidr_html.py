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


SERIES = [{"x": 1, "y": 2, "z": "a"}, {"x": 2, "y": 3, "z": "a"}]


class DataShapeTest(CheckerCase):
    """Each maidr.js trace class casts `layer.data` to one shape (maidr src/model/<type>.ts)."""

    def assertAccepted(self, type_: str, data) -> None:
        with self.subTest(type=type_):
            self.assertClean(self.check_doc(figure([{"layers": [layer(type_, data)]}])))

    def test_nested_types(self):
        # LineTrace / StepTrace / SegmentedTrace subclasses, and the violin, ridgeline and hexbin rows
        for type_ in ("bump", "radar", "polar_area", "parallel_coordinates", "roc", "survival"):
            self.assertAccepted(type_, [SERIES, SERIES])
        self.assertAccepted("contour", [[{"x": 1, "y": 1, "level": 1}, {"x": 2, "y": 1, "level": 1}]])
        self.assertAccepted("ridgeline", [[{"x": 1, "y": 0.2}], [{"x": 1, "y": 0.3}]])
        self.assertAccepted("hexbin", [[{"x": 1, "y": 1, "count": 3}, {"x": 2, "y": 1, "count": 1}]])
        self.assertAccepted("mosaic", [[{"x": "A", "y": 0.4, "z": "u", "width": 0.5}]])
        self.assertAccepted("diverging_bar", [[{"x": "A", "y": -2, "z": "neg"}], [{"x": "A", "y": 3, "z": "pos"}]])

    def test_nested_types_reject_flat_data(self):
        result = self.check_doc(figure([{"layers": [layer("radar", SERIES)]}]))
        self.assertErrorMentions(result, "expects nested data")

    def test_hexbin_needs_count(self):
        result = self.check_doc(figure([{"layers": [layer("hexbin", [[{"x": 1, "y": 1}]])]}]))
        self.assertErrorMentions(result, "count")

    def test_error_bar_is_flat_or_grouped(self):
        # errorBar.ts toGroups: a flat array is one group; y is optional (a band draws only bounds)
        flat = [{"x": 1, "y": 2, "yMin": 1, "yMax": 3}, {"x": 2, "yMin": 1, "yMax": 3}]
        self.assertAccepted("error_bar", flat)
        self.assertAccepted("error_bar", [flat, flat])
        self.assertAccepted("forest", [{"x": "study", "y": 1.2, "yMin": 0.9, "yMax": 1.5}])
        result = self.check_doc(figure([{"layers": [layer("forest", [{"x": "study", "yMin": 1}])]}]))
        self.assertErrorMentions(result, "missing ['y']")

    def test_object_types(self):
        self.assertAccepted("gauge", {"value": 3, "min": 0, "max": 10})
        self.assertAccepted("dumbbell", {"points": [{"x": "A", "start": 1, "end": 2}]})
        self.assertAccepted("gantt", {"points": [[{"x": "t", "start": 0, "end": 1}], [{"x": "u", "start": 1, "end": 3}]]})

    def test_object_types_reject_arrays_and_missing_keys(self):
        cases = [("gauge", [{"value": 3}], "one object"),
                 ("gauge", {"value": 3, "max": 10}, "missing ['min']"),
                 ("dumbbell", {"points": [[{"x": "A", "start": 1, "end": 2}]]}, "flat array"),
                 ("gantt", {"points": [{"x": "t", "start": 0, "end": 1}]}, "one inner array"),
                 ("gantt", {"points": [[{"x": "t", "start": 0}]]}, "missing ['end']")]
        for type_, data, needle in cases:
            with self.subTest(type=type_, data=data):
                self.assertErrorMentions(self.check_doc(figure([{"layers": [layer(type_, data)]}])), needle)

    def test_flat_types_still_reject_nested_data(self):
        result = self.check_doc(figure([{"layers": [layer("bar", [[{"x": "A", "y": 1}]])]}]))
        self.assertErrorMentions(result, "expects a flat array")

    def test_py_maidr_output(self):
        for name in ("hexbin", "contour", "errorbar", "gantt"):
            with self.subTest(fixture=name):
                self.assertClean(run(os.path.join(FIXTURES, "py-maidr", f"{name}.html")))


def rects(cls: str, n: int) -> str:
    return "".join(f'<rect class="{cls}" x="{i}" y="0" width="1" height="1"/>' for i in range(n))


@unittest.skipUnless(HAVE_BS4, "selector checks need beautifulsoup4")
class SelectorFamilyTest(CheckerCase):
    """The "By layer type" table under Selectors in maidr's docs/SCHEMA.md, type by type."""

    def warnings_about_selectors(self, result: dict) -> list[str]:
        return [m for m in messages(result, "WARN") if "select" in m or "series" in m]

    def test_diverging_bar_is_segmented(self):
        # diverging.ts: DivergingTrace extends SegmentedTrace, so a flat array is declined
        data = [[{"x": "A", "y": -2, "z": "n"}, {"x": "B", "y": -1, "z": "n"}], [{"x": "A", "y": 3, "z": "p"}, {"x": "B", "y": 1, "z": "p"}]]
        bad = layer("diverging_bar", data, selectors=["rect.s", None, "rect.s", None])
        self.assertErrorMentions(self.check_doc(figure([{"layers": [bad]}]), rects("s", 4)), "flat array is declined")
        good = layer("diverging_bar", data, selectors="rect.s", domMapping={"order": "column"})
        self.assertClean(self.check_doc(figure([{"layers": [good]}]), rects("s", 4)))

    def test_funnel_is_bar_family(self):
        # funnel.ts: FunnelTrace extends BarTrace; a list means one selector per stage
        data = [{"x": "a", "y": 3}, {"x": "b", "y": 2}, {"x": "c", "y": 1}]
        good = layer("funnel", data, selectors=["rect.s:nth-of-type(1)", "rect.s:nth-of-type(2)", "rect.s:nth-of-type(3)"])
        self.assertClean(self.check_doc(figure([{"layers": [good]}]), rects("s", 3)))
        bad = layer("funnel", data, selectors="rect.s")
        self.assertErrorMentions(self.check_doc(figure([{"layers": [bad]}]), rects("s", 2)), "matches 2 elements")

    def test_line_family_needs_one_selector_per_series(self):
        for type_ in ("bump", "radar", "polar_area", "parallel_coordinates", "contour", "survival"):
            with self.subTest(type=type_):
                result = self.check_doc(figure([{"layers": [layer(type_, [SERIES, SERIES], selectors="path.l")]}]),
                                        '<path class="l" d="M0 0 L1 1"/><path class="l" d="M0 0 L1 1"/>')
                self.assertErrorMentions(result, "one string for 2 series")

    def test_line_family_accepts_one_marker_per_point(self):
        # line.ts mapViaDomElements: a selector matching one element per point pairs them in order
        dots = "".join(f'<circle class="s{r}" cx="{i}" cy="{r}" r="1"/>' for r in range(2) for i in range(2))
        result = self.check_doc(figure([{"layers": [layer("radar", [SERIES, SERIES], selectors=["circle.s0", "circle.s1"])]}]), dots)
        self.assertClean(result)
        self.assertEqual(self.warnings_about_selectors(result), [])

    def test_contour_level_may_name_several_paths(self):
        # contour.ts: a selector resolving to several elements is read as one level
        level = [{"x": 0, "y": 0, "level": 1}, {"x": 1, "y": 1, "level": 1}]
        result = self.check_doc(figure([{"layers": [layer("contour", [level], selectors=["path.lv"])]}]),
                                '<path class="lv" d="M0 0 L1 1 L2 2"/><path class="lv" d="M5 5 L6 6 L7 7"/>')
        self.assertClean(result)
        self.assertEqual(self.warnings_about_selectors(result), [])

    def test_concatenated_types_count_every_match(self):
        # gantt.ts and its peers: each list entry is resolved and the matches concatenated
        data = {"points": [[{"x": "a", "start": 0, "end": 1}, {"x": "a", "start": 2, "end": 3}], [{"x": "b", "start": 1, "end": 2}]]}
        svg = rects("l0", 2) + rects("l1", 1)
        result = self.check_doc(figure([{"layers": [layer("gantt", data, selectors=["rect.l0", "rect.l1"])]}]), svg)
        self.assertClean(result)
        self.assertEqual(self.warnings_about_selectors(result), [])
        short = self.check_doc(figure([{"layers": [layer("gantt", data, selectors=["rect.l0"])]}]), svg)
        self.assertErrorMentions(short, "declares 3")

    def test_ridgeline_pairs_one_element_per_ridge(self):
        data = [[{"x": 1, "y": 0.2}, {"x": 2, "y": 0.4}], [{"x": 1, "y": 0.3}, {"x": 2, "y": 0.1}]]
        svg = '<path class="r" d="M0 0 L1 1"/><path class="r" d="M0 2 L1 3"/>'
        self.assertClean(self.check_doc(figure([{"layers": [layer("ridgeline", data, selectors="path.r")]}]), svg))

    def test_gauge_uses_its_first_match(self):
        gauge = layer("gauge", {"value": 3, "min": 0, "max": 10}, selectors="rect.g")
        self.assertClean(self.check_doc(figure([{"layers": [gauge]}]), rects("g", 2)))

    def test_py_maidr_gantt_selectors(self):
        result = run(os.path.join(FIXTURES, "py-maidr", "gantt.html"))
        self.assertClean(result)
        self.assertEqual(self.warnings_about_selectors(result), [])


@unittest.skipUnless(HAVE_BS4, "selector checks need beautifulsoup4")
class LegacySelectorListTest(CheckerCase):
    """maidr 4.10.0 joins a pre-4.0 flat list of strings into one selector (src/util/selectors.ts, #1275)."""

    BARS = [{"x": "a", "y": 1}, {"x": "b", "y": 2}, {"x": "c", "y": 3}]

    def legacy_warnings(self, result: dict) -> list[str]:
        return [m for m in messages(result, "WARN") if "joins the list" in m]

    def test_point_list_is_joined_with_a_warning(self):
        pts = [{"x": 1, "y": 1}, {"x": 2, "y": 2}]
        svg = '<circle class="a" cx="1" cy="1" r="1"/><circle class="b" cx="2" cy="2" r="1"/>'
        result = self.check_doc(figure([{"layers": [layer("point", pts, selectors=["circle.a", "circle.b"])]}]), svg)
        self.assertClean(result)
        self.assertEqual(len(self.legacy_warnings(result)), 1)

    def test_one_element_bar_list_is_checked_as_its_string(self):
        good = layer("bar", self.BARS, selectors=["rect.s"])
        result = self.check_doc(figure([{"layers": [good]}]), rects("s", 3))
        self.assertClean(result)
        self.assertEqual(len(self.legacy_warnings(result)), 1)
        # the joined selector still has to match one element per bar
        short = self.check_doc(figure([{"layers": [good]}]), rects("s", 2))
        self.assertErrorMentions(short, "matches 2 elements")

    def test_one_selector_per_bar_is_not_legacy(self):
        per_bar = ["rect.s:nth-of-type(1)", "rect.s:nth-of-type(2)", "rect.s:nth-of-type(3)"]
        result = self.check_doc(figure([{"layers": [layer("bar", self.BARS, selectors=per_bar)]}]), rects("s", 3))
        self.assertClean(result)
        self.assertEqual(self.legacy_warnings(result), [])

    def test_segmented_list_over_rects_is_read_by_column(self):
        data = [[{"x": "A", "y": 1, "z": "u"}, {"x": "B", "y": 2, "z": "u"}], [{"x": "A", "y": 3, "z": "v"}, {"x": "B", "y": 4, "z": "v"}]]
        result = self.check_doc(figure([{"layers": [layer("stacked_bar", data, selectors=["rect.s"])]}]), rects("s", 4))
        self.assertClean(result)
        self.assertEqual(len(self.legacy_warnings(result)), 1)
        self.assertFalse(any("domMapping" in m for m in messages(result, "WARN")))

    def test_point_list_with_a_blank_entry_is_declined(self):
        pts = [{"x": 1, "y": 1}]
        result = self.check_doc(figure([{"layers": [layer("point", pts, selectors=["circle", ""])]}]), '<circle cx="1" cy="1" r="1"/>')
        self.assertErrorMentions(result, "string only")


if __name__ == "__main__":
    unittest.main()
