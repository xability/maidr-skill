"""Regenerate the py-maidr output the checker tests run against.

These files are real binding output, not hand-written payloads: they pin the
checker to what a reader's copy of py-maidr actually emits. Run from a py-maidr
checkout (1.25.x) so `import maidr` is the binding:

    cd ../py-maidr && uv run --locked python ../maidr-skill/tests/fixtures/py-maidr/make_fixtures.py
"""
import os
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import maidr  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))


def save(fig, name: str) -> None:
    maidr.save_html(fig, file=os.path.join(OUT, name))
    plt.close("all")
    # save_html copies the bundle into lib/ as an offline fallback; the checker does not
    # need it, and 2 MB of vendored JS per fixture set is not worth keeping.
    shutil.rmtree(os.path.join(OUT, "lib"), ignore_errors=True)


# A 1x3 grid whose middle axes is left empty: py-maidr emits `layers: []` for it.
fig, axs = plt.subplots(1, 3)
axs[0].bar(["A", "B", "C"], [1, 3, 2])
axs[2].bar(["A", "B"], [1, 2])
axs[0].set_title("Left")
save(fig, "empty_panel.html")
