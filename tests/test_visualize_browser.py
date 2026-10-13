"""Real keyboard regression under the CSP observed in ChatGPT Work.

Optional: pip install playwright; playwright install chromium.
Synthetic public values only. No network access or CSP relaxation.
"""
import html
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
CHART = '''<svg id="public-bars" width="300" height="200" maidr='{"id":"public-bars",
"title":"Public sample","subplots":[[{"layers":[{"id":"bars","type":"bar",
"axes":{"x":{"label":"Quarter"},"y":{"label":"Count"}},"selectors":"#public-bars rect",
"data":[{"x":"Q1","y":120},{"x":"Q2","y":200}]}]}]]}'>
<rect x="20" y="80" width="50" height="120"/><rect x="100" y="0" width="50" height="200"/></svg>'''


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

    def test_external_cdn_fails_but_bundle_binds_and_keyboard_announces(self):
        original, _ = to_artifact.convert(CHART, "jsdelivr", None)
        blocked, _ = self.load(original)
        self.assertEqual(blocked.locator('article[id^="maidr-article-"]').count(), 0)
        self.assertEqual(blocked.locator('[tabindex="0"]').count(), 0)
        output, problems = to_artifact.visualize(original, "maidr-public")
        self.assertEqual(problems, [])
        page, requests = self.load(output, '<script>localStorage.setItem("maidr-settings", \'{"general":{"language":"ko"}}\');window.previousStorage = localStorage;</script>')
        page.wait_for_selector('#maidr-public[data-maidr-state="ready"]')
        self.assertEqual(page.locator('article[id^="maidr-article-"]').count(), 1)
        page.locator('#before').focus()
        page.keyboard.press('Tab')
        page.wait_for_function('document.activeElement.getAttribute("role") === "application"')
        page.keyboard.press('ArrowRight')
        page.wait_for_function('document.querySelector("[role=alert]")?.textContent.includes("120")')
        page.keyboard.press('ArrowRight')
        page.wait_for_function('document.querySelector("[role=alert]")?.textContent.includes("200")')
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

