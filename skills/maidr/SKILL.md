---
name: maidr
description: >-
  Make every chart, plot, graph, or data visualization accessible to blind and low-vision readers by building it with MAIDR (Multimodal Access and Interactive Data Representation): the visual chart stays exactly as designed and gains keyboard navigation, screen-reader text, sonification, braille, and AI descriptions. Use this skill whenever you are about to write plotting code or chart markup of any kind (matplotlib, seaborn, plotly, altair, ggplot2, base R graphics, D3, Chart.js, Highcharts, ECharts, Vega-Lite, Recharts, hand-written SVG) and whenever a user mentions accessibility, screen readers, WCAG, blind or low-vision users, sonification, or braille in connection with a chart, even if they never say "maidr". It picks the binding for the environment: py-maidr when Python is available, the maidr R package for R and ggplot2 work, and maidr.js (jsDelivr, cdnjs, or the vendored bundle for firewalled or offline environments) when neither runtime can run.
license: GPL-3.0-or-later
metadata:
  author: xability
  version: "0.1.0"
  maidr-js-version: "4.6.0"
  homepage: https://maidr.ai
  source: https://github.com/xability/maidr-skill
---

# Accessible charts with MAIDR

A chart delivered as pixels, or as an SVG with no data behind it, is invisible to a screen-reader user. MAIDR fixes that without touching the visual: the chart keeps its design, and a JSON description of the plotted data travels with it so `maidr.js` can let a reader move through the values with the arrow keys, hear them as tones, read them as text or braille, and ask an AI about them. The cost is one import or one script tag, so treat it as the default way to ship any chart rather than something to add when someone asks.

## Workflow

1. **Pick the binding** (next section). From the project directory run `scripts/detect_env.sh` (bash) or `scripts/detect_env.ps1` (PowerShell) for a JSON verdict, or judge from the same signals by hand.
2. **Draw the chart exactly as asked**, then route it through the binding using the recipes below. Keep the title and axis labels with units; they are what gets announced.
3. **Deliver something interactive**: an HTML file the user can open, or the inline render in a notebook, Quarto document, or Shiny app. A PNG alone is never the deliverable; if the user wants an image too, ship both.
4. **Verify** (see "Verify before you hand over").
5. **Explain how to use it** (see "What to tell the user").

## Pick the binding

| Situation | Use | Details |
|---|---|---|
| The user's code, files, or request are R: `.R`, `.Rmd`, `.qmd` with R chunks, `DESCRIPTION`, `renv.lock`, ggplot2, base graphics | **maidr R package** (CRAN `maidr`) | `references/r.md` |
| The chart lives in a JavaScript page or app: D3, Chart.js, Highcharts, ECharts, Vega-Lite, Plotly.js, React chart libraries, hand-drawn SVG | **maidr.js** with that library's adapter | `references/javascript.md` |
| Otherwise, and Python runs here (`python3 --version`, `python --version`, or `uv`) | **py-maidr** (PyPI `maidr`) | `references/python.md` |
| No Python and no R: browser-only sandboxes, artifacts, static HTML deliverables | **maidr.js** with hand-authored JSON | `references/javascript.md`, `references/schema.md` |

R is only for R work. Never move a Python or JavaScript user to R, and never move an R user to Python. When Python exists and the user wants "an HTML file" or "an artifact", py-maidr's `save_html()` is still the best route; hand-author maidr.js only when Python cannot run.

### How maidr.js reaches the page (every binding ends here)

| Source | When to use it | Notes |
|---|---|---|
| jsDelivr `https://cdn.jsdelivr.net/npm/maidr@4.6.0/dist/maidr.js` | Default whenever it is reachable | `maidr@latest` also works but changes under the reader; pin a version for anything that must keep working |
| cdnjs `https://cdnjs.cloudflare.com/ajax/libs/maidr/4.6.0/maidr.min.js` | The sandbox or firewall allows `cdnjs.cloudflare.com` but not jsDelivr (Claude artifacts allow both; some corporate CSPs allow only cdnjs) | Version-pinned only, no `latest` alias; only the core file is mirrored, not the chart-library adapters |
| Vendored bundle `assets/maidr.js` with `assets/maidr-math.css` beside it | No CDN is reachable, the deployment is air-gapped, or the deliverable must be one self-contained file | Copy both files next to the HTML and reference `./maidr.js`, or paste the bundle into an inline `<script>`. py-maidr (`use_cdn=False`) and r-maidr (default) already ship their own copy, so Python and R rarely need this |

