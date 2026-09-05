# Troubleshooting

Symptom first, then the usual cause and the fix. Run `python scripts/check_maidr_html.py page.html` before anything else; it catches most of these statically.

## The page loads but Tab never reaches the chart and nothing is announced

- **maidr.js did not load.** Open the browser console. A blocked CDN shows a network error on the script URL. Switch to the other CDN (`cdnjs.cloudflare.com/ajax/libs/maidr/4.6.0/maidr.min.js`), or copy `assets/maidr.js` and `assets/maidr-math.css` next to the page and load `./maidr.js`, or use the loader chain from `assets/template.html`.
- **The JSON does not parse.** Common causes: single quotes inside the JSON, a trailing comma, an unescaped apostrophe in a label (write `&#39;`), or the attribute wrapped in double quotes while the JSON also uses double quotes. The checker prints the character offset of the error.
- **No attachment method matched.** The JSON must sit in a `maidr` (or `maidr-data`) attribute, or in `window.maidr` with `id` equal to the SVG's `id`. A plain `<script type="application/json">` block is not read.
- **`axes` uses bare strings.** `"axes": { "x": "Day" }` is rejected; use `{ "x": { "label": "Day" } }`.
- **Unknown or misspelled `type`.** Scatter is `point`, histogram is `hist`, heatmap is `heat`. `candlestick_delta` must never be declared.
- **Empty `data` or wrong nesting.** `line`, `step`, `smooth`, and the grouped bar types need one inner array per series; `bar`, `point`, `hist`, `pie`, `box` are flat; `heat` is an object.

## Navigation works but nothing highlights on the chart

`selectors` does not resolve to exactly one element per data point, in data order. Point at the marks (`rect`, `circle`, `path`), not their `<g>` group, and check the count with the checker (needs `beautifulsoup4`) or in the console: `document.querySelectorAll('#id rect.bar').length`.

## Values are announced in the wrong order or against the wrong bar

`data` order and DOM order disagree. Emit the JSON in the same order the marks are drawn (left to right, or the library's series order).

## Numbers read as "1200.0" or with too many decimals

Format on the axis: `axes.y.format = { "type": "number", "decimals": 0 }` (JS), `ax.yaxis.set_major_formatter("{x:,.0f}")` (matplotlib), `scale_y_continuous(labels = scales::label_comma())` (ggplot2). Never pre-format numbers into strings inside `data`.

## py-maidr: `plt.show()` opens a normal window, not the accessible chart

`MPLBACKEND` points at a GUI backend, so maidr did not take over. Call `maidr.show(fig)` or `maidr.save_html(fig, "out.html")`, or unset `MPLBACKEND`. On matplotlib 3.8 use `matplotlib.use("module://maidr.backend")`.

## py-maidr: "Falling back to static image"

The plot type is unsupported (see `python.md`). Draw it anyway and tell the user, or restructure to a supported type if it stays faithful (a lollipop is a bar; a stacked area may be several lines).

## py-maidr: saved HTML is blank when opened offline

It was saved with `use_cdn="auto"` or `True` and the CDN is unreachable, or the `lib/` folder from `use_cdn=False` was not shipped alongside. Re-save with `use_cdn=False` and copy the `lib/` folder too, or set `MAIDR_CDN_VERSION=bundled`.

## py-maidr in Streamlit shows another user's chart or loses position

Always pass the figure to `render_maidr(fig, key=...)`; never rely on `plt.gcf()`. Cache the HTML string when the data has not changed so reruns do not rebuild the widget.

## r-maidr: "No Base R plots detected"

Base graphics must be drawn after `library(maidr)`, then `show()` is called with no argument. Check `getOption("maidr.base_r")` is `TRUE`. For quantmod or wordcloud charts, attach those packages before maidr or call `maidr::chartSeries()`.

## r-maidr: the ggplot prints as a plain plot

`options(maidr.ggplot2 = FALSE)` or `maidr_off()` was set, or the output is a non-HTML format (PDF, Word). Call `show(p)` explicitly or render to HTML.

## r-maidr: knitted document has static images

Only HTML formats get interactive widgets. Confirm `maidr_on()` runs in a setup chunk and the output format is HTML.

## Adapter charts (D3, Highcharts, ECharts) do nothing

- The adapter was loaded from cdnjs; adapters exist only on jsDelivr and npm.
- `maidr.js` was not loaded before a thin adapter (D3, Highcharts, ECharts, Vega-Lite, Google Charts, Frappe, Observable, Tableau, AnyChart need it; Chart.js and amCharts bundles are self-contained).
- The bind call ran before the chart finished rendering; call it after the library's render or ready callback.

## Claude artifacts and other sandboxed pages

Artifacts allow scripts from `cdnjs.cloudflare.com` and `cdn.jsdelivr.net/npm/`; local files and inline data URIs for scripts are blocked. Use a CDN URL (either host), keep the JSON inline in the attribute, and expect the AI chat to be unavailable unless the sandbox also permits the provider's API host.

## The AI chat asks for a key

Expected. MAIDR never ships with credentials; readers add their own OpenAI, Anthropic, or Gemini key under Settings (Ctrl+,), or point it at a local Ollama server (`http://localhost:11434`). Do not embed keys in the page.
