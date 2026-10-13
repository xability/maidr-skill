"""The skill gives the vendored maidr.js's size in words, not a number a new release falsifies.

references/javascript.md (Inline row) says the skill's assets/maidr.js is "well over 1 MB", which
matters where a host caps a page at 1 MB (ChatGPT Work's visualize, troubleshooting.md).
references/python.md (the inline save_html recipe) says the same of py-maidr's bundled copy, which
this test cannot read. That copy is a maidr.js release too, and can trail the vendored one: the
PyPI wheels of py-maidr 1.25.0 and 1.26.0 carry 4.10.0 (1,776,095 bytes) and 4.11.0 (1,850,102
bytes), by their maidr/static/VERSION, each byte-for-byte that release on npm. Every release from
4.8.0 to 4.15.0 is larger than the one before it (1,745,805 to 1,958,529 bytes), so the words hold
for whichever of them py-maidr bundles, and this measures them against assets/maidr.js, the one
release it can read. Both files said "1.5 MB" until 4.15.0 made that wrong with nothing failing.
This fails if a release makes the words wrong, and checks that the size maidr-bundle.json records,
which javascript.md points to for the exact figure, is the file's.

Run from the repository root:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "skills", "maidr", "assets")
REFERENCES = os.path.join(ROOT, "skills", "maidr", "references")


class BundleSizeTest(unittest.TestCase):
    def test_recorded_size_is_the_file_size(self):
        with open(os.path.join(ASSETS, "maidr-bundle.json"), encoding="utf-8") as fh:
            meta = json.load(fh)
        self.assertEqual(meta["files"]["maidr.js"]["bytes"], os.path.getsize(os.path.join(ASSETS, "maidr.js")))

    def test_well_over_1_mb_is_still_true(self):
        size = os.path.getsize(os.path.join(ASSETS, "maidr.js"))
        for name, claim in (("javascript.md", "`assets/maidr.js` into a `<script>` block (well over 1 MB;"),
                            ("python.md", "py-maidr's bundled maidr.js inline (well over 1 MB)")):
            with open(os.path.join(REFERENCES, name), encoding="utf-8") as fh:
                self.assertIn(claim, fh.read(), name)
        self.assertGreater(size, 1_500_000, "maidr.js is no longer well over 1 MB: reword javascript.md and python.md")


if __name__ == "__main__":
    unittest.main()
