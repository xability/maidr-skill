# maidr R package reference

CRAN package `maidr`, version 0.4.x. Docs: https://r.maidr.ai. Source: https://github.com/xability/r-maidr. R >= 4.0. Imports ggplot2, htmlwidgets, htmltools, gridSVG, jsonlite, shiny, xml2, R6.

## Install

```r
install.packages("maidr")            # CRAN release
pak::pak("xability/r-maidr")         # development build
packageVersion("maidr")
```

## Public API

| Call | What it does |
|---|---|
| `library(maidr)` | Registers a print method so a ggplot object opens in the accessible viewer when printed, records base R graphics calls, and exports transparent wrappers that shadow `plot`, `barplot`, `hist`, `boxplot`, `pie`, `image`, `lines`, `points`, `par`, `legend`, and friends. A startup message says so. |
| `show(plot = NULL, use_cdn = NULL, shiny = FALSE, as_widget = FALSE, ...)` | Display a ggplot (`show(p)`) or the most recent recorded base R plot (`show()`) in the RStudio Viewer, or the browser outside RStudio. |
| `save_html(plot = NULL, file = "plot.html", use_cdn = NULL, ...)` | Write a standalone HTML file. By default maidr.js is copied into a `lib/` folder beside the file; `use_cdn = TRUE` loads it from jsDelivr instead. Returns the path invisibly. |
| `maidr_on()`, `maidr_off()` | Turn interception on or off. In R Markdown and Quarto, `maidr_on()` in a setup chunk turns every plot into an accessible widget. |
| `maidr_output(output_id, width = "100%", height = "400px")` | Shiny UI placeholder. |
| `render_maidr(expr)` | Shiny server renderer; `expr` returns a ggplot or draws base R graphics. |
| `maidr_set_fallback(enabled, format, warning)`, `maidr_get_fallback()` | How unsupported plots are handled: default a static PNG with a warning; `format` is `"png"`, `"svg"`, or `"jpeg"`. |
| `run_example(example = NULL, type = c("ggplot2", "base_r"))` | Built-in demos; `run_example()` lists them. |

Nothing else exists. There is no `maidr::render()`, `maidr::maidr()`, or `maidr::accessible()`.

## Supported plots

| Plot | ggplot2 | Base R |
|---|---|---|
| Bar | `geom_bar()`, `geom_col()` | `barplot()` |
| Dodged bars | `position = "dodge"` | `barplot(beside = TRUE)` |
| Stacked bars | `position = "stack"` (`"fill"` for normalized) | `barplot(beside = FALSE)` |
| Pie | `geom_col()` + `coord_polar("y")` | `pie()` |
| Histogram | `geom_histogram()` | `hist()` |
| Scatter | `geom_point()` | `plot()` |
| Line | `geom_line()` | `plot(type = "l")`, `lines()` |
| Step | `geom_step()` | `plot(type = "s")` |
| Box | `geom_boxplot()` | `boxplot()` |
| Violin | `geom_violin()` | experimental `vioplot::vioplot()` |
| Heatmap | `geom_tile()` | `image()` |
| Contour | experimental | `contour()` |
| Smooth, density | `geom_smooth()`, `geom_density()` | `lines(density(x))` |
| Candlestick | `tidyquant::geom_candlestick()` | `quantmod::chartSeries()` (OHLC only) |

Also supported: `facet_wrap()` and `facet_grid()`, patchwork combinations, `par(mfrow = ...)` panels, and layered plots such as a histogram with a density line or bars with a line.

Experimental in ggplot2: area, stacked area, error bars, gantt, hexbin, polygon, rug, contour. Experimental in base R: `dotchart`, `mosaicplot`, `pairs`, `qqnorm`, `stars`, `stripchart`, `vioplot`, `wordcloud`, `acf`, `spectrum`, and others. Unsupported plots fall back to a static image with a warning; tell the user.

## Recipes

ggplot2:

```r
library(maidr)
library(ggplot2)
p <- ggplot(mpg, aes(class)) +
  geom_bar(fill = "steelblue") +
  labs(title = "Vehicle classes", x = "Class", y = "Count")
show(p)
save_html(p, "vehicle_classes.html")
```

Base R (draw first, then call with no plot argument):

```r
library(maidr)
barplot(table(mtcars$cyl), main = "Cars by cylinder count", xlab = "Cylinders", ylab = "Count")
show()
save_html(file = "cylinders.html")
```

R Markdown and Quarto (HTML output only; PDF and EPUB get static images):

````markdown
```{r setup, include=FALSE}
library(maidr)
maidr_on()
```
````

For reveal.js slides add `quarto add mcanouil/quarto-revealjs-a11y` (0.2.3 or newer) and `revealjs-plugins: [a11y]` so Tab reaches the chart.

Shiny:

```r
ui <- fluidPage(maidr_output("plot"))
server <- function(input, output) {
  output$plot <- render_maidr({
    ggplot(mpg, aes(displ, hwy)) + geom_point() + labs(title = "Fuel economy", x = "Displacement (L)", y = "Highway mpg")
  })
}
```

## Options

```r
options(
  maidr.auto_show = TRUE,        # master switch for interception
  maidr.ggplot2 = TRUE,          # auto-display printed ggplot objects
  maidr.base_r = TRUE,           # record base graphics calls
  maidr.startup_message = TRUE,
  maidr.fallback_enabled = TRUE, # static image for unsupported plots
  maidr.fallback_format = "png",
  maidr.fallback_warning = TRUE
)
```

There are no maidr environment variables. `RSTUDIO=1` decides Viewer versus browser.

## Offline and CDN

`show()` and `save_html()` default to the bundled maidr.js, so output works offline. `save_html(p, "f.html")` writes `lib/maidr-<version>/` beside the file (CRAN 0.4.0 ships maidr.js 3.69.0; the development build ships 4.6.0); ship both, or pass `use_cdn = TRUE` for a single file that loads the same pinned version from jsDelivr. Widgets, knitr documents, and Shiny apps detect internet access (`curl::has_internet()`, cached five minutes) and inline the bundle when offline. The package never emits cdnjs URLs; edit the script `src` in the saved file if a content-security policy requires cdnjs.

## Gotchas

1. Base R needs `show()` with no arguments after drawing. "No Base R plots detected" means nothing was recorded: draw after `library(maidr)` and check `getOption("maidr.base_r")`.
2. Attach `quantmod` or `wordcloud` before `maidr`, or call `maidr::chartSeries()`; attached later, they mask maidr's wrappers and the chart is never recorded.
3. `quantmod::chartSeries()` with volume or technical-analysis overlays falls back to a static image; pass OHLC without a Volume column or set `TA = NULL`.
4. Violin plots are stable in ggplot2 only; base R `vioplot(y ~ g)` formula calls are not read.
5. `matplot()` and `symbols()` can fail inside the SVG export and fall back with a warning.
6. `library(maidr)` masks base graphics functions and `methods::show`. Behaviour is unchanged; call `methods::show(x)` for S4 objects and `maidr_off()` to restore plain plotting.
7. ggplot2 3.x (S3) and 4.x (S7) are both supported.
8. Knitting to PDF yields static images by design; render to HTML for accessibility.
