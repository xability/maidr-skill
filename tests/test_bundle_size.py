"""The skill gives the vendored maidr.js's size in words, not a number a new release falsifies.

references/javascript.md (Inline row) and references/python.md (the inline save_html recipe) say
the bundle is "well over 1 MB", which matters where a host caps a page at 1 MB (ChatGPT Work's
visualize, troubleshooting.md). They said "1.5 MB" until 4.15.0's 1,958,529 bytes made it wrong
with nothing failing. This fails if a release makes the words wrong, and checks that the size
maidr-bundle.json records, which the docs point to for the exact figure, is the file's.

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
        for name in ("javascript.md", "python.md"):
            with open(os.path.join(REFERENCES, name), encoding="utf-8") as fh:
                self.assertIn("well over 1 MB", fh.read(), name)
        self.assertGreater(size, 1_500_000, "maidr.js is no longer well over 1 MB: reword javascript.md and python.md")


if __name__ == "__main__":
    unittest.main()
