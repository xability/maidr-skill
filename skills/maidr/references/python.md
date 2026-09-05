# py-maidr reference

PyPI package `maidr` (import name `maidr`), version 1.23.x. Docs: https://py.maidr.ai. Source: https://github.com/xability/py-maidr. Python >= 3.9. matplotlib (>= 3.8) and seaborn (>= 0.13) are hard dependencies and are imported by `import maidr`.

## Install

```bash
pip install -U maidr                 # core: matplotlib, seaborn, mplfinance
pip install -U "maidr[plotly]"       # Plotly figures
pip install -U "maidr[altair]"       # Altair charts
pip install -U "maidr[shiny]"        # Shiny for Python widget
pip install -U "maidr[streamlit]"    # Streamlit component
uv add maidr                         # uv projects; `uv run python script.py` to run
python -c "import maidr; print(maidr.__version__)"
```

Development build: `pip install -U git+https://github.com/xability/py-maidr.git`. No conda package.

## Public API

| Call | What it does |
|---|---|
| `import maidr` | Patches matplotlib and seaborn at import and installs the `maidr` matplotlib backend, so `plt.show()` renders accessibly in scripts and notebooks. Prints a one-time warning that the backend switched. |
| `maidr.show(plot=None, renderer="auto", clear_fig=True, use_cdn=None)` | Render accessibly regardless of backend. `plot` can be a Figure, Axes, artist or BarContainer, a seaborn `FacetGrid`/`JointGrid`/`PairGrid`, a Plotly `Figure`, or an Altair `Chart`/`LayerChart`; `None` means the current figure. In notebooks it shows an inline iframe; in scripts it writes a temp HTML file and opens the browser (`renderer="browser"` forces that). |
| `maidr.save_html(plot=None, file, *, lib_dir="lib", include_version=True, data_in_svg=True, use_cdn=None) -> str` | Write a standalone HTML file. `file` is required (positional or keyword). Returns the path. |
| `maidr.render(plot=None, use_cdn=None) -> htmltools.Tag` | The accessible chart as an htmltools Tag for embedding in Flask, Django, FastAPI templates (`str(tag)`). |
| `maidr.stacked(ax_or_bar_container) -> Maidr` | Register stacked bars drawn with `bottom=` as a stacked-bar chart when auto-detection missed it; call `.show()` or `.save_html(file)` on the result. |
| `maidr.close(plot=None)` | Drop the registration for a figure (long-running apps). |
| `maidr.set_backend(use_maidr=True)` | Whether `plt.show()` goes through maidr. |
| `maidr.set_use_cdn(value)`, `maidr.get_use_cdn()` | Process-wide default for `use_cdn`: `True`, `False`, or `"auto"`. |
| `maidr.set_cdn_version("4.6.0" \| "bundled" \| "latest" \| None)` | Pin the maidr.js version used in CDN URLs. |
| `maidr.bundle_status()` | Compare the bundled maidr.js with the published release. |
| `maidr.read_bundled_js()`, `maidr.bundled_js_path()`, `maidr.bundled_math_css_path()` | The maidr.js source (and file paths) shipped inside the installed package, for inlining into a single file. |
| `from maidr.widget.shiny import output_maidr, render_maidr` | `output_maidr(id, width="100%", height="auto")` in the UI; `@render_maidr` (accepts `use_cdn=`) decorates the server function that returns the plot. |
| `from maidr.widget.streamlit import render_maidr, maidr_html` | `render_maidr(fig, height="content", width="stretch", tab_index=None, use_cdn=None)`; `maidr_html(fig)` returns the HTML string. |

That is the whole user-facing surface. There is no `maidr.set_engine`, `maidr.plot`, `maidr.enable`, or `maidr.accessible`.

## Supported plots

Stable (15): bar (`ax.bar`, `sns.barplot`), count (`sns.countplot`), dodged/grouped bars, stacked bars, box (`ax.boxplot`, `sns.boxplot`), violin (`sns.violinplot`, read as box + density layers), histogram (`ax.hist`, `sns.histplot`), line (`ax.plot`, `sns.lineplot`), step (`ax.step`), scatter (`ax.scatter`, `sns.scatterplot`), smooth (`sns.regplot`, `sns.lmplot`), heatmap (`ax.imshow`, `sns.heatmap`), pie (`ax.pie`), candlestick (mplfinance).

