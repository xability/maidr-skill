"""Regenerate the py-maidr output the checker tests run against.

These files are real binding output, not hand-written payloads: they pin the
checker to what a reader's copy of py-maidr actually emits. Run from a py-maidr
checkout (1.25.x) so `import maidr` is the binding, naming the fixtures to
rebuild (all of them when none is named; every run mints new element ids):

    cd ../py-maidr && uv run --locked python ../maidr-skill/tests/fixtures/py-maidr/make_fixtures.py roc
"""
import os
import shutil
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import maidr  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))


def empty_panel():
    # A 1x3 grid whose middle axes is left empty: py-maidr emits `layers: []` for it.
    fig, axs = plt.subplots(1, 3)
    axs[0].bar(["A", "B", "C"], [1, 3, 2])
    axs[2].bar(["A", "B"], [1, 2])
    axs[0].set_title("Left")
    return fig


def roc():
    # A ROC curve drawn by scikit-learn's RocCurveDisplay: py-maidr emits type "roc".
    from sklearn.metrics import RocCurveDisplay

    fig, ax = plt.subplots()
    RocCurveDisplay.from_predictions(
        [0, 0, 1, 1, 0, 1, 1, 0], [0.1, 0.4, 0.35, 0.8, 0.2, 0.9, 0.6, 0.5], ax=ax, name="model"
    )
    return fig


def hexbin():
    # Hexagonal binning: py-maidr emits type "hexbin" with one array of bins per row.
    import numpy as np

    rng = np.random.default_rng(0)
    fig, ax = plt.subplots()
    ax.hexbin(rng.random(200), rng.random(200), gridsize=5)
    return fig


def contour():
    # Contour lines: py-maidr emits type "contour" with one array of points per curve.
    import numpy as np

    x, y = np.meshgrid(np.linspace(-2, 2, 20), np.linspace(-2, 2, 20))
    fig, ax = plt.subplots()
    ax.contour(x, y, x**2 + y**2, levels=3)
    return fig


def errorbar():
    # Error bars: py-maidr emits type "error_bar".
    fig, ax = plt.subplots()
    ax.errorbar([1, 2, 3], [2, 3, 1], yerr=[0.2, 0.3, 0.1])
    return fig


def gantt():
    # Axes.broken_barh, one call per lane: py-maidr emits type "gantt", data {points: [[...]]}.
    fig, ax = plt.subplots()
    ax.broken_barh([(1, 3), (6, 2)], (10, 8))
    ax.broken_barh([(2, 4)], (20, 8))
    return fig


FIXTURES = {"empty_panel": empty_panel, "roc": roc, "hexbin": hexbin, "contour": contour,
            "errorbar": errorbar, "gantt": gantt}

for name in sys.argv[1:] or FIXTURES:
    maidr.save_html(FIXTURES[name](), file=os.path.join(OUT, f"{name}.html"))
    plt.close("all")
# save_html copies the bundle into lib/ as an offline fallback; the checker does not
# need it, and 2 MB of vendored JS per fixture set is not worth keeping.
shutil.rmtree(os.path.join(OUT, "lib"), ignore_errors=True)
