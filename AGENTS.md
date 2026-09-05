# Contributor notes for maidr-skill

This repository distributes one Agent Skill, `skills/maidr`, that tells AI coding agents how to make charts accessible with MAIDR. Everything an installed agent reads lives under `skills/maidr/`; everything else here is packaging, documentation, or maintenance tooling.

## Layout

- `skills/maidr/SKILL.md`: the skill body. Keep it under 300 lines; move detail into `references/`.
- `skills/maidr/references/`: one file per binding (`python.md`, `r.md`, `javascript.md`), the JSON schema (`schema.md`), and `troubleshooting.md`.
- `skills/maidr/scripts/`: agent-runnable helpers. `detect_env.sh` and `detect_env.ps1` must stay behaviourally identical and print the same JSON shape. `check_maidr_html.py` uses only the standard library, with optional `beautifulsoup4` and `playwright`.
- `skills/maidr/assets/`: `template.html` (hand-authored example), the vendored `maidr.js` and `maidr-math.css`, and `maidr-bundle.json` (provenance and SHA-256).
- `.claude-plugin/`: Claude Code plugin (`plugin.json`) and single-plugin marketplace (`marketplace.json`, `source: "./"`).
- `evals/evals.json`: test prompts for exercising the skill with and without it installed.
- `tools/update-bundle.sh`: refreshes the vendored bundle and rewrites version pins.

## Facts must be verified

Every API name, URL, option, and keyboard shortcut in the skill was checked against the maidr, py-maidr, and r-maidr sources and their published docs. When you change one, cite where it comes from in the commit message. Do not add functions from memory; the skill explicitly tells agents not to invent APIs, and it has to hold itself to the same rule.

Current pins: maidr.js 4.6.0, py-maidr 1.23.x, maidr R package 0.4.x. The maidr.js version string appears in `SKILL.md` (frontmatter and CDN URLs), every reference file, both detect scripts, `check_maidr_html.py`, `assets/template.html`, `assets/maidr-bundle.json`, and `README.md`; `tools/update-bundle.sh` rewrites all of them.

## Validate before committing

```bash
uvx --from skills-ref agentskills validate skills/maidr          # frontmatter and naming rules
python skills/maidr/scripts/check_maidr_html.py skills/maidr/assets/template.html
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
- Bump `version` in `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and the `metadata.version` in `SKILL.md` together, then tag `vX.Y.Z`.
- Write for the agent that will read it: explain why a rule exists, prefer short tables and copyable code, keep trigger words in the frontmatter description.
