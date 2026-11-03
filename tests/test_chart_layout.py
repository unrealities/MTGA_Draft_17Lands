"""
tests/test_chart_layout.py
Canvas charts must keep every label inside the canvas and clear of each other
when Windows display scaling enlarges point-sized fonts (issue #238).
"""

import itertools
import tkinter

import pytest

from src.ui.components import ManaCurvePlot, SignalMeter, TypePieChart
from src.ui.styles import Theme

# Tk's pixels-per-point at 100% / 200% Windows display scaling.
SCALE_100 = 96 / 72
SCALE_200 = 192 / 72


@pytest.fixture
def root():
    root = tkinter.Tk()
    Theme.apply(root, "Dark")
    yield root
    root.destroy()


def _host(root, tk_scaling, width):
    root.tk.call("tk", "scaling", tk_scaling)
    host = tkinter.Toplevel(root)
    host.chart_width = width
    return host


def _show(widget):
    """Pack the chart into a window of fixed width and its requested height."""
    host = widget.winfo_toplevel()
    widget.pack(fill="x")
    host.update_idletasks()
    host.geometry(f"{host.chart_width}x{host.winfo_reqheight()}+0+0")
    host.update()


def _bboxes(canvas, kind=None):
    return [
        canvas.bbox(i)
        for i in canvas.find_all()
        if kind is None or canvas.type(i) == kind
    ]


def _assert_inside(canvas):
    w, h = canvas.winfo_width(), canvas.winfo_height()
    for x1, y1, x2, y2 in _bboxes(canvas):
        assert x1 >= -1 and y1 >= -1, (x1, y1, w, h)
        assert x2 <= w + 1 and y2 <= h + 1, (x2, y2, w, h)


def _overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


@pytest.mark.parametrize("tk_scaling", [SCALE_100, SCALE_200])
def test_mana_curve_labels_fit(root, tk_scaling):
    host = _host(root, tk_scaling, 600)
    curve = ManaCurvePlot(host, ideal_distribution=[0, 2, 6, 5, 3, 1, 0])
    curve.update_curve([0, 2, 16, 13, 7, 1, 1])
    _show(curve)

    _assert_inside(curve.canvas)
    texts = _bboxes(curve.canvas, "text")
    assert len(texts) == 7 + 6  # axis labels + non-zero counts
    for a, b in itertools.combinations(texts, 2):
        assert not _overlaps(a, b), (a, b)


def test_mana_curve_grows_with_display_scaling(root):
    # Aqua Tk draws point-sized fonts at a fixed 72 DPI and ignores tk scaling.
    if root.tk.call("tk", "windowingsystem") == "aqua":
        pytest.skip("tk scaling does not enlarge fonts on macOS")
    host = _host(root, SCALE_100, 600)
    small = ManaCurvePlot(host, ideal_distribution=[])
    root.tk.call("tk", "scaling", SCALE_200)
    large = ManaCurvePlot(host, ideal_distribution=[])
    assert int(large.canvas.cget("height")) > int(small.canvas.cget("height"))


def test_mana_curve_draws_within_squeezed_height(root):
    """A parent that grants less than the requested height must not clip labels."""
    host = _host(root, SCALE_200, 600)
    curve = ManaCurvePlot(host, ideal_distribution=[])
    curve.pack(fill="both", expand=True)
    host.geometry(f"600x{int(curve.canvas.cget('height')) * 3 // 4}+0+0")
    host.update()
    curve.update_curve([0, 2, 16, 13, 7, 1, 1])
    _assert_inside(curve.canvas)


@pytest.mark.parametrize("tk_scaling", [SCALE_100, SCALE_200])
def test_type_pie_legend_clear_of_pie(root, tk_scaling):
    host = _host(root, tk_scaling, 700)
    pie = TypePieChart(host)
    pie.update_counts(
        {
            "Creature": 24,
            "Planeswalker": 1,
            "Instant": 7,
            "Sorcery": 15,
            "Enchantment": 1,
            "Artifact": 1,
            "Land": 1,
        }
    )
    _show(pie)

    canvas = pie.canvas
    _assert_inside(canvas)
    arcs = [canvas.bbox(i) for i in canvas.find_all() if canvas.type(i) == "arc"]
    pie_left = min(b[0] for b in arcs)
    legend = [
        canvas.bbox(i)
        for i in canvas.find_all()
        if canvas.type(i) == "text" and ":" in canvas.itemcget(i, "text")
    ]
    assert len(legend) == 7
    for box in legend:
        assert box[2] <= pie_left, (box, pie_left)
    for a, b in itertools.combinations(legend, 2):
        assert not _overlaps(a, b), (a, b)


def test_type_pie_fits_narrow_sidebar(root):
    """The dashboard sidebar is narrow; the pie shrinks instead of the legend clipping."""
    host = _host(root, SCALE_200, 330)
    pie = TypePieChart(host)
    pie.update_counts({"Creature": 24, "Enchantment": 1, "Planeswalker": 2})
    _show(pie)
    _assert_inside(pie.canvas)


@pytest.mark.parametrize("tk_scaling", [SCALE_100, SCALE_200])
@pytest.mark.parametrize("spare", [0, 30, 80])
def test_type_pie_never_overflows_beside_wide_legend(root, tk_scaling, spare):
    """Widths are taken from the measured legend, so this holds whatever font
    the OS substitutes (CI's Linux runner lacks the Ubuntu font)."""
    from src.ui.components import measure_text

    host = _host(root, tk_scaling, 100)
    pie = TypePieChart(host)
    counts = {"Creature": 24, "Enchantment": 1, "Planeswalker": 2}
    legend_w = pie.dot_w + max(
        measure_text(pie, pie.label_font, f"{k}: {v}")[0] for k, v in counts.items()
    )
    host.chart_width = legend_w + 2 * pie.pad + spare
    pie.update_counts(counts)
    _show(pie)
    _assert_inside(pie.canvas)


@pytest.mark.parametrize("tk_scaling", [SCALE_100, SCALE_200])
def test_signal_meter_labels_fit(root, tk_scaling):
    host = _host(root, tk_scaling, 300)
    meter = SignalMeter(host)
    meter.update_values({"W": 10.0, "U": 25.0, "B": 5.0, "R": 1.0, "G": 0.0})
    _show(meter)
    _assert_inside(meter.canvas)