The network probe runs on your machine; the reader's browser may sit behind a different firewall. Hand-written pages should carry the loader chain from `assets/template.html` (jsDelivr, then cdnjs, then a local file). maidr initializes correctly even when its script arrives after `DOMContentLoaded`, so a late fallback still works.

## Python: py-maidr

```bash
pip install -U maidr            # import name is `maidr`; extras: maidr[plotly] maidr[altair] maidr[shiny] maidr[streamlit]
```

```python
import matplotlib.pyplot as plt
import maidr                    # takes over plt.show() in scripts and notebooks

fig, ax = plt.subplots()
ax.bar(["Q1", "Q2", "Q3", "Q4"], [120, 200, 150, 280], color="steelblue")
ax.set_title("Revenue by quarter")
ax.set_xlabel("Quarter")
ax.set_ylabel("Revenue (USD thousands)")
ax.yaxis.set_major_formatter("{x:,.0f}")   # formatted numbers read better aloud

maidr.save_html(fig, "revenue.html")       # standalone file; or maidr.show(fig) / plt.show()
```

- Works with matplotlib, seaborn (including `seaborn.objects`), Plotly figures, Altair `Chart`/`LayerChart`, and mplfinance. Fifteen chart types are stable: bar, count, dodged bar, stacked bar, box, violin, histogram, line, step, scatter, smooth/regression, heatmap, pie, candlestick. Other types render but are experimental. An unsupported plot falls back to a static image with a warning; nothing crashes.
- `maidr.show(obj)` always renders accessibly. `plt.show()` does too after `import maidr`, unless `MPLBACKEND` names a non-inline backend. `maidr.render(obj)` returns an `htmltools` tag for Flask and similar servers. If a stacked bar chart drawn with `bottom=` is not recognized as stacked, register it with `maidr.stacked(ax)`.
- Subplots from `plt.subplots(rows, cols)`, twin axes, seaborn `FacetGrid`/`PairGrid`/`JointGrid`, and overlaid layers are supported; pass the figure or the grid.
- Offline or firewalled: `maidr.save_html(fig, "out.html", use_cdn=False)` writes the bundled maidr.js into a `lib/` folder beside the file (ship both), or set `MAIDR_CDN_VERSION=bundled`. The default `use_cdn="auto"` uses jsDelivr with an in-browser fallback to the bundle.
- Notebooks: `import maidr`, then draw. Quarto: `format: html` and `maidr.show(fig)` in the chunk. Shiny: `output_maidr()` with `@render_maidr`. Streamlit: `render_maidr(fig)`, always passing the figure. Details and gotchas: `references/python.md`.

## R: maidr package

```r
install.packages("maidr")       # development build: pak::pak("xability/r-maidr")
```

```r
library(maidr)                  # ggplot2 objects now print into the accessible viewer
library(ggplot2)

p <- ggplot(mpg, aes(class)) +
  geom_bar(fill = "steelblue") +
  labs(title = "Vehicle classes", x = "Class", y = "Count")

show(p)                         # RStudio viewer or browser
save_html(p, "classes.html")    # standalone file with maidr.js copied into lib/ beside it
```

- Base R graphics: draw first (`barplot(...)`, `hist(...)`, `plot(...)`), then call `show()` or `save_html(file = "out.html")` with no plot argument.
- Supported: bar, dodged, stacked, and normalized bars, pie (`coord_polar`), histogram, scatter, line, step, box, violin, heatmap (`geom_tile`, `image`), contour, smooth/density, candlestick (tidyquant, quantmod), plus `facet_wrap`/`facet_grid`, patchwork, and `par(mfrow)` panels.
- R Markdown and Quarto: call `maidr_on()` in a setup chunk; HTML output only (PDF gets static images). Shiny: `maidr_output("id")` in the UI and `render_maidr({ p })` in the server.
- Output is offline-ready by default (bundled maidr.js); `use_cdn = TRUE` switches to jsDelivr. Options, environments, and gotchas: `references/r.md`.

## JavaScript: maidr.js

