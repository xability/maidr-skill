# Troubleshooting

Symptom first, then the usual cause and the fix. Run `python scripts/check_maidr_html.py page.html` before anything else; it catches most of these statically.

## The page loads but Tab never reaches the chart and nothing is announced

- **maidr.js did not load.** Open the browser console. A blocked CDN shows a network error on the script URL. Switch to the other CDN (`cdnjs.cloudflare.com/ajax/libs/maidr/4.12.0/maidr.min.js`), or copy `assets/maidr.js` and `assets/maidr-math.css` next to the page and load `./maidr.js`, or use the loader chain from `assets/template.html`.
- **The JSON does not parse.** Common causes: single quotes inside the JSON, a trailing comma, an unescaped apostrophe in a label (write `&#39;`), or the attribute wrapped in double quotes while the JSON also uses double quotes. The checker prints the character offset of the error.
- **No attachment method matched.** The JSON must sit in a `maidr` (or `maidr-data`) attribute, or in `window.maidr` with `id` equal to the SVG's `id`. A plain `<script type="application/json">` block is not read.
- **`axes` uses bare strings.** `"axes": { "x": "Day" }` is rejected; use `{ "x": { "label": "Day" } }`.
- **Unknown or misspelled `type`.** Scatter is `point`, histogram is `hist`, heatmap is `heat`. `candlestick_delta` must never be declared.
- **Empty `data` or wrong nesting.** `line`, `step`, `smooth`, and the grouped bar types need one inner array per series; `bar`, `point`, `hist`, `pie`, `box` are flat; `heat` is an object.

## Navigation works but nothing highlights on the chart: `selectors` has a shape the layer's type does not read, or resolves to the wrong count. The shapes are per type (`schema.md`): a `bar`/`hist` string must match one element per point, and an array must have exactly one selector per point -- a one-element array on a seven-point bar is declined by 4.x releases before 4.12.0, which joins it into one selector and warns in the console; `point` and `pie` read a string only (4.12.0 joins a list the same way, older 4.x releases ignore it); a multi-series `line` needs one selector per series, not one string matching every path; a segmented layer takes one string or a `selectors[series][category]` grid, not a flat array (joined with a console warning from 4.12.0, declined by earlier 4.x releases), and a grid with one unresolvable cell is declined whole. Point at the marks (`rect`, `circle`, `path`), not their `<g>` group, unless the type says otherwise (a candlestick names one `<g>` per candle), and check the count

`selectors` does not resolve to exactly one element per data point, in data order. Point at the marks (`rect`, `circle`, `path`), not their `<g>` group, and check the count with the checker (needs `beautifulsoup4`) or in the console: `document.querySelectorAll('#id rect.bar').length`.

## Values are announced in the wrong order or against the wrong bar: for a flat layer, `data` order and DOM order disagree -- emit the JSON in the order the marks are drawn. For a segmented layer (`dodged_bar`, `stacked_bar`, `stacked_normalized_bar`) reordering `data` cannot fix it, because `data` is one array per series whatever the drawing order: declare the drawing order instead with `"domMapping": { "order": "column" }` when the chart is drawn category by category (plus `"groupDirection": "forward"` when each category's first element is its first series), or name every cell in a `selectors[series][category]` grid

