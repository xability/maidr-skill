# Contributor notes for maidr-skill

This repository distributes one Agent Skill, `skills/maidr`, that tells AI coding agents how to make charts accessible with MAIDR. Everything an installed agent reads lives under `skills/maidr/`; everything else here is packaging, documentation, or maintenance tooling.

## Layout

- `skills/maidr/SKILL.md`: the skill body. Keep it under 300 lines; move detail into `references/`.
- `skills/maidr/references/`: one file per binding (`python.md`, `r.md`, `javascript.md`), the JSON schema (`schema.md`), and `troubleshooting.md`.
- `skills/maidr/scripts/`: agent-runnable helpers. `detect_env.sh` and `detect_env.ps1` must stay behaviourally identical and print the same JSON shape. `check_maidr_html.py`, `fetch_dotpad_sdk.py` and `fetch_locale_packs.py` use only the standard library, the former with optional `beautifulsoup4` and `playwright`.
- `skills/maidr/assets/`: `template.html` (hand-authored example), the vendored `maidr.js` and `maidr-math.css`, `maidr-bundle.json` (provenance and SHA-256), and `dotpad-sdk.json` (the DotPad SDK pin that `scripts/fetch_dotpad_sdk.py` downloads on demand; the SDK itself is never vendored, it is 14 MB). The pin is a copy of the maidr.js package's `dist/dotpad-sdk.json`, refreshed by `tools/update-bundle.sh`; do not hand-edit it, and keep the docs version-generic ("the version named in `assets/dotpad-sdk.json`") so a new pin needs no prose change.
- `.claude-plugin/`: Claude Code plugin (`plugin.json`) and single-plugin marketplace (`marketplace.json`, `source: "./"`).
- `plugin.json` (repository root) and `.agents/plugins/marketplace.json`: the Codex / ChatGPT side of the same plugin. The root manifest is the portable [Agent Plugins](https://agent-plugins.org) format; its `extensions.com.openai.interface` holds the listing text (`displayName` and `shortDescription` at most 30 characters each) and points at `assets/logo.svg`, a square copy of the logo in xability/maidr's `media/logo.svg`. Claude Code reads only `.claude-plugin/`, and Codex prefers `.agents/plugins/marketplace.json` over it. Keep `name`, `description`, `author`, `license` and `keywords` the same in both manifests. Its `version` is the same release version as the Claude manifest's.
- `tests/`: regression tests for `check_maidr_html.py`, `fetch_locale_packs.py` and `to_artifact.py` (standard-library `unittest`), with real binding output under `tests/fixtures/` and the script that regenerates it. They live outside `skills/maidr/` so installed copies do not carry them.
- `evals/evals.json`: test prompts for exercising the skill with and without it installed.
- `tools/update-bundle.sh`: refreshes the vendored bundle, copies the release's `dist/dotpad-sdk.json` over `assets/dotpad-sdk.json` when the release ships one, and rewrites version pins. It first waits, for up to an hour, until the npm registry serves the version it was asked for, because npm serves a release minutes after `npm publish` returns (18 for 4.11.0). It is idempotent —
  re-vendoring the release already recorded in `maidr-bundle.json` leaves the working tree clean, which
  is what keeps the `update-bundle` workflow (run by maidr's release dispatch and daily) from committing an
  empty refresh to `main`. `retrieved` therefore dates the vendored bytes, not the last run.

## Facts must be verified

Every API name, URL, option, and keyboard shortcut in the skill was checked against the maidr, py-maidr, and r-maidr sources and their published docs. When you change one, cite where it comes from in the commit message. Do not add functions from memory; the skill explicitly tells agents not to invent APIs, and it has to hold itself to the same rule.

Current pins: maidr.js 4.11.0, py-maidr 1.25.x, maidr R package 0.5.x. The maidr.js version string appears in `SKILL.md` (frontmatter and CDN URLs), every reference file, both detect scripts, `check_maidr_html.py`, `assets/template.html`, `assets/maidr-bundle.json`, and `README.md`; `tools/update-bundle.sh` rewrites all of them. The pinned version is the vendored release and a floor, not what pages load: `detect_env` reports the latest npm release as `maidr_js_version` and the skill tells agents to use it, and `check_maidr_html.py` warns only on a version older than the vendored one. The plugin's own version is separate: see Releases below.

The README's "Network access and data" section is a disclosure that Anthropic's plugin directory scans on every new version: it names every host the scripts and the vendored maidr.js contact, and what is sent. When `update-bundle` vendors a release, check the section against it. `grep -oE 'https?://[A-Za-z0-9.:-]+' skills/maidr/assets/maidr.js | sort -u` lists the hosts in the bundle, and its `fetch(` and `import(` call sites show what goes to them. A version that sends data to a destination the README does not name cannot go live in the directory. `PRIVACY.md` restates the same recipients as a privacy policy (`plugin.json` points the OpenAI directory at it), so change the two together.

## Validate before committing

```bash
uvx --from skills-ref agentskills validate skills/maidr          # frontmatter and naming rules
python skills/maidr/scripts/check_maidr_html.py skills/maidr/assets/template.html
uv run --no-project --with beautifulsoup4 python -m unittest discover -s tests -v   # checker regression tests
bash skills/maidr/scripts/detect_env.sh . | python -m json.tool
pwsh -File skills/maidr/scripts/detect_env.ps1 . | ConvertFrom-Json  # on Windows
python - <<'EOF'
import json, hashlib
meta = json.load(open("skills/maidr/assets/maidr-bundle.json"))
for name, info in meta["files"].items():
    digest = hashlib.sha256(open(f"skills/maidr/assets/{name}", "rb").read()).hexdigest()
    assert digest == info["sha256"], name
print("bundle checksums ok")
EOF
```

CI (`.github/workflows/validate.yml`) runs the same checks.

## Conventions

- Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `ci:`); one logical change per commit.
- Work on a branch and open a pull request; `main` is what `npx skills add` and the Claude Code marketplace install from.
- Never edit a `version` or `CHANGELOG.md` by hand; semantic-release owns them (Releases below).
- Write for the agent that will read it: explain why a rule exists, prefer short tables and copyable code, keep trigger words in the frontmatter description.

## Releases

semantic-release (`.releaserc.json`, `.github/workflows/release.yml`) releases `main` once a week, on Mondays at 17:00 UTC: an hour after py-maidr (16:00) and two after maidr (15:00), so the week's release carries the maidr.js that `update-bundle` vendored that afternoon. `validate` runs first on the same commit, and a red `main` releases nothing; the workflow can also be started by hand. It reads the Conventional Commits since the last `v*` tag, and `tools/set-version.py` writes the version into `.claude-plugin/plugin.json`, `plugin.json` and the `metadata.version` in `SKILL.md`; CI fails when the three disagree. The first release, 0.1.0, was tagged by the workflow on its first run.

Each release reaches the distribution channels from the same run: `tools/package-plugin.py` zips the plugin as `maidr-plugin-X.Y.Z.zip` on the GitHub release, which is the package the OpenAI plugin directory takes as an upload (#15), and the `release` branch is moved to the release commit. Anthropic's plugin directory follows `release` (#14), and so do Codex users who add the marketplace with `--ref release`. Never push to `release` by hand.

The version is Claude Code's update signal: an installed copy updates only when it changes. So a commit that changes what an installed agent reads has to release. `feat` (minor), `fix`, `perf` and `revert` (patch) do by default, `docs(skill)`, `refactor(skill)` and `style(skill)` release a patch too, and `update-bundle` commits its refresh as `fix(bundle)`. Use the `skill` scope for any prose change under `skills/maidr/`; `docs:` without it (README, AGENTS.md) does not release. `!` after the type, or a `BREAKING CHANGE:` footer, releases a major. A squash merge takes its message from the pull request title, so the title is what decides the release.
