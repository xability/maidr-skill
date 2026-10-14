#!/usr/bin/env python3
"""Build the standalone Agent Skill, not the versioned Claude/Codex plugin.

From a clean checkout of main:
    python tools/package-skill.py dist/maidr-skill.zip
    python -m unittest discover -s tests -p 'test_package_skill.py' -v

The ZIP contains maidr/SKILL.md and all skill assets/references/scripts/agents,
never repository manifests, tests, tools or caches. Beside it are
maidr-skill.zip.sha256 (sha256sum format) and maidr-skill.provenance.json
(source commit, archive checksum and per-file checksums). The CLI refuses dirty
or untracked non-cache skill inputs so the source commit describes the bytes.
Only Python's standard library is needed. No versions or Git refs are changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"__pycache__", ".git", ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}


def excluded(relative: Path) -> bool:
    return bool(SKIP_DIRS.intersection(relative.parts)) or relative.name in SKIP_FILES or relative.suffix in {".pyc", ".pyo"}


def collect(root: Path) -> dict[str, bytes]:
    source = root / "skills" / "maidr"
    if source.is_symlink() or not source.is_dir():
        raise ValueError("skills/maidr must be a real directory")
    files = {}
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        if excluded(relative):
            continue
        if item.is_symlink():
            raise ValueError(f"symlinks are not allowed: {relative}")
        if item.is_file():
            if "\\" in relative.as_posix():
                raise ValueError(f"unsafe archive path: {relative}")
            files["maidr/" + relative.as_posix()] = item.read_bytes()
    if not files.get("maidr/SKILL.md", b"").strip():
        raise ValueError("SKILL.md is missing or empty")
    for directory in ("assets", "references", "scripts"):
        if not any(name.startswith(f"maidr/{directory}/") for name in files):
            raise ValueError(f"skill {directory} is missing or empty")
    validate_bundle(files)
    return files


def validate_bundle(files: dict[str, bytes]) -> None:
    manifest = json.loads(files["maidr/assets/maidr-bundle.json"])
    recorded = manifest["files"]
    if not {"maidr.js", "maidr-math.css"}.issubset(recorded):
        raise ValueError("vendored bundle manifest is incomplete")
    for name, info in recorded.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError(f"unsafe bundle path: {name}")
        content = files["maidr/assets/" + name]
        if len(content) != info["bytes"] or hashlib.sha256(content).hexdigest() != info["sha256"]:
            raise ValueError(f"vendored bundle checksum/size mismatch: {name}")


def source_commit(root: Path, files: dict[str, bytes]) -> str:
    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
    commit = git("rev-parse", "HEAD")
    subprocess.run(["git", "-C", str(root), "diff", "--quiet", "HEAD", "--", "skills/maidr"], check=True)
    tracked = {p.removeprefix("skills/") for p in git("ls-files", "-z", "--", "skills/maidr").split("\0") if p and not excluded(Path(p).relative_to("skills/maidr"))}
    if tracked != set(files):
        raise ValueError("skill has untracked or missing files; use a clean checkout")
    return commit


def package(root: Path, output: Path, commit: str, files: dict[str, bytes] | None = None) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("source commit must be a full Git SHA-1")
    if output.suffix != ".zip" or output.resolve().is_relative_to((root / "skills").resolve()):
        raise ValueError("output must be a .zip outside skills/")
    files = collect(root) if files is None else files
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, content in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                mode = 0o755 if name.endswith(".sh") else 0o644
                info.external_attr = (0o100000 | mode) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None or archive.namelist() != sorted(files):
                raise ValueError("archive validation failed")
            for name, content in files.items():
                if archive.read(name) != content:
                    raise ValueError(f"archive content differs: {name}")
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        provenance = {
            "schema_version": 1,
            "source": {"commit": commit, "path": "skills/maidr"},
            "archive": {"name": output.name, "sha256": digest, "bytes": temporary.stat().st_size},
            "files": {name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)} for name, data in sorted(files.items())},
        }
        os.replace(temporary, output)
        output.with_suffix(".provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
        output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
        return provenance
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", type=Path, help="ZIP path, normally dist/maidr-skill.zip")
    args = parser.parse_args()
    try:
        files = collect(ROOT)
        commit = source_commit(ROOT, files)
        result = package(ROOT, args.output, commit, files)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"package-skill: {error}\n")
    print(f"{args.output}: {len(result['files'])} files; source {commit}; sha256 {result['archive']['sha256']}")


if __name__ == "__main__":
    main()
