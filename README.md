# maidr-skill

An [Agent Skill](https://agentskills.io) that teaches AI coding agents to make every chart they create accessible with [MAIDR](https://maidr.ai) (Multimodal Access and Interactive Data Representation). The visual chart stays exactly as designed; blind and low-vision readers additionally get keyboard navigation, screen-reader text, sonification, braille, and AI descriptions.

Works with Claude Code, OpenAI Codex, Cursor, GitHub Copilot, Gemini CLI, and any other agent that reads the open `SKILL.md` format.

## What the agent does once the skill is installed

Whenever a user asks for a chart, plot, or visualization, the agent:

1. Detects the environment and picks the binding:
   - **R project or ggplot2 / base graphics request** -> the [`maidr` R package](https://r.maidr.ai) (CRAN).
   - **JavaScript page or app** (D3, Chart.js, Highcharts, ECharts, Vega-Lite, Plotly.js, React chart libraries, hand-drawn SVG) -> [`maidr.js`](https://maidr.ai) with that library's adapter.
   - **Otherwise, Python available** -> [`py-maidr`](https://py.maidr.ai) (`pip install maidr`).
   - **No Python, no R** (browser-only sandboxes, artifacts, static HTML) -> `maidr.js` with hand-authored MAIDR JSON.
2. Loads `maidr.js` from jsDelivr, falls back to cdnjs when a firewall or content-security policy allows only that host, and falls back to the vendored bundle shipped in this repository when no CDN is reachable.
3. Draws the chart the user asked for, routes it through the binding, and verifies the output with the bundled checker before handing it over with a short keyboard cheat sheet.

## See it in a chat

Two public artifacts show what the skill produces when the chart is embedded in a conversation instead of shipped as a file. Open one, press Tab (or click the chart), then use the arrow keys; **B**, **T**, **S**, and **R** toggle braille, text, sound, and review mode.

- [Hand-authored SVG with MAIDR JSON](https://claude.ai/code/artifact/05de1e51-7fd4-4aa1-83e8-c1b4525e6393): the `assets/template.html` approach, maidr.js loaded from cdnjs.
- [matplotlib chart saved by py-maidr](https://claude.ai/code/artifact/056a2136-3cef-40b2-8d00-2d89cc6c4c6c): `maidr.save_html(fig, use_cdn=True)` reshaped by `scripts/to_artifact.py`.

Inside the artifact sandbox everything works except the AI chat (`?`), which cannot reach a model provider from there; sound starts after the first click or Tab into the chart.

## Install

### Any agent (recommended)

```bash
npx skills add xability/maidr-skill
```

The [skills CLI](https://skills.sh) lets you pick which agents to install into (Claude Code, Codex, Cursor, Copilot, Gemini CLI, OpenCode, and more). Add `-g` for a user-wide install, `--agent claude-code codex` to target specific agents, or `--all` to skip prompts.

### Claude Code

```text
/plugin marketplace add xability/maidr-skill
/plugin install maidr@maidr-skill
```

Or copy the skill directory by hand: `skills/maidr` -> `~/.claude/skills/maidr` (all projects) or `.claude/skills/maidr` (one project).

### OpenAI Codex

Ask Codex: `$skill-installer install the skill at https://github.com/xability/maidr-skill/tree/main/skills/maidr`, or run `npx skills add xability/maidr-skill --agent codex`. Manual: copy `skills/maidr` to `~/.codex/skills/maidr` (user) or `.agents/skills/maidr` (repository).

### Cursor, GitHub Copilot, Gemini CLI, and others

`npx skills add xability/maidr-skill --agent cursor` (or `github-copilot`, `gemini-cli`, ...). Agents that read the universal project location find the skill at `.agents/skills/maidr`.

### Manual

```bash
git clone https://github.com/xability/maidr-skill.git
cp -r maidr-skill/skills/maidr <your-agent's skills directory>/maidr
```

## What is inside

```text
skills/maidr/
  SKILL.md                     the skill: decision tree, recipes, verification, principles
  references/python.md         py-maidr API, environments, offline mode, gotchas
  references/r.md              maidr R package API, R Markdown/Quarto/Shiny, gotchas
  references/javascript.md     loading maidr.js, attachment methods, chart-library adapters
  references/schema.md         MAIDR JSON schema by trace type, multi-layer and multi-panel layouts
  references/troubleshooting.md symptom -> cause -> fix
  scripts/detect_env.sh        environment probe (bash): runtimes, project signals, CDN reachability, verdict
  scripts/detect_env.ps1       the same probe for PowerShell
  scripts/check_maidr_html.py  static validator for MAIDR-enabled HTML (optional headless browser check)
  scripts/to_artifact.py       reshape py-maidr or any maidr page for chat artifacts (one pinned CDN script, no lib/)
  assets/template.html         hand-authored bar chart with the jsDelivr -> cdnjs -> local loader chain
  assets/candlestick.html      hand-authored candlestick, for when the plotting library cannot draw one
  assets/maidr.js              vendored maidr.js 4.6.0 for offline or firewalled use
  assets/maidr-math.css        stylesheet maidr.js fetches beside itself for math in AI-chat replies
  assets/maidr-bundle.json     version, source URLs, and SHA-256 of the vendored files
  agents/openai.yaml           display metadata for Codex and ChatGPT
.claude-plugin/                Claude Code plugin and marketplace manifests
evals/evals.json               test prompts used to exercise the skill
tools/update-bundle.sh         refresh the vendored bundle and version pins
```

## Verifying a chart yourself

```bash
python skills/maidr/scripts/check_maidr_html.py chart.html            # static checks
python skills/maidr/scripts/check_maidr_html.py chart.html --browser  # plus a headless load (needs `pip install playwright`)
```

Then open the file, press Tab to reach the chart, and use the arrow keys. **B** toggles braille, **T** text, **S** sound, **R** review mode. Four global shortcuts open maidr's own interfaces:

| Action | Windows / Linux | macOS |
|---|---|---|
| Show or hide the keyboard shortcut help | Ctrl + / | Command + / |
| Open the command palette listing every available command | Ctrl + Shift + P | Command + Shift + P |
| Open the AI chat (requires the reader's own API key, entered in Settings, or a local Ollama server) | Shift + / (that is, **?**) | Shift + / (**?**) |
| Open Settings | Ctrl + , | Command + , |

## Keeping the vendored maidr.js current

```bash
tools/update-bundle.sh          # latest release on npm
tools/update-bundle.sh 4.7.0    # a specific version
```

The script downloads `maidr.js` and `maidr-math.css` from jsDelivr, records their SHA-256 in `assets/maidr-bundle.json`, and rewrites the version pins across the skill. Re-vendoring a release that is already vendored changes nothing, so the script is safe to re-run.

A scheduled GitHub Action runs it weekly and opens a pull request only when a new release exists. Opening that pull request needs one of:

- **Settings > Actions > General > Workflow permissions**, with *Allow GitHub Actions to create and approve pull requests* enabled (an organization can also enforce this switch off from its own settings, which overrides the repository), or
- a `BUNDLE_UPDATE_TOKEN` repository secret holding a personal access token with `repo` scope, which the workflow prefers when present.

Without either, the job pushes `chore/update-maidr-bundle` and then fails with `GitHub Actions is not permitted to create or approve pull requests`.

## Related projects

- [xability/maidr](https://github.com/xability/maidr): the maidr.js engine ([docs](https://maidr.ai))
- [xability/py-maidr](https://github.com/xability/py-maidr): Python binding for matplotlib, seaborn, Plotly, Altair ([docs](https://py.maidr.ai))
- [xability/r-maidr](https://github.com/xability/r-maidr): R package for ggplot2 and base graphics ([docs](https://r.maidr.ai))

## License

GPL-3.0-or-later, the same license as maidr, py-maidr, and r-maidr. The vendored `assets/maidr.js` is an unmodified copy of the npm release and keeps its GPL-3.0-or-later license.
