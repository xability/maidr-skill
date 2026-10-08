# maidr-skill

An [Agent Skill](https://agentskills.io) that teaches AI coding agents to make every chart they create accessible with [MAIDR](https://maidr.ai) (Multimodal Access and Interactive Data Representation). The visual chart stays exactly as designed; blind and low-vision readers additionally get keyboard navigation, screen-reader text, sonification, braille, and AI descriptions.

Works with Claude Code, OpenAI Codex, ChatGPT Work, Cursor, GitHub Copilot, Gemini CLI, and any other agent that reads the open `SKILL.md` format.

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

In ChatGPT Work the chart appears in the conversation the same way, through Work's `visualize` surface: `scripts/to_artifact.py --visualize` turns py-maidr output into the fragment that surface takes.

In the ChatGPT desktop app, the reader can also open the chart page in the app's built-in browser. maidr's own tools then reach ChatGPT Work and Codex as site tools, so the model can answer from the chart and move the reader through it. This has not been tried in the app yet.

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

```bash
codex plugin marketplace add xability/maidr-skill --ref release
codex plugin add maidr@maidr-skill
```

In the ChatGPT desktop app, the same marketplace then appears as a source in the Plugins Directory. `codex plugin marketplace upgrade maidr-skill` pulls the latest weekly release; leave out `--ref release` to follow `main` instead.

To install the bare skill instead, ask Codex: `$skill-installer install the skill at https://github.com/xability/maidr-skill/tree/main/skills/maidr`, or run `npx skills add xability/maidr-skill --agent codex`. Manual: copy `skills/maidr` to `~/.codex/skills/maidr` (user) or `.agents/skills/maidr` (repository).

### ChatGPT Work

Ask ChatGPT Work: `install the skill at https://github.com/xability/maidr-skill/tree/main/skills/maidr`. Its built-in skill installer copies the skill into `$CODEX_HOME/skills`, and the skill is available from the next turn. Charts then appear in the conversation itself, through Work's `visualize` surface, rather than as files to download.

### Cursor, GitHub Copilot, Gemini CLI, and others

`npx skills add xability/maidr-skill --agent cursor` (or `github-copilot`, `gemini-cli`, ...). Agents that read the universal project location find the skill at `.agents/skills/maidr`.

### Manual

```bash
git clone https://github.com/xability/maidr-skill.git
cp -r maidr-skill/skills/maidr <your-agent's skills directory>/maidr
```

## Example prompts

With the skill installed, ask for a chart the way you normally would; you do not have to mention MAIDR or accessibility. The agent picks the binding from the project and the environment. Each prompt below names the route and the maidr layer type the agent is expected to produce. Types marked *experimental* may change in any maidr release (see `references/schema.md`).

### Data analysis in Python

| Scenario | Prompt | Route and type |
| --- | --- | --- |
| Exploring a dataset | "Load `penguins.csv` and plot flipper length against body mass, coloured by species." | py-maidr, seaborn, `point` |
| Sales report | "Make a bar chart of total revenue per region from `sales.xlsx` and save it as `revenue.html`." | py-maidr, `bar` |
| Comparing groups | "Show a grouped bar chart of average test scores by school and year." | py-maidr, `dodged_bar` |
| Composition | "Stack monthly energy use by source (gas, solar, wind) for 2025, and a second chart normalised to 100%." | py-maidr, `stacked_bar`, `stacked_normalized_bar` |
| Time series | "Plot daily closing prices of the three tickers in `prices.csv` as lines over the last year." | py-maidr, `line` |
| Distributions | "Histogram of trip durations in `trips.parquet` with 30 bins." | py-maidr, `hist` |
| Experiment results | "Box plots of reaction time by condition, then the same data as violin plots." | py-maidr, `box`, `violin_box` + `violin_kde` |
| Correlations | "Draw a correlation heatmap of the numeric columns, with the values printed in the cells." | py-maidr, `heat` |
| Regression | "Scatter of advertising spend against sales with a fitted regression line." | py-maidr, seaborn `regplot`, `point` + `smooth` |
| Finance | "Candlestick chart of BTC's daily OHLC for the last 60 days." | py-maidr, mplfinance, `candlestick` |
| Faceting | "One line chart per country in a 2 x 3 grid, sharing the y axis." | py-maidr, multi-panel `subplots` |
| Machine learning | "Plot the ROC curves of my three classifiers with their AUC in the legend." | py-maidr, `roc` (*experimental*) |
| Notebooks | "In this Jupyter notebook, make every chart from here on accessible." | py-maidr, `import maidr` before plotting |

### R and Quarto

| Scenario | Prompt | Route and type |
| --- | --- | --- |
| ggplot2 | "Using ggplot2, plot `mpg` highway mileage by class as a bar chart of means." | maidr R package, `bar` |
| Statistical report | "In `report.qmd`, add a scatter of `displ` against `hwy` with a `geom_smooth` line." | maidr R package, `point` + `smooth` |
| Teaching | "Make a histogram and a box plot of `faithful$eruptions` for my intro statistics slides." | maidr R package, `hist`, `box` |
| Dashboards | "Add an accessible line chart of `economics$unemploy` to this Shiny app." | maidr R package, Shiny output |
| Base graphics | "Use base R `barplot()` to show the `VADeaths` table as stacked bars." | maidr R package, `stacked_bar` |

### JavaScript and the web

| Scenario | Prompt | Route and type |
| --- | --- | --- |
| A web page | "Add a D3 bar chart of monthly signups to `index.html`." | maidr.js, D3 adapter, `bar` |
| A dashboard | "Build a React dashboard with a Recharts line chart of traffic and a pie chart of devices." | maidr.js, Recharts adapter, `line`, `pie` |
| Existing chart | "This page already has a Chart.js chart. Make it accessible without changing how it looks." | maidr.js, Chart.js adapter |
| Declarative specs | "Turn this Vega-Lite spec into a page with an accessible scatter plot." | maidr.js, Vega-Lite adapter, `point` |
| Hand-drawn SVG | "I drew this SVG step chart by hand; wire it up so screen-reader users can explore it." | maidr.js, hand-written MAIDR JSON, `step` |

### Charts in a chat, with no Python or R

| Scenario | Prompt | Route and type |
| --- | --- | --- |
| Quick look | "Show me a bar chart of these numbers right here in the chat: apples 12, pears 7, plums 15." | maidr.js in an artifact, `bar` |
| Explaining a concept | "Draw a normal distribution and a right-skewed one so I can hear the difference." | maidr.js, `line` |
| Planning | "Make a timeline of this project's four phases from the dates below." | maidr.js, `gantt` (*experimental*) |
| Funnel metrics | "Show our signup funnel: visited 10,000, signed up 2,400, activated 900, paid 210." | maidr.js, `funnel` (*experimental*) |
| Hierarchies | "Show this department budget as a treemap." | maidr.js, `treemap` (*experimental*) |

### Checking and fixing

- "Check `chart.html` and tell me what a screen-reader user would miss." The agent runs `scripts/check_maidr_html.py` and fixes what it reports.
- "The highlight does not move when I press the arrow keys. Why?" The agent follows `references/troubleshooting.md`: usually a selector that matches the wrong number of elements.
- "Our firewall blocks jsDelivr. Make this page work offline." The agent switches to cdnjs or the vendored `assets/maidr.js`.
- "Show the chart in Korean." The agent loads maidr.js's Korean locale pack beside the bundle.
- "My reader uses a Dot Pad. Make sure this chart works on it." The agent fetches the pinned Dot Pad SDK for an offline page.

### Whole conversations

- **A blind student's homework.** "I'm a screen-reader user. Plot these 40 exam scores as a histogram, tell me which keys to press to explore it, and whether the distribution is skewed."
- **A research paper.** "For each figure in `analysis.py`, keep the visual exactly as it is but also save an accessible HTML version next to the PNG."
- **A data journalist.** "Make an accessible line chart of rent prices in five cities since 2010 for our article, and a short alt text to go with it."
- **An accessibility review.** "Go through every chart in this repository, make each one accessible with MAIDR, and list what you changed."

## Network access and data

The plugin is instructions, helper scripts, and a vendored copy of maidr.js. It has no hooks, no MCP servers, and no background processes, and it needs no account or API key of its own. It collects no telemetry and sets no cookies, and nothing it does is sent to its authors or to Anthropic. This section lists everything an agent with the skill installed can run, fetch, or send, and what the chart pages it writes do when a reader opens them. The same facts, as a policy, are in [PRIVACY.md](PRIVACY.md).

### What the agent runs

| Step | When | Connects to |
|---|---|---|
| `scripts/detect_env.sh` or `detect_env.ps1` | Before the first chart of a task | Reads the installed runtimes and the project's file names on this machine. Asks `registry.npmjs.org` for the latest maidr.js release, and sends HEAD requests to `cdn.jsdelivr.net`, `cdnjs.cloudflare.com`, `pypi.org`, and `cloud.r-project.org` to see which are reachable. Nothing from the machine or the project is sent. |
| `pip install maidr` or `uv add maidr` | Python route, when py-maidr is missing | `pypi.org` |
| `install.packages("maidr")` | R route, when the package is missing | CRAN |
| `npm install maidr` | JavaScript route, when the project already builds with npm | `registry.npmjs.org` |
| `scripts/check_maidr_html.py` | After a chart is written | Nothing. With `--browser` (Playwright, installed by the user) it opens the local file in headless Chromium, which loads maidr.js from the CDN the page names. |
| `scripts/to_artifact.py` | For a chart shown in a chat | Nothing; it rewrites a local file. |
| `python -m http.server --bind 127.0.0.1` | To preview a page in a browser tool | Listens on localhost only. |
| `scripts/fetch_dotpad_sdk.py`, `scripts/fetch_locale_packs.py` | Only when a page must drive a Dot Pad or show a non-English pack offline | `cdn.jsdelivr.net`. Each file is checked against a recorded SHA-256 and written to disk; the scripts never run what they download. |
| Development builds and Quarto extensions | Only in the cases the references name: a development build, Quarto reveal.js slides, Observable Plot in Quarto | GitHub: `pip install git+https://github.com/xability/py-maidr.git`, `pak::pak("xability/r-maidr")`, `quarto add xability/maidr`, `quarto add mcanouil/quarto-revealjs-a11y` |

`tools/update-bundle.sh` downloads from jsDelivr and the npm registry. Maintainers and this repository's `update-bundle` workflow run it; the skill does not ask an agent to.

### What a chart page does when a reader opens it

- It loads maidr.js from jsDelivr, from cdnjs when the agent chose that, or from the vendored copy when no CDN is reachable. maidr.js takes its math stylesheet and any locale pack from the same place. The CDN sees the reader's IP address and browser headers, as it does for any script tag. A Plotly or Bokeh page passed through `scripts/to_artifact.py` loads plotly.js or BokehJS from jsDelivr as well, instead of from `cdn.plot.ly` or `cdn.bokeh.org`.
- Connecting a Dot Pad makes maidr.js import the vendor's SDK from `cdn.jsdelivr.net/gh/xability/dotpad-sdk-guide@<commit>/`. `fetch_dotpad_sdk.py` lets an offline page carry its own copy.
- When the browser offers the WebMCP API (`navigator.modelContext`) on a secure origin, maidr.js registers three chart tools (`maidr_list_charts`, `maidr_get_layer_data`, `maidr_navigate`) for an AI agent running in the reader's browser. maidr.js itself sends nothing; an agent that calls the tools, such as ChatGPT in its desktop app's built-in browser, receives the chart's data, and that agent's provider handles it like anything else the agent reads. `<meta name="maidr-webmcp" content="off">` turns the tools off.
- It keeps the reader's settings in the browser's `localStorage` under `maidr-settings`.

### AI chat, only when the reader opens it

The chat stays off until the reader enters their own API key, or an Ollama server address, in Settings. When the reader then asks a question, the page sends the chart image, the chart's MAIDR JSON (title, labels, values), the text for the current point, and the question straight from the reader's browser to the provider the reader chose:

| Provider | Host |
|---|---|
| OpenAI | `api.openai.com` |
| Anthropic | `api.anthropic.com` |
| Google Gemini | `generativelanguage.googleapis.com` |
| Ollama | the server address the reader enters (`http://localhost:11434` by default) |

Entering a key also sends it to that provider's model-list endpoint, to check the key and list the models. The key is stored only in the reader's `localStorage`. Do not put data that must stay private in a chart whose readers will use the chat: the values leave the page when they ask a question.

maidr.js also contains the address of a MAIDR-hosted relay, `maidr-service.azurewebsites.net`, which it uses only when a client token is present in its settings. This skill never sets one, and the Settings panel has no field for one, so no chart this skill produces reaches that host.

### The vendored bundle

`skills/maidr/assets/maidr.js` (minified) and `maidr-math.css` are unmodified copies of the npm release named in `assets/maidr-bundle.json`. CI compares each file's SHA-256 with the same file in that release on jsDelivr, so the copy can be checked byte for byte. The readable source is [xability/maidr](https://github.com/xability/maidr), at the tag `v` followed by the version in `assets/maidr-bundle.json`.

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
  scripts/to_artifact.py       reshape py-maidr or any maidr page for chat artifacts (one pinned CDN script, no lib/) or a ChatGPT Work visualize fragment
  scripts/fetch_dotpad_sdk.py  download the DotPad tactile-display SDK maidr.js is pinned to, for offline pages (not vendored: 14 MB)
  scripts/fetch_locale_packs.py put maidr.js's non-English locale packs beside a local maidr.js (not vendored)
  assets/template.html         hand-authored bar chart with the jsDelivr -> cdnjs -> local loader chain
  assets/candlestick.html      hand-authored candlestick, for when the plotting library cannot draw one
  assets/maidr.js              vendored maidr.js 4.14.0 for offline or firewalled use
  assets/maidr-math.css        stylesheet maidr.js fetches beside itself for math in AI-chat replies
  assets/maidr-bundle.json     version, source URLs, and SHA-256 of the vendored files
  assets/dotpad-sdk.json       version, commit, URLs, and SHA-256 of the DotPad SDK files fetch_dotpad_sdk.py downloads (copied from maidr.js's dist/dotpad-sdk.json)
  agents/openai.yaml           display metadata for Codex and ChatGPT
.claude-plugin/                Claude Code plugin and marketplace manifests
plugin.json                    portable Agent Plugins manifest with the Codex / ChatGPT listing (extensions.com.openai)
.agents/plugins/marketplace.json  Codex marketplace
assets/logo.svg                square MAIDR logo for the Codex / ChatGPT listing
evals/evals.json               test prompts used to exercise the skill
tools/update-bundle.sh         refresh the vendored bundle, the DotPad SDK pin, and version pins
tools/set-version.py           write a release version into both manifests and SKILL.md (run by semantic-release)
tools/package-plugin.py        zip the plugin for the OpenAI plugin directory (attached to each GitHub release)
.releaserc.json                semantic-release configuration
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

The script downloads `maidr.js` and `maidr-math.css` from jsDelivr, records their SHA-256 in `assets/maidr-bundle.json`, and rewrites the version pins across the skill. It also fetches the release's `dist/dotpad-sdk.json`, the DotPad SDK pin maidr.js is built against, into `assets/dotpad-sdk.json`; a release that does not ship that file leaves the asset as it is, and the script says so. Re-vendoring a release that is already vendored changes nothing, so the script is safe to re-run.

The `update-bundle` workflow runs it and commits the refresh straight to `main`: maidr's release workflow notifies this repository the moment a release reaches npm (a `maidr-released` repository dispatch), and a daily run catches a notification that never arrives. It then starts `validate` on `main`, because a push made with the workflow's own token starts no workflows.

Pages do not wait for that refresh either. `scripts/detect_env.sh` (and `.ps1`) looks up the latest release on npm and reports it as `maidr_js_version`, and the skill tells the agent to put that version in every URL; the vendored version is only the fallback when the lookup fails. The refresh is committed as a `fix`, so the next weekly release (Mondays 17:00 UTC, an hour after py-maidr's) is at least a patch, and an installed plugin picks it up on its next update.

## Related projects

- [xability/maidr](https://github.com/xability/maidr): the maidr.js engine ([docs](https://maidr.ai))
- [xability/py-maidr](https://github.com/xability/py-maidr): Python binding for matplotlib, seaborn, Plotly, Altair ([docs](https://py.maidr.ai))
- [xability/r-maidr](https://github.com/xability/r-maidr): R package for ggplot2 and base graphics ([docs](https://r.maidr.ai))

## License

GPL-3.0-or-later, the same license as maidr, py-maidr, and r-maidr. The vendored `assets/maidr.js` is an unmodified copy of the npm release and keeps its GPL-3.0-or-later license.
