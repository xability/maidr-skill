"""Standard-library packaging tests; run python -m unittest discover -s tests -p 'test_package_skill.py' -v."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("package_skill", ROOT / "tools/package-skill.py")
packager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packager)
COMMIT = "a" * 40


class PackageSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / "skills/maidr"
        for directory in ("assets", "references", "scripts", "agents"):
            (self.skill / directory).mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: maidr\ndescription: Accessible charts\n---\nSkill\n", encoding="utf-8")
        for name, data in {"references/python.md": b"reference", "scripts/detect_env.sh": b"#!/bin/sh\n", "agents/openai.yaml": b"agent", "assets/template.html": b"template", "assets/maidr.js": b"vendored js", "assets/maidr-math.css": b"vendored css"}.items():
            (self.skill / name).write_bytes(data)
        self.manifest = {"files": {name: {"sha256": hashlib.sha256((self.skill / "assets" / name).read_bytes()).hexdigest(), "bytes": (self.skill / "assets" / name).stat().st_size} for name in ("maidr.js", "maidr-math.css")}}
        self.write_manifest()
        self.output = self.root / "dist/maidr-skill.zip"

    def write_manifest(self):
        (self.skill / "assets/maidr-bundle.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def build(self):
        return packager.package(self.root, self.output, COMMIT)

    def test_layout_and_exact_skill_bytes_without_repository_files(self):
        for name in ("README.md", "plugin.json", "LICENSE"):
            (self.root / name).write_text("outside", encoding="utf-8")
        provenance = self.build()
        with zipfile.ZipFile(self.output) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn("maidr/SKILL.md", archive.namelist())
            self.assertIn("maidr/agents/openai.yaml", archive.namelist())
            self.assertEqual(set(archive.namelist()), set(provenance["files"]))
            for name in archive.namelist():
                self.assertTrue(name.startswith("maidr/"))
                self.assertEqual(archive.read(name), (self.skill / name.removeprefix("maidr/")).read_bytes())
            self.assertEqual((archive.getinfo("maidr/scripts/detect_env.sh").external_attr >> 16) & 0o777, 0o755)

    def test_caches_and_bytecode_are_excluded(self):
        for name in ("scripts/__pycache__/cached.pyc", "assets/.cache/download", "scripts/.pytest_cache/state", "scripts/node_modules/package/index.js", "scripts/foo.pyc", "scripts/foo.pyo", "assets/.DS_Store", "assets/Thumbs.db"):
            item = self.skill / name
            item.parent.mkdir(parents=True, exist_ok=True)
            item.write_bytes(b"excluded")
        result = self.build()
        self.assertEqual(len(result["files"]), 8)

    def test_deterministic_zip_and_provenance(self):
        first = self.build()
        data = self.output.read_bytes()
        second = self.build()
        self.assertEqual(self.output.read_bytes(), data)
        self.assertEqual(first, second)
        self.assertFalse(self.output.with_suffix(".zip.tmp").exists())

    def test_sidecar_checksums_and_commit(self):
        result = self.build()
        digest = hashlib.sha256(self.output.read_bytes()).hexdigest()
        self.assertEqual(result["archive"]["sha256"], digest)
        self.assertEqual(result["source"], {"commit": COMMIT, "path": "skills/maidr"})
        self.assertEqual(json.loads(self.output.with_suffix(".provenance.json").read_text(encoding="utf-8")), result)
        self.assertEqual(self.output.with_suffix(".zip.sha256").read_text(encoding="utf-8"), f"{digest}  maidr-skill.zip\n")
        for name, info in result["files"].items():
            data = (self.skill / name.removeprefix("maidr/")).read_bytes()
            self.assertEqual(info, {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})

    def test_missing_or_empty_skill_is_rejected(self):
        (self.skill / "SKILL.md").write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "SKILL.md"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_missing_reference_directory_is_rejected(self):
        (self.skill / "references/python.md").unlink()
        with self.assertRaisesRegex(ValueError, "references"):
            self.build()

    def test_bundle_corruption_is_rejected_before_writing(self):
        (self.skill / "assets/maidr.js").write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "checksum/size mismatch"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_missing_bundle_record_is_rejected(self):
        del self.manifest["files"]["maidr.js"]
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.build()

    def test_unsafe_bundle_path_is_rejected(self):
        self.manifest["files"]["../SKILL.md"] = {"sha256": "0" * 64, "bytes": 1}
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "unsafe bundle path"):
            self.build()

    def test_symlink_is_rejected(self):
        item = self.skill / "references/link.md"
        try:
            item.symlink_to(self.skill / "SKILL.md")
        except OSError:
            self.skipTest("symlinks require platform permission")
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.build()

    def test_output_inside_source_and_invalid_commit_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside skills"):
            packager.package(self.root, self.skill / "bad.zip", COMMIT)
        with self.assertRaisesRegex(ValueError, "full Git SHA"):
            packager.package(self.root, self.output, "main")

    def test_git_provenance_requires_clean_tracked_skill_only(self):
        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.root), *args], text=True, stderr=subprocess.DEVNULL).strip()
        git("init")
        git("add", "skills")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "test")
        files = packager.collect(self.root)
        self.assertEqual(packager.source_commit(self.root, files), git("rev-parse", "HEAD"))
        (self.root / "README.md").write_text("untracked outside source", encoding="utf-8")
        cache = self.skill / "scripts/__pycache__/cache.pyc"
        cache.parent.mkdir()
        cache.write_bytes(b"cache")
        self.assertEqual(packager.source_commit(self.root, packager.collect(self.root)), git("rev-parse", "HEAD"))
        extra = self.skill / "references/untracked.md"
        extra.write_text("untracked", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "untracked"):
            packager.source_commit(self.root, packager.collect(self.root))
        extra.unlink()
        (self.skill / "SKILL.md").write_text("dirty", encoding="utf-8")
        with self.assertRaises(subprocess.CalledProcessError):
            packager.source_commit(self.root, packager.collect(self.root))

    def test_real_repository_bundle_and_layout(self):
        result = packager.package(ROOT, self.output, COMMIT)
        self.assertIn("maidr/SKILL.md", result["files"])
        self.assertIn("maidr/assets/maidr.js", result["files"])
        self.assertIn("maidr/scripts/to_artifact.py", result["files"])
        self.assertNotIn("README.md", result["files"])


if __name__ == "__main__":
    unittest.main()
