"""Regression tests for reaching maidr.js's locale packs (xability/maidr-skill#9).

Since maidr.js 4.8.0 every language but English is a locale pack, dist/locale-<code>.js, that
maidr.js fetches from beside its own URL or from window.maidrLocaleBaseUrl. A bundle pasted inline
has no URL and a vendored ./maidr.js has no packs beside it, so both leave a non-English reader in
English with only a console warning. These cover the checker's warning for that, the declaration
and packs that silence it, scripts/fetch_locale_packs.py, and scripts/to_artifact.py leaving the
declaration alone.

Run from the repository root:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "maidr", "scripts")
ASSETS = os.path.join(ROOT, "skills", "maidr", "assets")
CHECKER = os.path.join(SCRIPTS, "check_maidr_html.py")
FETCH = os.path.join(SCRIPTS, "fetch_locale_packs.py")
VERSION = json.load(open(os.path.join(ASSETS, "maidr-bundle.json")))["version"]
DECLARATION = ('<script>window.maidrLocaleBaseUrl = window.maidrLocaleBaseUrl || '
               f'"https://cdn.jsdelivr.net/npm/maidr@{VERSION}/dist/";</script>')
SVG = ('<svg id="c" maidr=\'{"id":"c","subplots":[[{"layers":[{"id":"l","type":"bar",'
       '"axes":{"x":{"label":"x"},"y":{"label":"y"}},"data":[{"x":"A","y":1}]}]}]]}\'>'
       '<rect class="bar"/></svg>')


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bundle() -> str:
    with open(os.path.join(ASSETS, "maidr.js"), encoding="utf-8") as fh:
        return fh.read()


def fake_pack(code: str) -> str:
    # the tail of a real pack: it queues [code, dictionary] on globalThis.maidrLocales
    return ('(function(){var d={},f=`maidrLocales`;function p(){return globalThis}'
            f'function m(e,t){{let n=p();n[f]??=[],n[f].push([e,t])}}m(`{code}`,d)}})();')


class LocaleWarningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def check(self, head: str, files: dict[str, str] | None = None) -> dict:
        for name, text in (files or {}).items():
            with open(os.path.join(self.tmp, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        path = os.path.join(self.tmp, "page.html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"<!doctype html><html><head>{head}</head><body>{SVG}</body></html>")
        out = subprocess.run([sys.executable, CHECKER, path, "--json"], capture_output=True, text=True)
        result = json.loads(out.stdout)
        result["exit"] = out.returncode
        return result

    def locale_warnings(self, result: dict) -> list[str]:
        return [i["message"] for i in result["items"]
                if i["level"] == "WARN" and "locale packs" in i["message"]]

    def inline(self) -> str:
        return "<script>" + bundle().replace("</script>", "<\\/script>") + "</script>"

    def test_inline_bundle_without_a_locale_source_warns(self):
        result = self.check(self.inline())
        self.assertEqual(result["exit"], 0)
        warnings = self.locale_warnings(result)
        self.assertEqual(len(warnings), 1, result["items"])
        self.assertIn("inline bundle", warnings[0])
        self.assertIn(f"maidr@{VERSION}/dist/", warnings[0])

    def test_inline_bundle_with_the_declaration_passes(self):
        result = self.check(DECLARATION + self.inline())
        self.assertEqual(self.locale_warnings(result), [])
        # the declaration names the CDN directory but is not a loader: the inlined bundle is the source
        self.assertIn("maidr.js source: inlined bundle", [i["message"] for i in result["items"]])

    def test_inline_bundle_with_a_pack_script_passes(self):
        pack = f'<script src="https://cdn.jsdelivr.net/npm/maidr@{VERSION}/dist/locale-ko.js"></script>'
        self.assertEqual(self.locale_warnings(self.check(pack + self.inline())), [])

    def test_inline_bundle_with_a_pasted_pack_passes(self):
        # the offline one-file recipe: the reader's pack pasted inline, before or after the bundle
        pack = f"<script>{fake_pack('ko')}</script>"
        self.assertEqual(self.locale_warnings(self.check(self.inline() + pack)), [])
        self.assertEqual(self.locale_warnings(self.check(pack + self.inline())), [])

    def test_relative_maidr_js_without_packs_warns(self):
        result = self.check('<script src="./maidr.js"></script>', {"maidr.js": "/* bundle */"})
        warnings = self.locale_warnings(result)
        self.assertEqual(len(warnings), 1, result["items"])
        self.assertIn("relative path (./maidr.js)", warnings[0])
        self.assertIn("fetch_locale_packs.py", warnings[0])

    def test_relative_maidr_js_with_packs_beside_it_passes(self):
        files = {"maidr.js": "/* bundle */", "locale-ko.js": fake_pack("ko")}
        self.assertEqual(self.locale_warnings(self.check('<script src="./maidr.js"></script>', files)), [])

    def test_cdn_pages_are_not_flagged(self):
        tag = f'<script src="https://cdn.jsdelivr.net/npm/maidr@{VERSION}/dist/maidr.js"></script>'
        self.assertEqual(self.locale_warnings(self.check(tag)), [])

    def test_a_declaration_alone_does_not_count_as_loading_maidr(self):
        result = self.check(DECLARATION)
        self.assertEqual(result["exit"], 1)
        self.assertTrue(any("maidr.js is not loaded" in i["message"] for i in result["items"]))

    def test_template_is_not_flagged(self):
        out = subprocess.run([sys.executable, CHECKER, os.path.join(ASSETS, "template.html"), "--json"],
                             capture_output=True, text=True)
        self.assertEqual(self.locale_warnings(json.loads(out.stdout)), [])


class FetchLocalePacksTest(unittest.TestCase):
    def test_locales_match_the_vendored_bundle(self):
        # maidr.js's SUPPORTED_LOCALES compiles to [`en`,`ko`,...]; English is built in
        m = re.search(r"=\[`en`((?:,`[a-z]{2}`)+)\]", bundle())
        self.assertIsNotNone(m, "SUPPORTED_LOCALES not found in the vendored maidr.js")
        self.assertEqual(tuple(re.findall(r"`([a-z]{2})`", m.group(1))), load("fetch_locale_packs").LOCALES)

    def run_fetch(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, FETCH, *args, "--json"], capture_output=True, text=True)

    def test_copies_packs_from_a_local_dist(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dest:
            for code in ("ko", "ja"):
                with open(os.path.join(src, f"locale-{code}.js"), "w", encoding="utf-8") as fh:
                    fh.write(fake_pack(code))
            shutil.copy(os.path.join(ASSETS, "maidr.js"), dest)
            out = self.run_fetch(dest, "--lang", "ko,ja", "--from", src)
            self.assertEqual(out.returncode, 0, out.stderr)
            report = json.loads(out.stdout)
            self.assertEqual(report["fetched"], ["locale-ko.js", "locale-ja.js"])
            self.assertIsNone(report["note"])
            again = json.loads(self.run_fetch(dest, "--lang", "ko", "--from", src).stdout)
            self.assertEqual(again["kept"], ["locale-ko.js"])

    def test_rejects_a_file_that_is_not_the_pack(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dest:
            with open(os.path.join(src, "locale-ko.js"), "w", encoding="utf-8") as fh:
                fh.write(fake_pack("ja"))  # a Japanese pack saved under the Korean name
            out = self.run_fetch(dest, "--lang", "ko", "--from", src)
            self.assertEqual(out.returncode, 1)
            self.assertFalse(os.path.exists(os.path.join(dest, "locale-ko.js")))

    def test_rejects_unknown_languages(self):
        self.assertEqual(self.run_fetch(".", "--lang", "en").returncode, 2)
        self.assertEqual(self.run_fetch(".", "--lang", "pt").returncode, 2)


class ToArtifactTest(unittest.TestCase):
    def test_declaration_is_not_mistaken_for_the_loader(self):
        page = (f"<html><head>{DECLARATION}<script>var s=document.createElement('script');"
                f"s.src='https://cdn.jsdelivr.net/npm/maidr@{VERSION}/dist/maidr.js';"
                f"document.head.appendChild(s);</script></head><body>{SVG}</body></html>")
        out, _ = load("to_artifact").convert(page, "jsdelivr", None)
        self.assertIn(DECLARATION, out)
        self.assertEqual(out.count(f"maidr@{VERSION}/dist/maidr.js"), 1)
        self.assertNotIn("createElement", out)


if __name__ == "__main__":
    unittest.main()
