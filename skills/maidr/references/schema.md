# MAIDR JSON schema (maidr 4.6.0)

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
- Each subplot: `layers` (required, non-empty), optional `selector` (CSS selector of the panel's container, useful when several panels share one SVG), optional `legend` (array of strings), optional `id`.
- Each layer: `id` (string), `type` (trace type), `data`, optional `title`, `name`, `axes`, `selectors`, `orientation` (`"vert"` default or `"horz"`), `stepDirection` (`"hv"`, `"vh"`, `"mid"`, step only).
- `axes` per layer: `{ "x": {...}, "y": {...}, "z": {...} }`. Each axis object accepts `label`, `min`, `max`, `tickStep` (the last three drive grid navigation on scatter plots), and `format`. Bare strings such as `"x": "Day"` are rejected. Default labels are `X`, `Y`, and `Level`.
- `format`: `{ "type": "currency" | "percent" | "fixed" | "number" | "date" | "scientific", "decimals": 0, "currency": "USD", "locale": "en-US" }`, or `{ "function": "return value.toFixed(1) + ' kg'" }`.
- `selectors`: a CSS selector string that matches one element per data point in data order, or an array of selectors (one per point; for grouped bars an array of arrays, one per series). Highlighting is skipped when the count does not match, so navigation still works but the visual cue is lost. Nested types (line, step, smooth) usually point at one path per series.

## Trace types

Stable (build on these): `bar`, `box`, `candlestick`, `dodged_bar`, `heat`, `hist`, `line`, `pie`, `point`, `smooth`, `stacked_bar`, `stacked_normalized_bar`, `step`, `violin_box`, `violin_kde`.

Experimental (may change in any release): `alluvial`, `area`, `boxen`, `bump`, `chord`, `choropleth`, `contour`, `diverging_bar`, `dot`, `dumbbell`, `error_bar`, `forest`, `funnel`, `gantt`, `gauge`, `hexbin`, `icicle`, `lollipop`, `manhattan`, `mosaic`, `network`, `pack`, `parallel_coordinates`, `polar_area`, `radar`, `ridgeline`, `sankey`, `stacked_area`, `stacked_normalized_area`, `sunburst`, `sunflower`, `survival`, `tree`, `treemap`, `volcano`, `waterfall`, `word_cloud`.

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

Optional per-point `label` names an ordinal level announced instead of the number (`y` stays numeric). `step` adds layer-level `"stepDirection": "hv" | "vh" | "mid"` (matplotlib `steps-post`, `steps-pre`, `steps-mid`). Selectors for lines typically match one `path` per series.

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

Readers move Left/Right across categories and Up/Down across fills; maidr adds summary and combined pseudo-layers itself. `selectors` for these is an array of arrays matching the data.

### `pie` (flat array in slice order)

```json
"axes": { "x": { "label": "Fruit" }, "y": { "label": "Units" } },
"selectors": "#chart path.slice",
"data": [ { "x": "Apples", "y": 30 }, { "x": "Bananas", "y": 50 }, { "x": "Cherries", "y": 20 } ]
```

No `percentage` field (derived) and no `orientation`. `selectors` must match exactly one element per slice. A doughnut is the same layer.

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
