# MAIDR JSON schema (maidr 4.10.0)

Authoritative source: https://maidr.ai/docs/SCHEMA.html (`src/type/grammar.ts` in the maidr repository). This page condenses what a hand-authored chart needs. py-maidr and r-maidr generate this JSON for you; you only write it for hand-drawn SVGs or when an adapter does not exist.

## Skeleton

```json
{
  "id": "same-as-svg-id",
  "title": "Figure title",
  "subtitle": "optional",
  "caption": "optional",
  "axes": { "x": { "label": "shared X label" }, "y": { "label": "shared Y label" } },
  "subplots": [
    [ { "layers": [ { "id": "L0", "type": "bar", "title": "...", "axes": {...}, "selectors": "...", "data": [...] } ] } ]
  ]
}
```

- `id` (required) and `subplots` (required) are the only mandatory top-level keys. `subplots` is a 2-D grid: outer array = rows, inner array = columns. A single chart is `[[ { "layers": [...] } ]]`.
- Top-level `axes` is optional and only `label` is honored there (shared labels for a facet grid). `live` and `maxWidth` are for streaming charts.
- Each subplot: `layers` (required; `[]` for a grid position no chart occupies, which readers can still move onto), optional `selector` (CSS selector of the panel's container, useful when several panels share one SVG), optional `legend` (array of strings), optional `id`.
- Each layer: `id` (string), `type` (trace type), `data`, optional `title`, `name`, `axes`, `selectors`, `orientation` (`"vert"` default or `"horz"`), `stepDirection` (`"hv"`, `"vh"`, `"mid"`, step only).
- `axes` per layer: `{ "x": {...}, "y": {...}, "z": {...} }`. Each axis object accepts `label`, `min`, `max`, `tickStep` (the last three drive grid navigation on scatter plots), and `format`. Bare strings such as `"x": "Day"` are rejected. Default labels are `X`, `Y`, and `Level`.
- `format`: `{ "type": "currency" | "percent" | "fixed" | "number" | "date" | "scientific", "decimals": 0, "currency": "USD", "locale": "en-US" }`, or `{ "function": "return value.toFixed(1) + ' kg'" }`.
- `selectors`: which drawn elements the layer highlights. The shape is a contract with maidr.js 4.x, and it is read **per type** -- a shape the type does not read loses the highlight silently, while navigation and speech keep working, which is the failure nothing announces:
  - `bar`, `hist`, `dot`, `lollipop`, `funnel`: a **string** matched with `querySelectorAll` and paired with the points in document order, or an array with **exactly one selector per point** (single-row data only). A one-element array on a multi-point layer is not "a string in a list": it is one selector for N points, and the layer is declined.
  - `point`, `pie` (and `sunflower`, `volcano`, `manhattan`, read as scatters): a **string only**. An array of any length is ignored (`Svg.isUsableSelector` accepts strings), so a per-point list must be joined with `", "` into one selector list.
  - `line`, `step`, `smooth`, `area`, `stacked_area`, `stacked_normalized_area`, `survival`, `bump`, `radar`, `polar_area`, `parallel_coordinates`, `roc`, `contour`: an array with **one selector per series**, in series order; a bare string counts as one series, so a string matching N paths for N series is declined. Each entry names the series' `<path>`/`<polyline>`/`<polygon>` (its vertices are the points) or one marker per point; a `contour` entry may name several paths, which are read as one level.
  - `dodged_bar`, `stacked_bar`, `stacked_normalized_bar`, `mosaic`, `diverging_bar`: a **string** matching every segment, paired series by series by default -- see `domMapping` under the segmented types below when the chart is drawn category by category -- or a grid `selectors[series][category]` with one selector per cell that `querySelector` resolves to that one segment, `null` for a cell that was never drawn. A flat array is declined.
  - `heat`: a string matching every cell (row-major, top row first), or a grid `selectors[row][column]` with `null` for a cell that was not drawn.
  - `boxen`, `ridgeline`, `dumbbell`, `error_bar`, `forest`, `gantt`, `hexbin`, `waterfall`, `word_cloud`, `gauge`, `alluvial`, `chord`, `sankey`, `network`, `choropleth`, `treemap`, `sunburst`, `icicle`, `tree`, `pack`: a string, or a list of strings whose matches are **concatenated**; the total must be exactly one element per item (per ridge for `ridgeline`, per point otherwise) or the highlight is declined. `gauge` uses the first match.
  - `box`, `violin_box`: one selector object per box (see the box section); `candlestick`: a string, a one-element array or a selector object.
  - Fewer matches than points is not skipped for a bar: the elements are assigned to the non-zero points in document order, so a selector that under-matches by one shifts every highlight after it onto the wrong bar. More matches than points is declined.

## Trace types

Stable (build on these): `bar`, `box`, `candlestick`, `dodged_bar`, `heat`, `hist`, `line`, `pie`, `point`, `smooth`, `stacked_bar`, `stacked_normalized_bar`, `step`, `violin_box`, `violin_kde`.

Experimental (may change in any release): `alluvial`, `area`, `boxen`, `bump`, `chord`, `choropleth`, `contour`, `diverging_bar`, `dot`, `dumbbell`, `error_bar`, `forest`, `funnel`, `gantt`, `gauge`, `hexbin`, `icicle`, `lollipop`, `manhattan`, `mosaic`, `network`, `pack`, `parallel_coordinates`, `polar_area`, `radar`, `ridgeline`, `roc`, `rug`, `sankey`, `stacked_area`, `stacked_normalized_area`, `sunburst`, `sunflower`, `survival`, `tree`, `treemap`, `volcano`, `waterfall`, `word_cloud`.

Never declare `candlestick_delta`; it is derived at runtime from a `candlestick` layer and a page that declares it fails to bind. Scatter is `point` (not `scatter`), histogram is `hist`, heatmap is `heat`.

## Data shapes

### `bar` (flat array, one object per bar)

```json
"data": [ { "x": "A", "y": 5.98 }, { "x": "B", "y": 9.31 } ]
```

Horizontal bars: add `"orientation": "horz"` on the layer and keep `x` as the category, `y` as the value.

### `line` and `step` (nested: one inner array per series)

```json
"data": [
  [ { "x": 1, "y": 2 }, { "x": 2, "y": 4 } ],
  [ { "x": 1, "y": 1 }, { "x": 2, "y": 3 } ]
]
```

Optional per-point `label` names an ordinal level announced instead of the number (`y` stays numeric). `step` adds layer-level `"stepDirection": "hv" | "vh" | "mid"` (matplotlib `steps-post`, `steps-pre`, `steps-mid`).

`selectors` for a line is an array with one entry per series, in series order, each matching that series' one `<path>` (or `<polyline>`); a bare string is read as a single series and is declined when it matches more than one path. maidr highlights a line by walking that path's vertices, so draw each series with straight `M`/`L` segments and exactly one vertex per data point in data order; a smoothed curve (`C`, `Q`) or an over-sampled path makes the highlight drift away from the announced point. Draw markers as separate elements if you want them.

### `point` (scatter, flat array, numeric coordinates)

```json
"data": [ { "x": 1.0, "y": 2.0 }, { "x": 1.5, "y": 2.7 } ]
```

Category axis (strip or swarm plots): keep the coordinate numeric and add `xLabel` or `yLabel`: `{ "x": 0, "xLabel": "control", "y": 1.4 }`. Optional `axes.x.min`/`max`/`tickStep` enable grid navigation.

### `hist` (flat array, one object per bin)

```json
"data": [ { "x": 1.15, "y": 4, "xMin": 1.0, "xMax": 1.3, "yMin": 0, "yMax": 4 } ]
```

### `heat` (an object, not an array)

```json
"data": { "points": [[60.5, 86.7], [18.6, 67.6]], "x": ["CoLA", "MNLI"], "y": ["BERT", "BiLSTM"] }
```

`points[row][col]`; `y` labels rows, `x` labels columns. Name the value with `"axes": { "z": { "label": "Score" } }`.

### `box` and `violin_box` (flat array, one object per box)

```json
"data": [ { "fill": "Group 1", "lowerOutliers": [40, 50], "min": 71.4, "q1": 92.6, "q2": 99.6, "q3": 107.7, "max": 118.2, "upperOutliers": [150] } ]
```

Layer-level `"orientation": "vert"` or `"horz"`. Empty outlier arrays are fine.

### `dodged_bar`, `stacked_bar`, `stacked_normalized_bar` (nested: one inner array per series/fill)

```json
"data": [
  [ { "x": "Adelie", "fill": "Below", "y": 70 }, { "x": "Gentoo", "fill": "Below", "y": 40 } ],
  [ { "x": "Adelie", "fill": "Above", "y": 90 }, { "x": "Gentoo", "fill": "Above", "y": 60 } ]
]
```

Readers move Left/Right across categories and Up/Down across fills; maidr adds summary and combined pseudo-layers itself.

`selectors` for these is either one string matching every segment, or a grid the same shape as `data` -- `selectors[series][category]`, one selector per cell, each resolving with `querySelector` to that one segment, `null` where the chart drew nothing for the cell. A flat array of selectors is declined.

With the string form maidr pairs the matched segments with the cells **series by series**: all of series 0's segments in document order, then series 1's, and so on. A chart drawn **category by category** -- every hand-written stacking loop, ggplot2, R's `barplot()` -- has to say so, or every segment after the first is outlined for another cell's value:

```json
"domMapping": { "order": "column", "groupDirection": "forward" }
```

`order: "column"` pairs the segments one category at a time; `groupDirection` says which series a category's first element is: `"forward"` for series 0 first (bars drawn bottom-up in the order the series are listed), `"reverse"` (the default) when the last series is drawn first, as a stack drawn top-down is. Chart-library adapters set this themselves; hand-authored JSON has to.

### `pie` (flat array in slice order)

```json
"axes": { "x": { "label": "Fruit" }, "y": { "label": "Units" } },
"selectors": "#chart path.slice",
"data": [ { "x": "Apples", "y": 30 }, { "x": "Bananas", "y": 50 }, { "x": "Cherries", "y": 20 } ]
```

No `percentage` field (derived) and no `orientation`. `selectors` is a string, never an array, and must match exactly one element per slice. A doughnut is the same layer.

### `candlestick` (flat array)

```json
"data": [ { "value": "2023-02-16", "open": 151.61, "high": 151.82, "low": 151.59, "close": 151.80, "volume": 0 } ]
```

### `smooth` (nested like line; `svg_x`/`svg_y` optional pixel coordinates for highlighting)

```json
"data": [ [ { "x": 4.7, "y": 3.12, "svg_x": 404.5, "svg_y": 390.0 } ] ]
```

### `violin_kde` (nested: one array per violin; points come in left/right pairs per y level)

```json
"data": [ [ { "x": "Ideal", "y": -501.7, "svg_x": 100.4, "svg_y": 281.8, "width": 0.044 }, ... ] ]
```

A violin plot is two layers in one subplot: `violin_box` first, then `violin_kde`. Spec: https://maidr.ai/docs/VIOLIN_PLOT_SPEC.html.

### Experimental types: the data container

Only the container is listed here, because it is what `check_maidr_html.py` checks and what a wrong guess breaks; point fields beyond these may change between releases (see maidr's `docs/SCHEMA.md` for the release in use).

| Container | Types |
|---|---|
| nested, one inner array per series or row, points `{x, y}` | `area`, `stacked_area`, `stacked_normalized_area`, `bump`, `radar`, `polar_area`, `parallel_coordinates`, `roc`, `contour`, `survival`, `ridgeline`, `hexbin` (points also carry `count`), `mosaic`, `diverging_bar` (points carry `z` or `fill`, as the segmented bars do) |
| flat for one group, or nested with one array per group; points need `x` | `error_bar` (`y` optional), `forest` (`y` required) |
| one object | `gauge` `{value, min, max}`, `dumbbell` `{points: [{x, start, end}, ...]}`, `gantt` `{points: [[{x, start, end}, ...], ...]}` with one inner array per lane |
| flat array of point objects | every other type, e.g. `dot`, `lollipop`, `funnel`, `boxen`, `waterfall`, `rug` (`x`, or `y` when `orientation` is `"horz"`) |

## Multiple layers (overlaid charts, one panel)

```json
"subplots": [[ { "layers": [
  { "id": "bars", "type": "bar", "selectors": "#chart rect.bar", "axes": {...}, "data": [ {"x": "Q1", "y": 120}, ... ] },
  { "id": "trend", "type": "line", "selectors": "#chart path.trend", "axes": {...}, "data": [ [ {"x": "Q1", "y": 100}, ... ] ] }
] } ]]
```

Readers switch layers with PageUp/PageDown; give each layer a `name` or `title` so the switch is announced meaningfully.

## Multiple panels (facets, subplots)

```json
"subplots": [
  [ { "id": "p00", "selector": "#chart g.panel-0", "layers": [ ... ] }, { "id": "p01", "selector": "#chart g.panel-1", "layers": [ ... ] } ],
  [ { "id": "p10", "selector": "#chart g.panel-2", "layers": [ ... ] }, { "id": "p11", "selector": "#chart g.panel-3", "layers": [ ... ] } ]
]
```

The grid shape is the visual layout (2 rows x 2 columns above). Readers start in a figure overview where the arrow keys move between panels, Space announces the current panel, Enter opens it, and Escape returns to the overview. Put shared axis labels in the top-level `axes` and a figure `title`.

## Number and date formatting

Prefer formatting on the axis (`"format": { "type": "currency", "currency": "USD", "decimals": 0 }`) over pre-formatted strings in `data`; values must stay numeric so sonification and braille have a scale to work with.