Experimental (23, work but may change): area and stacked area, boxen, choropleth, contour, error bar, funnel, gantt, gauge, hexbin, icicle, lollipop, normalized stacked bars, parallel coordinates, polar area, radar, sankey and alluvial, sunburst, treemap, waterfall, word cloud. Full list: https://py.maidr.ai/stability.html.

Anything else renders as a static image with the warning "Falling back to static image". Tell the user when that happens.

- Plotly: pass a `plotly.graph_objects.Figure` to `maidr.show()` or `maidr.save_html()`.
- Altair: `alt.Chart` and `alt.LayerChart` only. Facet, repeat, and concat charts are not accepted. Altair output always loads Vega from jsDelivr and cannot go offline.
- Multi-panel: `fig, axes = plt.subplots(2, 2)` becomes one figure with panel navigation. `ax.twinx()` becomes two layers. seaborn `FacetGrid`, `PairGrid`, `JointGrid`: pass the grid object.

## Make the announcement good

- Set a title, x label, and y label with units on every axes. They are read verbatim.
- Format numbers: `ax.yaxis.set_major_formatter("{x:,.0f}")`, `matplotlib.ticker.PercentFormatter()`, `StrMethodFormatter("${x:,.2f}")`. maidr reads the axis formatter, so readers hear "1,200" rather than "1200.0". The formatter also rounds what is announced (182,341 for 182340.50) while the JSON keeps the exact value, so match its precision to the data (`{x:,.2f}` when cents matter) or tell the user.
- Heatmap and hexbin colour axis: `sns.heatmap(df, z_label="Score")` or `ax.hexbin(x, y, z_label="Count")`. `z_label` is a py-maidr keyword; without it the axis is called "Level".
- Pie: `ax.set_xlabel("Region")` and `ax.set_ylabel("Share of sales")` name what slices and values mean.
- Series names come from `label=` in plot calls (the legend), so label every series.
- Word cloud: pass the `WordCloud` object to `imshow`, not `.to_array()`.

## Environments

| Where | Pattern |
|---|---|
| Script | `import maidr`, draw, then `maidr.save_html(fig, "out.html")`; `plt.show()` opens the accessible chart in the browser instead of a native window. |
| Jupyter, JupyterLab, VS Code, Colab | `import maidr` in the first cell; `plt.show()` or `maidr.show(fig)` renders an inline iframe. The bundled maidr.js is injected at import, so no network is needed. |
| Quarto (`.qmd`) | `format: html` and `jupyter: python3` in the YAML; `import maidr` once and `maidr.show(fig)` in each chunk. For reveal.js decks add `quarto add mcanouil/quarto-revealjs-a11y` (0.2.3+) and `revealjs-plugins: [a11y]` so Tab reaches the chart. |
| Shiny for Python | `ui.output_maidr("plot")` and `@render_maidr` on a function returning the figure. Pass `use_cdn=` to the decorator; do not use process-wide setters in a multi-session server. |
| Streamlit | `render_maidr(fig, key="sales")`. Always pass the figure; `plt.gcf()` is process-global and another session's chart can leak in. The chart is rendered in an iframe because Streamlit binds `r` document-wide. |
| Flask, Django, FastAPI | `tag = maidr.render(fig)` and place `str(tag)` in the template. |

## Offline and firewalled networks

| `use_cdn` | Behaviour |
|---|---|
| `"auto"` (default) | Emits `<script src="https://cdn.jsdelivr.net/npm/maidr@<version>/dist/maidr.js">` with an in-browser fallback to the bundled copy; `save_html()` therefore also writes `lib/maidr-<version>/` beside the file. One HTTPS lookup per process resolves `latest` to a concrete version (3 s timeout). Inside notebook, Shiny, and Flask iframes the fallback is not available: air-gapped deployments must use `False`. |
| `False` | Bundled maidr.js only. `save_html()` copies it to `lib/maidr-<version>/` beside the file (ship the folder with the HTML); iframe renders get it inlined. |
| `True` | CDN only, no fallback, no `lib/` folder: a single file that needs internet. |

