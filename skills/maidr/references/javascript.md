# maidr.js reference

npm package `maidr` 4.6.0, GPL-3.0-or-later. Site: https://maidr.ai. Schema: https://maidr.ai/docs/SCHEMA.html. Controls: https://maidr.ai/docs/CONTROLS.html. Per-library guides: `https://maidr.ai/docs/<library>.html` (plotly, d3, chartjs, highcharts, echarts, vegalite, recharts, victory, amcharts, anychart, frappe, google-charts, observable, tableau, react). Source: https://github.com/xability/maidr.

## Loading maidr.js

| Source | Tag |
|---|---|
| jsDelivr, pinned (default) | `<script src="https://cdn.jsdelivr.net/npm/maidr@4.6.0/dist/maidr.js"></script>` |
| jsDelivr, floating | `https://cdn.jsdelivr.net/npm/maidr@latest/dist/maidr.js` (changes under the reader; avoid for durable pages) |
| cdnjs, pinned only | `<script src="https://cdnjs.cloudflare.com/ajax/libs/maidr/4.6.0/maidr.min.js"></script>` |
| npm | `npm install maidr`; `import 'maidr'` for the UMD side-effect build, or `import { Maidr } from 'maidr/react'` |
| Local file | `<script src="./maidr.js"></script>` with `maidr-math.css` in the same folder (both in this skill's `assets/`) |
| Inline | Paste the contents of `assets/maidr.js` into a `<script>` block (1.5 MB) when the deliverable must be a single file. An inline bundle has no URL to find `maidr-math.css` from; if math in AI-chat replies should be styled, set `window.maidrMathStylesheetUrl = "https://cdn.jsdelivr.net/npm/maidr@4.6.0/dist/maidr-math.css"` (or a local path) in a script before it |

- No stylesheet is required; maidr styles its own UI at runtime. `maidr.css` on the CDN is an empty placeholder. `maidr-math.css` (KaTeX) is fetched from the same directory as `maidr.js` only when an AI-chat answer contains math.
- maidr runs on `DOMContentLoaded`, or immediately if the document has already loaded, so async or late loading works. A `MutationObserver` picks up `maidr` attributes and Plotly charts added later (single-page apps, notebooks).
- `assets/template.html` carries a loader that tries jsDelivr, then cdnjs, then `./maidr.js`. Copy it when the reader's network is unknown.
- Content-security policy: `script-src` needs `https://cdn.jsdelivr.net` and/or `https://cdnjs.cloudflare.com`, plus `'unsafe-inline'` if the page uses inline scripts. The AI chat also needs `connect-src` for the provider the reader picks (or `http://localhost:11434` for Ollama).
- Only the core `maidr.js` is mirrored on cdnjs. Adapter bundles (`d3.js`, `chartjs.js`, ...) come from jsDelivr or npm.

## Attaching a chart

maidr looks for charts in this order and uses the first match per element:

1. A `maidr` attribute holding the JSON, on the `<svg>` (or an element wrapping it). Preferred.
2. A `maidr-data` attribute holding the same JSON (used by adapters and by r-maidr).
3. A `window.maidr` object literal in a `<script>`. The element is found with `document.getElementById(maidr.id)`, so the ids must match, and only one chart per page is possible this way.
4. Plotly.js charts (`.js-plotly-plot`), detected with no JSON at all.

One attribute per chart. Several charts on one page means several attributes; an array value is not accepted. Put the JSON in a single-quoted attribute and escape any apostrophe inside it as `&#39;`. Keep the SVG's own `id`; maidr manages focus and ARIA itself, so do not add `tabindex`.

## Hand-authored SVG

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Revenue by quarter</title>
  <script src="https://cdn.jsdelivr.net/npm/maidr@4.6.0/dist/maidr.js"></script>
</head>
<body>
  <svg id="rev" width="480" height="300" viewBox="0 0 480 300" role="img" aria-label="Bar chart of revenue by quarter"
       maidr='{
         "id": "rev",
         "title": "Revenue by quarter",
         "subplots": [[{ "layers": [{
           "id": "rev-bars", "type": "bar",
           "axes": { "x": { "label": "Quarter" }, "y": { "label": "Revenue (USD thousands)" } },
           "selectors": "#rev rect.bar",
           "data": [ { "x": "Q1", "y": 120 }, { "x": "Q2", "y": 200 }, { "x": "Q3", "y": 150 }, { "x": "Q4", "y": 280 } ]
         }] }]]
       }'>
    <rect class="bar" x="75"  y="165.7" width="70" height="94.3"/>
    <rect class="bar" x="175" y="102.9" width="70" height="157.1"/>
    <rect class="bar" x="275" y="142.1" width="70" height="117.9"/>
    <rect class="bar" x="375" y="40"    width="70" height="220"/>
    <!-- axes, ticks, labels -->
  </svg>
</body>
</html>
```

Checklist: JSON `id` equals the SVG `id`; `axes.x`/`axes.y` are objects with `label`; `data` is in drawn order; `selectors` matches exactly one mark per data point (marks, not groups); `type` is a stable trace type. Data shapes per type and multi-panel layouts: `schema.md`. Validate with `scripts/check_maidr_html.py page.html`.

## Chart-library adapters

Adapters read the library's own data model and write `maidr-data` for you. Load `maidr.js` first unless the row says the adapter bundle is self-contained. Exact option names live in the per-library guide at `https://maidr.ai/docs/<library>.html`; fetch it before writing unfamiliar options rather than guessing.

