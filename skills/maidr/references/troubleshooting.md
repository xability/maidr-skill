# Troubleshooting

Symptom first, then the usual cause and the fix. Run `python scripts/check_maidr_html.py page.html` before anything else; it catches most of these statically.

## The page loads but Tab never reaches the chart and nothing is announced

- **maidr.js did not load.** Open the browser console. A blocked CDN shows a network error on the script URL. Switch to the other CDN (`cdnjs.cloudflare.com/ajax/libs/maidr/4.16.0/maidr.min.js`; cdnjs mirrors a release some time after npm publishes it, so that URL can 404 for a while; `https://api.cdnjs.com/libraries/maidr?fields=version` names the newest version it has, but an older release there is no stand-in on a page with require.js, where the UMD releases never start, as the next bullet says), or copy `assets/maidr.js` and `assets/maidr-math.css` next to the page and load `./maidr.js`, or use the loader chain from `assets/template.html`.
- **The page has require.js and maidr.js is 4.14.0 or older.** Quarto adds require.js to Jupyter output. Up to 4.14.0 maidr.js was UMD: a `<script>` tag on such a page never starts it, and the console shows `Mismatched anonymous define() module` from the page's next `require()`. Raise the pin (`javascript.md`, Loading maidr.js).
- **The JSON does not parse.** Common causes: single quotes inside the JSON, a trailing comma, an unescaped apostrophe in a label (write `&#39;`), or the attribute wrapped in double quotes while the JSON also uses double quotes. The checker prints the character offset of the error.
- **No attachment method matched.** The JSON must sit in a `maidr` (or `maidr-data`) attribute, or in `window.maidr` with `id` equal to the SVG's `id`. A plain `<script type="application/json">` block is not read.
- **`axes` uses bare strings.** `"axes": { "x": "Day" }` is rejected; use `{ "x": { "label": "Day" } }`.
- **Unknown or misspelled `type`.** Scatter is `point`, histogram is `hist`, heatmap is `heat`. `candlestick_delta` must never be declared.
- **Empty `data` or wrong nesting.** `line`, `step`, `smooth`, and the grouped bar types need one inner array per series; `bar`, `point`, `hist`, `pie`, `box` are flat; `heat` is an object.

## Navigation works but nothing highlights on the chart: `selectors` has a shape the layer's type does not read, or resolves to the wrong count. The shapes are per type (`schema.md`): a `bar`/`hist` string must match one element per point, and an array must have exactly one selector per point -- a one-element array on a seven-point bar is one selector for seven points (maidr.js 4.10.0 and later join it into one selector list with a console warning, 4.x releases before 4.10.0 highlight nothing); `point` and `pie` read a string only (4.10.0 and later join a list the same way, 4.x releases before 4.10.0 highlight nothing); a multi-series `line` needs one selector per series, not one string matching every path; a segmented layer takes one string or a `selectors[series][category]` grid, not a flat array (4.10.0 and later join it with a console warning, 4.x releases before 4.10.0 highlight nothing), and a grid with one unresolvable cell is declined whole. Point at the marks (`rect`, `circle`, `path`), not their `<g>` group, unless the type says otherwise (a candlestick names one `<g>` per candle), and check the count

`selectors` does not resolve to exactly one element per data point, in data order. Point at the marks (`rect`, `circle`, `path`), not their `<g>` group, and check the count with the checker (needs `beautifulsoup4`) or in the console: `document.querySelectorAll('#id rect.bar').length`.

## Values are announced in the wrong order or against the wrong bar: for a flat layer, `data` order and DOM order disagree -- emit the JSON in the order the marks are drawn. For a segmented layer (`dodged_bar`, `stacked_bar`, `stacked_normalized_bar`) reordering `data` cannot fix it, because `data` is one array per series whatever the drawing order: declare the drawing order instead with `"domMapping": { "order": "column" }` when the chart is drawn category by category (plus `"groupDirection": "forward"` when each category's first element is its first series), or name every cell in a `selectors[series][category]` grid