Three ways to attach, in order of least work:

1. **Plotly.js**: load `maidr.js` after Plotly. Nothing else; Plotly charts are auto-detected.
2. **Chart libraries with an adapter**: D3, Chart.js, Highcharts, ECharts, Vega-Lite, Recharts, Victory, amCharts, AnyChart, Frappe, Google Charts, Observable Plot, Tableau. Load the adapter from `https://cdn.jsdelivr.net/npm/maidr@4.6.0/dist/<lib>.js` (adapters are jsDelivr-only) and call its bind helper. Per-library patterns: `references/javascript.md`.
3. **Any SVG you draw yourself**: put the MAIDR JSON in a `maidr` attribute on the `<svg>`.

```html
<script src="https://cdn.jsdelivr.net/npm/maidr@4.6.0/dist/maidr.js"></script>
<svg id="rev" width="480" height="300" maidr='{"id":"rev","title":"Revenue by quarter",
  "subplots":[[{"layers":[{"id":"rev-bars","type":"bar",
    "axes":{"x":{"label":"Quarter"},"y":{"label":"Revenue (USD thousands)"}},
    "selectors":"#rev rect.bar",
    "data":[{"x":"Q1","y":120},{"x":"Q2","y":200},{"x":"Q3","y":150},{"x":"Q4","y":280}]}]}]]}'>
  <rect class="bar" ... />   <!-- one bar per data point, in data order -->
</svg>
```

Rules that matter: the JSON `id` equals the SVG `id`; `axes` values are objects with a `label`, never bare strings; `data` follows the drawn order; `selectors` resolves to exactly one element per data point so highlighting lands on the right mark; `type` is one of the stable names `bar`, `line`, `point`, `hist`, `heat`, `box`, `pie`, `step`, `dodged_bar`, `stacked_bar`, `stacked_normalized_bar`, `smooth`, `candlestick`, `violin_box`, `violin_kde`. Per-type data shapes plus multi-panel and multi-layer layouts: `references/schema.md`. Start from `assets/template.html`.

## Verify before you hand over

Accessibility that is not verified is a claim, not a feature. Do as many of these as the environment allows:

1. `python scripts/check_maidr_html.py out.html` runs static checks: maidr.js is referenced from a source that will resolve, the JSON parses, ids match, trace types are known, data shapes fit the type, and selector counts match data counts. Add `--browser` to also load the page headlessly when the `playwright` Python package is installed.
2. With a browser tool (Playwright MCP, Chrome DevTools MCP): open the file, confirm there are no console errors and that maidr has wrapped the chart in an `<article>` and `<figure>` whose ids start with `maidr-article-` and `maidr-figure-` (followed by the chart id), then Tab to the chart and press Right Arrow; a text announcement of the first data point should appear.
3. py-maidr and r-maidr print a warning when a chart type fell back to a static image. Read the console output and tell the user instead of shipping a silent image.

## What to tell the user

Give the file path (and the `lib/` folder if one was written), how to open it, and this cheat sheet: Tab or click to focus the chart; Arrow keys move between data points; **B** braille, **T** text, **S** sound, **R** review mode; **L** then **T**, **X**, or **Y** announces the title or an axis label; **PageUp/PageDown** switches overlaid layers; in a multi-panel figure the arrows first move between panels, **Enter** opens one and **Escape** returns; **?** opens the AI chat, which uses the reader's own API key or a local Ollama model entered under Settings (**Ctrl+,**); nothing is sent anywhere until the reader configures it.

## Principles

- **Same chart, plus access.** Never swap the user's design, library, or language to satisfy maidr. If a chart type is unsupported, draw it anyway, let the binder fall back, and say so.
- **Data fidelity.** Announced values come from the JSON, not the pixels, so they must be the exact plotted values, in plotted order, with real titles and axis labels including units. Never round or summarize in the JSON.
- **Stable types first.** Experimental trace types may change without notice; prefer a stable representation when it is a faithful one.
- **No secrets in the page.** MAIDR's AI chat uses keys the reader enters locally. Never embed API keys.
- **Do not invent APIs.** Only the functions named in this skill and its references exist. When unsure, open the reference file instead of guessing a `maidr.something()`.

Blank page, nothing announced, CDN blocked, or backend conflicts: `references/troubleshooting.md`.
