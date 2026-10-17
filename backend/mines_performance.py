"""
Mines Production Performance -- a standalone report laid out like the
monthly report's pages 5-6 (Plant Wise Item Wise Production), with mines in
place of plants. Not part of the monthly PDF yet (some coal/flux figures are
only kept at SAIL level today). See
docs/superpowers/specs/2026-10-17-mines-production-performance-design.md.

generate(month) -> {"labels", "pct_idx", "blocks"}: one block per mine, per
group (JGoM/OGoM/CGoM) and for SAIL. Every row carries 11 unrounded values:
    0 FY Plan | 1 Plan  2 Actual  3 %Ful  4 CPLY Act.  5 %Gr    (month)
              | 6 Plan  7 Actual  8 %Ful  9 CPLY Act. 10 %Gr    (Apr-to-month)
Every total is a live sum of its parts -- nothing stored is a total.

A "series" is {report_month: (actual, plan)}; rows are built by combining
series and then deriving the 11 values, so totals' percentages come from
the summed quantities, never from averaging percentages.
"""
import db

PCT_IDX = (3, 5, 8, 10)

_MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def periods(month: str) -> dict:
    y, m = int(month[:4]), int(month[5:7])
    fy = y if m >= 4 else y - 1
    fy_months = [f"{fy}-{k:02d}" for k in range(4, 13)] + [f"{fy + 1}-{k:02d}" for k in range(1, 4)]
    ytd = [mo for mo in fy_months if mo <= month]

    def prev(mo):
        return f"{int(mo[:4]) - 1}{mo[4:]}"

    return {"fy": fy_months, "month": month, "cply": prev(month),
            "ytd": ytd, "cply_ytd": [prev(mo) for mo in ytd]}


def labels(month: str) -> dict:
    y, m = int(month[:4]), int(month[5:7])
    fy = y if m >= 4 else y - 1
    sy, py = f"{y % 100:02d}", f"{(y - 1) % 100:02d}"
    return {
        "title": f"Mines Production Performance :{_MON[m]}'{sy} and Apr-{_MON[m]}'{sy}",
        "fy": f"{fy % 100:02d}-{(fy + 1) % 100:02d}",
        "month": f"{_MON[m]}'{sy}",
        "cply": f"{_MON[m]}'{py}",
        "ytd": f"Apr-{_MON[m]}'{sy}",
        "ytd_cply": f"Apr-{_MON[m]}'{py}",
    }


def _sum(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def combine(series_list) -> dict:
    out = {}
    for s in series_list:
        for mo, (a, p) in s.items():
            oa, op = out.get(mo, (None, None))
            out[mo] = (_sum([oa, a]), _sum([op, p]))
    return out


def _ratio(n, d):
    # n * 100 / d (not n / d * 100): 90 / 200 * 100 is 45.00000000000001
    return None if n is None or not d else n * 100 / d


def _growth(a, c):
    return None if a is None or not c else (a - c) * 100 / c


def values(series: dict, P: dict) -> list:
    def act(mo):
        return series.get(mo, (None, None))[0]

    def plan(mo):
        return series.get(mo, (None, None))[1]

    m_plan, m_act, m_cply = plan(P["month"]), act(P["month"]), act(P["cply"])
    y_plan = _sum(plan(mo) for mo in P["ytd"])
    y_act = _sum(act(mo) for mo in P["ytd"])
    y_cply = _sum(act(mo) for mo in P["cply_ytd"])
    return [_sum(plan(mo) for mo in P["fy"]),
            m_plan, m_act, _ratio(m_act, m_plan), m_cply, _growth(m_act, m_cply),
            y_plan, y_act, _ratio(y_act, y_plan), y_cply, _growth(y_act, y_cply)]