`data` order and DOM order disagree. Emit the JSON in the same order the marks are drawn (left to right, or the library's series order).

## Navigation and text work, but every value sounds like an alert

Check the numeric axis before blaming audio permissions. With `"orientation": "horz"`, bars need numeric `x` and categorical `y`, with `axes.x` naming the quantity and `axes.y` naming the category. For example, `{ "x": 120, "y": "Q1" }` is horizontal; `{ "x": "Q1", "y": 120 }` is vertical/default. Keeping the vertical fields on a horizontal chart lets text and highlighting appear correct, but passes a nonfinite magnitude to sound and produces a multi-tone missing-value alert. Ordinary chart boundaries can use the same cue, so hearing it at interior numeric points is not proof that data sonification works. Correct the fields and labels, including every series of a segmented bar; do not label a horizontal drawing as vertical to force sound. The checker validates the orientation-dependent quantitative field.

With sound on (`S` toggles it), test several unequal non-missing values inside the bounds, not just an edge. Listen or inspect real Web Audio oscillator frequencies in the chart's execution world and confirm they reflect the data. A tool's isolated-world prototype hooks may observe nothing even while the chart plays sound. If audio is unverified, say so; a moving outline and announced values are not proof of sonification.

## Announcements stay in English for a reader whose browser or Settings name another language

maidr.js 4.8.0 and later carry only English; ko, ja, zh, es, de, fr, it, and hi are locale packs (`locale-<code>.js`) fetched from beside maidr.js. The console says which way it failed:

- `[maidr] Cannot locate the locale pack for "ko"; add <script src="…/locale-ko.js"> or set window.maidrLocaleBaseUrl.` The bundle is pasted inline and has no URL. Put `<script>window.maidrLocaleBaseUrl = window.maidrLocaleBaseUrl || "https://cdn.jsdelivr.net/npm/maidr@4.16.0/dist/";</script>` before it, and for an offline file paste the reader's pack too.
- `[maidr] Could not load the locale pack at …/locale-ko.js; announcements stay in English.` The directory maidr.js came from has no packs: a vendored `./maidr.js` (run `python scripts/fetch_locale_packs.py` on its folder), or cdnjs at 4.8.0 to 4.11.0, which have none there (cdnjs mirrors the packs for 4.12.0 and later; raise the pin or switch to jsDelivr).
- No `[maidr]` message, and the page has require.js (Quarto's Jupyter output does): packs up to 4.14.0 were UMD and never register on such a page, whether maidr.js fetched the pack or a `<script>` tag loaded it. Instead the console shows `Mismatched anonymous define() module: function(){var e={"common.missing":...` as an uncaught error: at once for a pack a `<script>` tag loaded, and from the page's next `require()` for one maidr.js fetched. Raise the pin to the current release.

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
- The page has require.js (Quarto's Jupyter output does) and the adapter is 4.14.0 or older. Up to 4.14.0 an adapter's UMD wrapper called `define()` instead of setting its global when the page had an AMD loader, so an adapter loaded by a script tag on such a page never set its global: the bind call fails with `maidrD3 is not defined` (or `maidrHighcharts`, ...) and the console shows `Mismatched anonymous define() module`. Raise the pin to the current release, for `maidr.js` too.

## Claude artifacts and other sandboxed pages

Artifacts allow scripts from `cdnjs.cloudflare.com` and `cdn.jsdelivr.net/npm/`; local files and inline data URIs for scripts are blocked. Use a CDN URL (either host), keep the JSON inline in the attribute, and expect the AI chat to be unavailable unless the sandbox also permits the provider's API host. This is the way to embed an explorable chart directly in a claude.ai or Claude Code conversation instead of handing over a file; py-maidr output can be embedded the same way, since its loader points at jsDelivr. Other chat products that preview HTML have their own script policies: try the cdnjs tag first and fall back to a downloadable single file if the sandbox blocks it.

**ChatGPT Work shows nothing, or a picture with no MAIDR.**

- **The chart went to the chart widget.** Work's `genui{"charts_widget_v2": ...}` draws its own picture and binds nothing. The MAIDR fragment goes through `visualize` instead.
- **The reply does not name the file.** It needs `visualize{"path":"/workspace/<title>.html"}` on a line of its own, with the absolute path of a file directly in `/workspace`.
- **A CDN script was used.** Work's production `visualize` CSP blocks all external CDN scripts and has `connect-src 'none'`. Do not switch CDNs or handcraft a CDN-only fragment. Always run `python scripts/to_artifact.py chart.html --visualize -o /workspace/<title>.html`; it bundles the roughly 752 KB base64 gzip of `assets/maidr.js`, restores it with modern `DecompressionStream`, and assigns it to an inline script's `textContent` inside a scoped IIFE, with no `eval`, blob, or network runtime.
- **The file is a full page or too large.** It must be a fragment with no `<!doctype>`, `<html>`, `<head>`, or `<body>`, one root element with an id, and stay below 1 MB. The converter enforces these rules.
- **The source uses Plotly, Bokeh, or Altair/Vega.** Their external runtimes cannot simply be moved to a different CDN in Work. The converter may reject them with an actionable fallback; use matplotlib, seaborn, or plain SVG rather than ship a broken fragment.
- **The image appears but MAIDR does not initialize.** Verify in the actual Work host, not only with `check_maidr_html.py`: Tab must land on MAIDR's focus target, it must become `role="application"`, and an arrow key must announce a data point. Do not instruct a reader to Tab into a static or uninitialized image.
- **The announced point has a green outline, but it is on the wrong bar or marks move/hide after resize.** A source `ResizeObserver` or resize handler redrew geometry after MAIDR initialized and selected hidden or active MAIDR clones that inherited `rect.bar`; a count such as six originals plus six hidden clones and one active clone is normal, not duplicate initialization. Do not try to fix this only by filtering clones, because MAIDR has cached their geometry. Fully materialize an SVG with explicit `width`/`height` and matching `viewBox` before initialization (the converter fills missing dimensions from a valid numeric `viewBox`), and scale only with CSS `max-width`/`height: auto`. Use matplotlib, seaborn, or a pre-materialized hand SVG; Work's converter rejects these redraw patterns. Verify every point maps to its matching original mark before and after resize, not merely that an outline moves.
- **The runtime reports that the browser is unsupported.** Work packages require the modern `DecompressionStream` API to unpack the runtime; the converter emits an accessible failure notice when it is absent. Use a current supported browser rather than substituting a CDN script.
- **Runtime messages are English, settings reset, or `?` cannot answer.** Initial Work packages use English runtime UI messages, but chart labels and data retain the user's text. Settings are session-local rather than persisted, and the CSP prevents AI-chat network access. Math layout CSS is included, but embedded math font faces are omitted to stay within the 1 MB budget.

**ChatGPT desktop app: Site tools does not list maidr's tools.**

- **The chart is inside an iframe.** Site tools read only the page itself. py-maidr's `save_html()` output qualifies; a notebook render, a chat artifact or a `visualize` fragment does not.
- **maidr.js is older than 4.11.0**, the first release that registers the tools; `maidr_list_commands` and `maidr_run_command` came in 4.12.0.
- **The tools are switched off.** Either the page carries `<meta name="maidr-webmcp" content="off">`, or the reader unchecked **Browser AI Agent Access** under maidr's Settings > General.
- **Site tools are off in the app.** Check three things:
  - Settings > Browser > Permissions > Enable site tools is on.
  - The model is GPT-5.6 Sol or GPT-6 Sol.
  - In an Enterprise workspace, the admin has approved site tools.
- **The page is not a secure context.** maidr registers nothing outside https, `localhost` or `127.0.0.1`, and local files.
- **The browser refused the registration.** The console shows `[maidr] WebMCP: could not register the tool "maidr_list_charts" (…)`. Chrome's WebMCP refuses a document served with `Origin-Agent-Cluster: ?0`, and one in a cross-origin iframe without `allow="tools"`.

## The AI chat asks for a key

Expected. MAIDR never ships with credentials; readers add their own OpenAI, Anthropic, or Gemini key under Settings (Ctrl+,), or point it at a local Ollama server (`http://localhost:11434`). Do not embed keys in the page.
