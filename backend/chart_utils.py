"""Shared helpers for the report's server-built SVG bar charts.

Several charts compare figures that sit within a few percent of each other
(production totals across 4 FYs, % value-added share, % imported coal in
blend). From a zero baseline those bars all look the same height, so these
charts draw each series on its OWN value scale instead, and mark every
bar's base with a zig-zag "axis cut" (plus a note near the chart) so the
cut axis is never hidden. Values stay printed on every bar.
"""


def own_scale(vals: list, lo_frac: float, hi_frac: float) -> tuple:
    """(floor, span) putting the lowest of `vals` at lo_frac and the highest
    at hi_frac of the plot height: bar height = ch * (v - floor) / span.
    None values are ignored; all-equal values still get a sane scale."""
    present = [v for v in vals if v is not None]
    if not present:
        return 0.0, 1.0
    lo, hi = min(present), max(present)
    rng = max(hi - lo, abs(hi) * 0.01, 1e-6)
    span = rng / (hi_frac - lo_frac)
    return lo - lo_frac * span, span


def axis_break_svg(x0: float, x1: float, y: float, k: float = 1.0) -> str:
    """Zig-zag "axis cut" band across [x0, x1] at height y: a white gap edged
    by two thin gray zig-zags. k scales it for a chart's own viewBox units
    (1.0 suits a ~1000-unit-wide chart; smaller charts pass less)."""
    step, amp = 6.0 * k, 2.5 * k
    pts, x, up = [], x0, True
    while x <= x1 + 0.01:
        pts.append((x, y + (-amp if up else amp)))
        x += step
        up = not up

    def _line(dy, stroke, width):
        d = " ".join(f"{px:.1f},{py + dy:.1f}" for px, py in pts)
        return f'<polyline points="{d}" fill="none" stroke="{stroke}" stroke-width="{width:.2f}"/>'
    return (_line(0, "#ffffff", 5.0 * k) + _line(-2.8 * k, "#94a3b8", 0.9 * k)
            + _line(2.8 * k, "#94a3b8", 0.9 * k))