`data` order and DOM order disagree. Emit the JSON in the same order the marks are drawn (left to right, or the library's series order).

## Announcements stay in English for a reader whose browser or Settings name another language

maidr.js 4.8.0 and later carry only English; ko, ja, zh, es, de, fr, it, and hi are locale packs (`locale-<code>.js`) fetched from beside maidr.js. The console says which way it failed:

- `[maidr] Cannot locate the locale pack for "ko"; add <script src="…/locale-ko.js"> or set window.maidrLocaleBaseUrl.` The bundle is pasted inline and has no URL. Put `<script>window.maidrLocaleBaseUrl = window.maidrLocaleBaseUrl || "https://cdn.jsdelivr.net/npm/maidr@4.12.0/dist/";</script>` before it, and for an offline file paste the reader's pack too.
- `[maidr] Could not load the locale pack at …/locale-ko.js; announcements stay in English.` The directory maidr.js came from has no packs: a vendored `./maidr.js` (run `python scripts/fetch_locale_packs.py` on its folder), or cdnjs, which mirrors none yet (switch to jsDelivr).

Until a fetched pack arrives the first announcement is English; a page that loads the pack itself (`javascript.md`, Languages) speaks the language from the start.

## Numbers read as "1200.0" or with too many decimals

Format on the axis: `axes.y.format = { "type": "number", "decimals": 0 }` (JS), `ax.yaxis.set_major_formatter("{x:,.0f}")` (matplotlib), `scale_y_continuous(labels = scales::label_comma())` (ggplot2). Never pre-format numbers into strings inside `data`.

## py-maidr: `plt.show()` opens a normal window, not the accessible chart

`MPLBACKEND` points at a GUI backend, so maidr did not take over. Call `maidr.show(fig)` or `maidr.save_html(fig, "out.html")`, or unset `MPLBACKEND`. On matplotlib 3.8 use `matplotlib.use("module://maidr.backend")`.

## py-maidr: "Falling back to static image"

The plot type is unsupported (see `python.md`). Draw it anyway and tell the user, or restructure to a supported type if it stays faithful (a lollipop is a bar; a stacked area may be several lines).

## py-maidr: saved HTML is blank when opened offline

It was saved with `use_cdn="auto"` or `True` and the CDN is unreachable, or the `lib/` folder from `use_cdn=False` was not shipped alongside. Re-save with `use_cdn=False` and copy the `lib/` folder too, or set `MAIDR_CDN_VERSION=bundled`.

## A DotPad connects online but not from the offline page, or braille on it reads uncontracted

The page reached maidr.js but not the DotPad SDK, which maidr.js imports from jsDelivr on first connect unless the page names a copy. The console shows "DotPad SDK could not be loaded". Ship the SDK beside the page: py-maidr `maidr.download_dotpad_sdk()` then `save_html(..., use_cdn=False)`; r-maidr `maidr_download_dotpad_sdk()` then `save_html(..., use_cdn = FALSE)`; a hand-authored page `python scripts/fetch_dotpad_sdk.py` plus the two `window.MAIDR_DOTPAD_*` globals (`javascript.md`). Uncontracted (grade 1) braille on the device with the pins otherwise working means the SDK loaded but its braille engine did not: `MAIDR_DOTPAD_ASSET_BASE_URL` is unset or points at a directory without `liblouis.data`, or the copy was made from a pre-fix checkout of the vendor's repository (the file must be 13,751,594 bytes; `fetch_dotpad_sdk.py` verifies it).

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

Artifacts allow scripts from `cdnjs.cloudflare.com` and `cdn.jsdelivr.net/npm/`; local files and inline data URIs for scripts are blocked. Use a CDN URL (either host), keep the JSON inline in the attribute, and expect the AI chat to be unavailable unless the sandbox also permits the provider's API host. This is the way to embed an explorable chart directly in a claude.ai or Claude Code conversation instead of handing over a file; py-maidr output can be embedded the same way, since its loader points at jsDelivr. Other chat products that preview HTML have their own script policies: try the cdnjs tag first and fall back to a downloadable single file if the sandbox blocks it.

**ChatGPT Work shows nothing, or a picture with no maidr.**

- **The chart went to the chart widget.** Work's `genui{"charts_widget_v2": ...}` draws its own picture and binds nothing. The maidr fragment goes through `visualize` instead.
- **The reply does not name the file.** It needs `visualize{"path":"/workspace/<title>.html"}` on a line of its own, with the absolute path of a file directly in `/workspace`.
- **The file is a full page.** It has to be a fragment, with no `<!doctype>`, `<html>`, `<head>` or `<body>`, under 1 MB, loading only from jsDelivr, cdnjs, unpkg or esm.sh. `scripts/to_artifact.py --visualize` produces that, and exits non-zero when a page breaks one of those rules.
- **The chart is from Plotly or Bokeh.** Run the page through that script, which moves their library off cdn.plot.ly and cdn.bokeh.org.
- **The chart is from Altair.** Vega compiles its expressions to code at run time, which the frame may refuse. Draw it with matplotlib or seaborn there.

**ChatGPT desktop app: Site tools does not list maidr's tools.**

- **The chart is inside an iframe.** Site tools read only the page itself. py-maidr's `save_html()` output qualifies; a notebook render, a chat artifact or a `visualize` fragment does not.
- **maidr.js is older than 4.12.0**, the first release that registers the tools.
- **The tools are switched off.** Either the page carries `<meta name="maidr-webmcp" content="off">`, or the reader unchecked **Browser AI Agent Access** under maidr's Settings > General.
- **Site tools are off in the app.** Check three things:
  - Settings > Browser > Permissions > Enable site tools is on.
  - The model is GPT-5.6 Sol or GPT-6 Sol.
  - In an Enterprise workspace, the admin has approved site tools.
- **The page is not a secure context.** maidr registers nothing outside https, `localhost` or `127.0.0.1`, and local files.
- **The browser refused the registration.** The console shows `[maidr] WebMCP: could not register the tool "maidr_list_charts" (…)`. Chrome's WebMCP refuses a document served with `Origin-Agent-Cluster: ?0`, and one in a cross-origin iframe without `allow="tools"`.

## The AI chat asks for a key

Expected. MAIDR never ships with credentials; readers add their own OpenAI, Anthropic, or Gemini key under Settings (Ctrl+,), or point it at a local Ollama server (`http://localhost:11434`). Do not embed keys in the page.