Single self-contained file that also works offline (when the user wants exactly one file to send): save with `use_cdn=True`, then replace py-maidr's inline loader block (the `<script>` that injects the jsDelivr URL) with the bundled source. Verified with `check_maidr_html.py chart.html --browser`.

```python
import pathlib, re
import maidr

path = pathlib.Path("chart.html")
maidr.save_html(fig, str(path), use_cdn=True)
html = path.read_text(encoding="utf-8")
inline = "<script>" + maidr.read_bundled_js().replace("</script>", "<\\/script>") + "</script>"
loader = re.compile(r"<script\b[^>]*>(?:(?!</script>).)*?cdn\.jsdelivr\.net/npm/maidr@(?:(?!</script>).)*?</script>", re.S)
html = loader.sub(lambda m: inline, html, count=1)
path.write_text(html, encoding="utf-8")   # about 1.5 MB, no lib/ folder, no network needed
```

The inlined bundle cannot locate `maidr-math.css`, so math inside AI-chat replies renders unstyled; if that matters, prepend `<script>window.maidrMathStylesheetUrl = "https://cdn.jsdelivr.net/npm/maidr@4.6.0/dist/maidr-math.css";</script>` to `inline`.

Environment variables: `MAIDR_USE_CDN=auto|1|0`; `MAIDR_CDN_VERSION=4.6.0|bundled|latest` (`bundled` avoids all network requests); `MAIDR_CDN_TIMEOUT=3`; `MAIDR_BUNDLE_STALE_WARNING=0` silences the stale-bundle warning.

py-maidr never emits cdnjs URLs. If a page must load from `cdnjs.cloudflare.com`, save with `use_cdn=True` and rewrite the script `src` to `https://cdnjs.cloudflare.com/ajax/libs/maidr/4.6.0/maidr.min.js`, or use `use_cdn=False`.

## Embedding in a chat artifact

claude.ai and Claude Code render HTML artifacts in a sandbox that loads scripts only from cdnjs and jsDelivr and cannot see files, so the chart has to travel as HTML text with a CDN script. py-maidr output already fits: with `use_cdn=True` it is a single document (about 27 KB for a bar chart, 12 KB with `plt.rcParams["svg.fonttype"] = "none"`, which keeps axis text as text instead of glyph outlines) whose inline loader points at jsDelivr.

```python
import matplotlib.pyplot as plt
import maidr
plt.rcParams["svg.fonttype"] = "none"
# ... draw fig ...
maidr.save_html(fig, "chart.html", use_cdn=True)
```

Then `python scripts/to_artifact.py chart.html -o artifact.html` replaces the loader with one pinned `<script src>` (`--cdn cdnjs` to prefer cdnjs) and drops any `lib/` reference; `--fragment` strips the `<html>`/`<head>`/`<body>` shell for hosts that add their own, such as the Claude Code Artifact tool. In claude.ai, paste the full document as an HTML artifact. Inside the sandbox the AI chat (`?`) cannot reach a provider and sound starts after the reader clicks or tabs into the chart; everything else works.

## Gotchas

1. `MPLBACKEND` set to a GUI backend (TkAgg, QtAgg, MacOSX) stops `import maidr` from taking over `plt.show()`. Call `maidr.show(fig)` explicitly.
2. matplotlib 3.8 needs `matplotlib.use("module://maidr.backend")`; 3.9+ accepts `matplotlib.use("maidr")`.
3. `maidr.save_html(fig)` without `file` raises `TypeError`.
4. `use_cdn` must be exactly `True`, `False`, `"auto"`, or `None`; strings like `"false"` raise.
5. Passing something that is not a figure, axes, artist, or supported grid raises `TypeError: maidr cannot find a figure for ...`.
6. Drawing into a figure while it renders emits `MaidrRenderRaceWarning`; finish drawing before `show()`.
7. seaborn older than 0.13 raises a clear version error at import; upgrade seaborn.
8. Generated HTML embeds the JSON as a `maidr` attribute on the SVG; validate it with `scripts/check_maidr_html.py out.html`.
9. Inside the py-maidr repository itself, run examples with `uv run python script.py`.