| Library | Load | Bind |
|---|---|---|
| Plotly.js | `maidr.js` only | Automatic. Create the chart with `Plotly.newPlot(...)` as usual. |
| D3 | `maidr.js` + `dist/d3.js` (global `maidrD3`) | `maidrD3.bindD3Bar(svgEl, { selector: 'rect.bar', title: 'Daily count', axes: { x: 'Day', y: 'Count' }, x: 'day', y: 'count' })`. One binder per trace type: `bindD3Line`, `bindD3Scatter`, `bindD3Histogram`, `bindD3Pie`, `bindD3Box`, `bindD3Heatmap`, `bindD3Segmented` (stacked/dodged), `bindD3Smooth`, `bindD3Candlestick`, `bindD3Facets`, `bindD3Subplots`, and more. Sets `maidr-data` on the SVG. |
| Chart.js | `dist/chartjs.js` only (self-contained, global `maidrChartjs`) | `Chart.register(maidrChartjs.maidrPlugin)` before creating charts; every chart on the page becomes accessible, with a highlight overlay on the canvas. |
| Highcharts | `maidr.js` + `dist/highcharts.js` (`maidrHighcharts`) | `const data = maidrHighcharts.highchartsToMaidr(chart, { id: 'bar-chart' }); container.setAttribute('maidr-data', JSON.stringify(data)); maidrHighcharts.createHighchartsSync(chart);` (`highchartsGridToMaidr` for dashboards). |
| ECharts | `maidr.js` + `dist/echarts.js` (`maidrECharts`) | `maidrECharts.createMaidrFromEChart(chartInstance, ...)` after `setOption`. |
| Vega-Lite | `maidr.js` + `dist/vegalite.js` (`maidrVegaLite`) | `maidrVegaLite.embed('#vis', spec)` as a drop-in for `vegaEmbed`, or `maidrVegaLite.bindVegaLite(...)` on an existing view. |
| Google Charts | `maidr.js` + `dist/google-charts.js` (`maidrGoogleCharts`) | `maidrGoogleCharts.whenGoogleChartsReady(() => maidrGoogleCharts.createMaidrFromGoogleChart(...))`. |
| Frappe Charts | `maidr.js` + `dist/frappe.js` (`maidrFrappe`) | `maidrFrappe.createMaidrFromFrappeChart(chart, ...)`. |
| Observable Plot | `maidr.js` + `dist/observable.js` (`maidrObservable`) | `maidrObservable.initObservablePlots()` once the plots are in the DOM. Quarto: `quarto add xability/maidr` and `filters: [maidr]` handles `{ojs}` cells. |
| amCharts 5 | `dist/amcharts.js` (self-contained, `maidrAmCharts`) | `maidrAmCharts.bindAmCharts(root, { axisLabels: { x: 'Fruit', y: 'Units sold' } })` returns `{ maidr, dispose }`; multi-chart roots become subplots. |
| AnyChart | `maidr.js` + `dist/anychart.mjs` (ES module) | `import { bindAnyChart } from 'https://cdn.jsdelivr.net/npm/maidr@4.6.0/dist/anychart.mjs'; bindAnyChart(chart, { ... })` after `chart.draw()`. |
| Tableau Embedding API | `maidr.js` + `dist/tableau.js` (`maidrTableau`) | `maidrTableau.bindTableau(viz, ...)`. |
| React (any SVG) | `import { Maidr } from 'maidr/react'` | `<Maidr data={maidrJson}><svg>...</svg></Maidr>`; `data` is the same JSON as the attribute. |
| Recharts | `import { MaidrRecharts } from 'maidr/recharts'` | Wrap the chart: `<MaidrRecharts id="sales" title="Quarterly revenue" ...props><BarChart>...</BarChart></MaidrRecharts>`. |
| Victory | `import { MaidrVictory } from 'maidr/victory'` | `<MaidrVictory id="sales" title="Quarterly revenue"><VictoryChart>...</VictoryChart></MaidrVictory>`; data is read from the nested Victory components. |

Canvas libraries (Chart.js, amCharts) get a drawn highlight overlay instead of SVG highlighting; everything non-visual works the same.

## What maidr does at runtime

Once initialized, maidr wraps the chart in `<article id="maidr-article-<chart id>">` containing `<figure id="maidr-figure-<chart id>">` and a focusable `div[tabindex="0"]` with `role="img"`. Focusing that div (Tab or click) switches its role to `application` and mounts the text, braille, and settings UI inside the article; Right Arrow then announces the first point in a `role="alert"` element (for example "Quarter is Q1, Revenue (USD thousands) is 120") and highlights the matching mark. Use `document.querySelector('[id^="maidr-figure-"]')` to confirm initialization from a browser tool, and `document.querySelector('[id^="maidr-article-"] [tabindex="0"]').focus()` to drive it programmatically. If they never appear, the JSON did not parse or no attachment method matched; run `scripts/check_maidr_html.py`.

## Live and streaming charts

Set `"live": true` (and optionally `"maxWidth": N`) at the top level, then push points with `window.maidrLive.setData(...)` / `appendData(...)`; readers press **M** for monitor mode. Guide: https://maidr.ai/docs/LIVE_DATA.html.
