"""Real keyboard regression under the CSP observed in ChatGPT Work.

Optional: pip install playwright; playwright install chromium.
Synthetic public values only. No network access or CSP relaxation.
"""
import html
import json
import unittest

from test_to_artifact import to_artifact

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

CSP = ("default-src 'none'; script-src https://work.test/assets/ 'unsafe-inline' "
       "'unsafe-eval' 'wasm-unsafe-eval' blob:; connect-src 'none'; "
       "style-src https://work.test/assets/ 'unsafe-inline'; img-src data: blob:; "
       "font-src data:; media-src blob:")
BAR_GEOMETRIES = [dict(x=135, y=40 + 49 * i, width=600 - 80 * i, height=30) for i in range(6)]
SPEC = {"id": "public-bars", "title": "Public sample", "subplots": [[{"layers": [{
    "id": "bars", "type": "bar", "orientation": "horz",
    "axes": {"x": {"label": "Count"}, "y": {"label": "Category"}},
    "selectors": "#public-bars rect.bar",
    "data": [{"x": mark["width"], "y": f"Public row {i + 1}"} for i, mark in enumerate(BAR_GEOMETRIES)],
}]}]]}
# Fixed, fully materialized geometry in nested groups reproduces the source structure
# whose resize redraw selected MAIDR's hidden clones as though they were original bars.
CHART = ('<svg id="public-bars" width="760" height="390" viewBox="0 0 760 390" '
         'style="width:100%;height:auto" maidr=\'' + html.escape(json.dumps(SPEC), quote=True) + '\'>'
         '<g class="plot"><g class="rows">' + ''.join(
             f'<g data-row="{i}"><rect class="bar" ' +
             ' '.join(f'{key}="{value}"' for key, value in mark.items()) + '/></g>'
             for i, mark in enumerate(BAR_GEOMETRIES)) + '</g></g></svg>')
ORIGINAL_MARKS = '#public-bars rect.bar:not([data-maidr-owned])'
ACTIVE_HIGHLIGHT = '#public-bars [id^="maidr-highlight-"]'


