"""Regression tests for tools/pin_versions.py, the version rewrite tools/update-bundle.sh runs.

update-bundle.sh used to replace every exact match of the vendored version, so each refresh also
moved the statements about past releases that happened to name it: "hoverMode needs maidr.js after
4.14.0" read "after 4.15.0" once 4.15.0 was vendored, and the checker's "4.x releases before 4.10.0
highlight nothing" had read 4.12.0 to 4.15.0 in turn. These hold the rewrite to the pins, and fail
when the tree names the vendored version anywhere a refresh could not classify.

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
TOOL = os.path.join(ROOT, "tools", "pin_versions.py")


def read(path: str) -> str:
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


VERSION = json.loads(read(os.path.join(ROOT, "skills", "maidr", "assets", "maidr-bundle.json")))["version"]
NEXT = "99.98.97"   # a release that will never exist, so every match of it is the rewrite's

spec = importlib.util.spec_from_file_location("pin_versions", TOOL)
pins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pins)

# The pin check in .github/workflows/validate.yml, verbatim.
VALIDATE_PINS = re.compile(r"npm/maidr@(\d+\.\d+\.\d+)/|(?:unpkg\.com|esm\.sh)/maidr@(\d+\.\d+\.\d+)|/libs/maidr/(\d+\.\d+\.\d+)/|MAIDR_(?:JS_)?VERSION\s*=\s*\"(\d+\.\d+\.\d+)\"|maidr-js-version:\s*\"(\d+\.\d+\.\d+)\"")
ANY_VERSION = re.compile(r"(?<![0-9.])\d+\.\d+\.\d+(?![0-9])(?!\.[0-9])")


def copy_tree(dest: str) -> None:
    """The files update-bundle.sh reads and writes, laid out as in the repository."""
    shutil.copytree(os.path.join(ROOT, "skills"), os.path.join(dest, "skills"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(os.path.join(ROOT, "tools"), os.path.join(dest, "tools"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("README.md", "AGENTS.md"):
        shutil.copy(os.path.join(ROOT, name), os.path.join(dest, name))


class TreeTest(unittest.TestCase):
    def test_every_vendored_version_is_a_pin_or_declared_history(self):
        found = pins.problems(VERSION)
        self.assertEqual(found, [], "\n".join(found + ["", pins.HINT]))

    def test_no_version_newer_than_the_vendored_one_is_undeclared(self):
        found = [f"{rel}: {pins.ANY_VERSION.match(text, o).group()}"
                 for rel, path in pins.files() if (text := pins._read(path)) is not None
                 for o in pins.newer(text, VERSION, rel)]
        self.assertEqual(found, [], pins.HINT)

    def test_check_command_passes_on_the_tree(self):
        out = subprocess.run([sys.executable, TOOL, "check", VERSION], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_a_refresh_moves_every_pin_and_no_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy_tree(tmp)
            before = {rel: read(path)
                      for rel, path in pins.files(tmp) if pins._read(path) is not None}
            changed = pins.rewrite(VERSION, NEXT, root=tmp)
            self.assertTrue(changed)
            for rel, path in pins.files(tmp):
                after = pins._read(path)
                if after is None:
                    continue
                old = before[rel]
                # Every pin moved, as validate.yml reads them.
                stale = [m.group(0) for m in VALIDATE_PINS.finditer(after)
                         if next(g for g in m.groups() if g) != NEXT]
                self.assertEqual(stale, [], f"{rel}: pins left behind")
                # The vendored version is gone except where declared as history.
                self.assertEqual(pins.unclassified(after, VERSION, rel), [], rel)
                # Every other version, the history among them, is exactly where it was: only a
                # pin became NEXT, and a declared phrase naming VERSION still names it.
                self.assertNotIn(NEXT, old, rel)
                self.assertEqual(ANY_VERSION.findall(old),
                                 [VERSION if v == NEXT else v for v in ANY_VERSION.findall(after)], rel)
                # And the version is the only thing that changed.
                self.assertEqual(after.replace(NEXT, VERSION), old, rel)
            for rel, phrase in pins.HISTORY:
                self.assertIn(phrase, read(os.path.join(tmp, rel)), rel)
            # The constants the scripts and the skill's frontmatter read.
            for rel, pin in (("skills/maidr/scripts/check_maidr_html.py", f'MAIDR_VERSION = "{NEXT}"'),
                             ("skills/maidr/scripts/detect_env.sh", f'MAIDR_JS_VERSION="{NEXT}"'),
                             ("skills/maidr/scripts/detect_env.ps1", f'$MaidrJsVersion = "{NEXT}"'),
                             ("skills/maidr/scripts/to_artifact.py", f'DEFAULT_VERSION = "{NEXT}"'),
                             ("skills/maidr/SKILL.md", f'maidr-js-version: "{NEXT}"')):
                self.assertIn(pin, read(os.path.join(tmp, rel)), rel)

    def test_update_bundle_refuses_before_fetching_when_history_names_the_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy_tree(tmp)
            schema = os.path.join(tmp, "skills", "maidr", "references", "schema.md")
            with open(schema, "a", encoding="utf-8") as fh:
                # Worded so that no HISTORY entry can cover it: a declared "maidr.js X and later"
                # would, once X is vendored, and this test would then pass a tree it should not.
                fh.write(f"\nzz undeclared test sentence {VERSION} zz\n")
            before = read(schema)
            env = dict(os.environ, MAIDR_NPM_REGISTRY="http://127.0.0.1:9/maidr",
                       MAIDR_FETCH_MAX_ATTEMPTS="1", MAIDR_FETCH_RETRY_DELAY="0")
            out = subprocess.run(["bash", os.path.join(tmp, "tools", "update-bundle.sh"), NEXT],
                                 capture_output=True, text=True, env=env, timeout=60)
            self.assertNotEqual(out.returncode, 0)
            self.assertIn("neither a pin nor declared history", out.stdout + out.stderr)
            self.assertNotIn("registry", out.stderr)   # it stopped before the first check
            self.assertEqual(read(schema), before)


    def test_update_bundle_refuses_before_fetching_when_a_statement_names_the_next_release(self):
        # Written while VERSION is vendored, this names no pin, so it used to pass every check;
        # vendored, NEXT made it an undeclared mention of the pin, and main went red.
        with tempfile.TemporaryDirectory() as tmp:
            copy_tree(tmp)
            schema = os.path.join(tmp, "skills", "maidr", "references", "schema.md")
            with open(schema, "a", encoding="utf-8") as fh:
                fh.write(f"\n`newKey` (maidr.js {NEXT} and later) does a new thing.\n")
            before = read(schema)
            check = subprocess.run([sys.executable, os.path.join(tmp, "tools", "pin_versions.py"), "check", VERSION],
                                   capture_output=True, text=True)
            self.assertNotEqual(check.returncode, 0)
            self.assertIn(f"{NEXT} is newer than the vendored {VERSION}", check.stdout)
            env = dict(os.environ, MAIDR_NPM_REGISTRY="http://127.0.0.1:9/maidr",
                       MAIDR_FETCH_MAX_ATTEMPTS="1", MAIDR_FETCH_RETRY_DELAY="0")
            out = subprocess.run(["bash", os.path.join(tmp, "tools", "update-bundle.sh"), NEXT],
                                 capture_output=True, text=True, env=env, timeout=60)
            self.assertNotEqual(out.returncode, 0)
            self.assertIn(f"{NEXT} is newer than the vendored {VERSION}", out.stdout + out.stderr)
            self.assertNotIn("registry", out.stderr)   # it stopped before the first check
            self.assertEqual(read(schema), before)

    def test_update_bundle_refuses_before_fetching_when_an_older_target_is_named(self):
        # Moving the pin back to a release the prose names would leave that prose naming the pin.
        with tempfile.TemporaryDirectory() as tmp:
            copy_tree(tmp)
            schema = os.path.join(tmp, "skills", "maidr", "references", "schema.md")
            with open(schema, "a", encoding="utf-8") as fh:
                fh.write("\n`oldKey` was dropped after 1.2.3.\n")
            env = dict(os.environ, MAIDR_NPM_REGISTRY="http://127.0.0.1:9/maidr",
                       MAIDR_FETCH_MAX_ATTEMPTS="1", MAIDR_FETCH_RETRY_DELAY="0")
            out = subprocess.run(["bash", os.path.join(tmp, "tools", "update-bundle.sh"), "1.2.3"],
                                 capture_output=True, text=True, env=env, timeout=60)
            self.assertNotEqual(out.returncode, 0)
            self.assertIn("1.2.3 is the release being vendored", out.stdout + out.stderr)
            self.assertNotIn("registry", out.stderr)

    def test_a_declared_statement_about_the_next_release_survives_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy_tree(tmp)
            rel = "skills/maidr/references/schema.md"
            phrase = f"maidr.js {NEXT} and later"
            with open(os.path.join(tmp, rel), "a", encoding="utf-8") as fh:
                fh.write(f"\n`newKey` ({phrase}) does a new thing.\n")
            history = pins.HISTORY + ((rel, phrase),)
            self.assertEqual(pins.problems(VERSION, root=tmp, history=history, target=NEXT), [])
            pins.rewrite(VERSION, NEXT, root=tmp)
            self.assertIn(f"`newKey` ({phrase})", read(os.path.join(tmp, rel)))
            self.assertEqual(pins.problems(NEXT, root=tmp, history=history), [])

    def test_update_bundle_refuses_a_bare_package_spec_naming_the_pin(self):
        # "maidr@VERSION" outside a jsDelivr URL is a statement about a release, not a pin.
        with tempfile.TemporaryDirectory() as tmp:
            copy_tree(tmp)
            schema = os.path.join(tmp, "skills", "maidr", "references", "schema.md")
            with open(schema, "a", encoding="utf-8") as fh:
                fh.write(f"\nzz undeclared test sentence maidr@{VERSION} zz\n")
            before = read(schema)
            env = dict(os.environ, MAIDR_NPM_REGISTRY="http://127.0.0.1:9/maidr",
                       MAIDR_FETCH_MAX_ATTEMPTS="1", MAIDR_FETCH_RETRY_DELAY="0")
            out = subprocess.run(["bash", os.path.join(tmp, "tools", "update-bundle.sh"), NEXT],
                                 capture_output=True, text=True, env=env, timeout=60)
            self.assertNotEqual(out.returncode, 0)
            self.assertIn("neither a pin nor declared history", out.stdout + out.stderr)
            self.assertNotIn("registry", out.stderr)
            self.assertEqual(read(schema), before)


class UnitTest(unittest.TestCase):
    def test_a_newer_version_is_reported_unless_declared(self):
        text = "`newKey` (maidr.js 4.16.0 and later); 4.14.0 and 4.15.0 and 3.99.0 and 14.0.1.\n"
        self.assertEqual([text[o:o + 6] for o in pins.newer(text, "4.15.0", "x.md", history=())],
                         ["4.16.0", "14.0.1"])
        history = (("x.md", "maidr.js 4.16.0 and later"), ("x.md", "and 14.0.1"))
        self.assertEqual(pins.newer(text, "4.15.0", "x.md", history=history), [])
        # A pin form does not excuse a newer version: pins name the vendored release.
        self.assertEqual(len(pins.newer("npm/maidr@4.16.0/dist", "4.15.0", "x.md", history=())), 1)

    TEXT = ('<script src="https://cdn.jsdelivr.net/npm/maidr@4.15.0/dist/maidr.js"></script>\n'
            "`hoverMode` needs maidr.js 4.15.0 or later; 4.14.0 ignores it. Not 4.15.01 or 14.15.0.\n")

    def test_only_the_pin_is_rewritten(self):
        out = pins.rewrite_text(self.TEXT, "4.15.0", "4.16.0")
        self.assertIn("maidr@4.16.0/dist", out)
        self.assertIn("needs maidr.js 4.15.0 or later", out)
        self.assertIn("Not 4.15.01 or 14.15.0", out)

    def test_an_undeclared_mention_of_the_pin_is_reported(self):
        offsets = pins.unclassified(self.TEXT, "4.15.0", "x.md", history=())
        self.assertEqual([self.TEXT[o:o + 20] for o in offsets], ["4.15.0 or later; 4.1"])

    def test_declared_history_is_accepted_and_kept(self):
        history = (("x.md", "needs maidr.js 4.15.0 or later"),)
        self.assertEqual(pins.unclassified(self.TEXT, "4.15.0", "x.md", history=history), [])
        self.assertEqual(pins.unclassified(self.TEXT, "4.15.0", "y.md", history=history),
                         [self.TEXT.index("4.15.0 or later")])

    def test_a_bare_package_spec_is_history_not_a_pin(self):
        # Only a jsDelivr URL pins with "maidr@": "maidr@4.15.0 or later" in a sentence is about a
        # release, so it must be reported rather than moved to the next one by a refresh.
        text = ("`hoverMode` needs `maidr@4.15.0` or later.\n"
                "<script src=\"https://cdn.jsdelivr.net/npm/maidr@4.15.0/dist/maidr.js\"></script>\n")
        self.assertEqual(pins.unclassified(text, "4.15.0", "x.md", history=()),
                         [text.index("4.15.0` or later")])
        out = pins.rewrite_text(text, "4.15.0", "4.16.0")
        self.assertIn("needs `maidr@4.15.0` or later", out)
        self.assertIn("npm/maidr@4.16.0/dist", out)
        self.assertEqual([m.group(1) for m in VALIDATE_PINS.finditer(out)], ["4.16.0"])

    def test_unpkg_and_esm_sh_urls_are_pins(self):
        # A page may load maidr.js from unpkg or esm.sh (ChatGPT Work's CSP admits both), so such a
        # URL is moved by a refresh, and an older version left in one is a stale pin to validate.yml,
        # as it was before the jsDelivr form became "npm/maidr@{v}/".
        text = ('<script src="https://unpkg.com/maidr@4.15.0/dist/maidr.js"></script>\n'
                'import "https://esm.sh/maidr@4.15.0";\n')
        self.assertEqual(pins.unclassified(text, "4.15.0", "x.md", history=()), [])

        def found(t):
            return [next(g for g in m.groups() if g) for m in VALIDATE_PINS.finditer(t)]

        self.assertEqual(found(pins.rewrite_text(text, "4.15.0", "4.16.0")), ["4.16.0", "4.16.0"])
        self.assertEqual(found(text.replace("4.15.0", "4.14.0")), ["4.14.0", "4.14.0"])

    def test_the_validate_pins_copy_is_the_workflows(self):
        workflow = read(os.path.join(ROOT, ".github", "workflows", "validate.yml"))
        self.assertIn(f're.finditer(r"{VALIDATE_PINS.pattern}", text)', workflow)

    def test_a_declared_phrase_that_is_gone_or_holds_a_pin_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "skills", "maidr"))
            with open(os.path.join(tmp, "README.md"), "w", encoding="utf-8") as fh:
                fh.write("Load https://cdn.jsdelivr.net/npm/maidr@4.15.0/dist/maidr.js here.\n")
            found = pins.problems("4.15.0", root=tmp, history=(("README.md", "gone"),
                                                                 ("README.md", "Load https://cdn.jsdelivr.net/npm/maidr@4.15.0/")))
            self.assertEqual(len(found), 2, found)
            self.assertIn("not found", found[0])
            self.assertIn("contains a pin form", found[1])


if __name__ == "__main__":
    unittest.main()