@unittest.skipUnless(sync_playwright, "optional playwright package not installed")
class VisualizeBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as exc:
            cls.pw.stop()
            raise unittest.SkipTest(f"optional Chromium browser not installed: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def load(self, content, before=""):
        context = self.browser.new_context(locale="ko-KR")
        self.addCleanup(context.close)
        page = context.new_page()
        requests = []
        page.on("request", lambda req: requests.append(req.url) if not req.is_navigation_request() else None)
        context.route("**/*", lambda route: route.abort())
        document = ('<meta http-equiv="Content-Security-Policy" content="' +
                         html.escape(CSP, quote=True) + '">' + before +
                         '<button id="before">Before chart</button>' + content)
        context.route('https://work.test/', lambda route: route.fulfill(body=document, content_type='text/html'))
        page.goto('https://work.test/')
        return page, requests

    def assert_bar_geometry(self, page, index):
        expected = BAR_GEOMETRIES[index]
        page.wait_for_function('''({row, value}) => {
            const text = document.querySelector('[role="alert"]')?.textContent || '';
            return text.includes(row) && text.includes(String(value));
        }''', arg={"row": f"Public row {index + 1}", "value": expected["width"]})
        highlight = page.locator(ACTIVE_HIGHLIGHT)
        self.assertEqual(highlight.count(), 1)
        # A highlight merely existing is insufficient: compare every dimension to the
        # announced datum, then compare rendered bounds to its actual original mark.
        actual = highlight.evaluate("el => Object.fromEntries(['x','y','width','height'].map(k => [k, Number(el.getAttribute(k))]))")
        self.assertEqual(actual, expected)
        marks = page.locator(ORIGINAL_MARKS)
        originals = marks.evaluate_all("els => els.map(el => Object.fromEntries(['x','y','width','height'].map(k => [k, Number(el.getAttribute(k))])))")
        self.assertEqual(originals, BAR_GEOMETRIES, 'MAIDR or redraw code changed an original mark')
        # getBoundingClientRect compares SVG geometry without Playwright's extra
        # stroke-inclusive box, which can be 1px larger for MAIDR's highlight.
        bounds = "el => {const r = el.getBoundingClientRect(); return {x:r.x, y:r.y, width:r.width, height:r.height};}"
        active_bounds = highlight.evaluate(bounds)
        original_bounds = marks.nth(index).evaluate(bounds)
        self.assertIsNotNone(active_bounds)
        self.assertIsNotNone(original_bounds)
        for key in ('x', 'y', 'width', 'height'):
            self.assertAlmostEqual(active_bounds[key], original_bounds[key], delta=0.5)

    def test_external_cdn_fails_but_bundle_preserves_each_highlight_on_resize(self):
        original, _ = to_artifact.convert(CHART, "jsdelivr", None)
        blocked, _ = self.load(original)
        self.assertEqual(blocked.locator('article[id^="maidr-article-"]').count(), 0)
        self.assertEqual(blocked.locator('[tabindex="0"]').count(), 0)
        for source in (CHART, CHART.replace(' width="760" height="390"', '')):
            with self.subTest(intrinsic_dimensions=' width="760"' in source):
                original, _ = to_artifact.convert(source, "jsdelivr", None)
                output, problems = to_artifact.visualize(original, "maidr-public")
                self.assertEqual(problems, [])
                page, requests = self.load(output, '<script>localStorage.setItem("maidr-settings", \'{"general":{"language":"ko"}}\');window.previousStorage = localStorage;</script>')
                page.wait_for_selector('#maidr-public[data-maidr-state="ready"]')
                self.assertEqual(page.locator('article[id^="maidr-article-"]').count(), 1)
                svg = page.locator('#public-bars')
                self.assertEqual(svg.get_attribute('width'), '760')
                self.assertEqual(svg.get_attribute('height'), '390')
                page.set_viewport_size({"width": 1024, "height": 700})
                self.assertAlmostEqual(svg.bounding_box()['width'], 760, delta=0.5,
                                       msg='fit-content must not collapse the chart to the 300px default')
                page.locator('#before').focus()
                page.keyboard.press('Tab')
                page.wait_for_function('document.activeElement.getAttribute("role") === "application"')
                page.keyboard.press('ArrowRight')
                rendered_widths = []
                for width in (1024, 390, 778):
                    page.set_viewport_size({"width": width, "height": 700})
                    rendered_widths.append(svg.bounding_box()['width'])
                    for index in range(6):
                        if index:
                            page.keyboard.press('ArrowRight')
                        self.assert_bar_geometry(page, index)
                    # Return to datum one before the next actual viewport resize.
                    for _ in range(5):
                        page.keyboard.press('ArrowLeft')
                self.assertLess(rendered_widths[1], rendered_widths[0])
                self.assertGreater(rendered_widths[2], rendered_widths[1])
                self.assertEqual(requests, [], 'fragment attempted a browser network request')
                self.assertTrue(page.evaluate('window.localStorage === window.previousStorage'))
                self.assertIn('"ko"', page.evaluate('localStorage.getItem("maidr-settings")'))
                self.assertEqual(page.locator('script[src], link[href]').count(), 0)

    def test_missing_decompression_renders_accessible_error(self):
        original, _ = to_artifact.convert(CHART, "jsdelivr", None)
        output, problems = to_artifact.visualize(original, "maidr-public")
        self.assertEqual(problems, [])
        page, requests = self.load(output, '<script>window.DecompressionStream = undefined;</script>')
        page.wait_for_selector('#maidr-public[data-maidr-state="error"]')
        self.assertIn('Accessible chart could not start', page.locator('[role=alert]').inner_text())
        self.assertEqual(requests, [])


if __name__ == '__main__':
    unittest.main()

