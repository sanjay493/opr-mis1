"""
Best-Ever Highlights — all-time-record snapshot for SAIL (5 Plants) and
SAIL (8 Plants), across the 6 headline items (Oven Pushing, Sinter, Hot
Metal, Crude Steel, Finished Steel, Saleable Steel) and 5 period types
(Month/Quarter/Half/FY/CY). A print version of the "Best-Ever Records"
table already on the /reports/highlights on-screen tool (see that page's
`recordRows` useMemo — this module ports the same derivation to Python so
it can render server-side into the PDF), narrowed to just the two plant-
group scopes and this fixed item list per direct instruction. SAIL (8
Plants) is further narrowed to just Crude Steel/Finished Steel/Saleable
Steel (see _ALL8_ITEMS, same rule as page_best_calendar_month.py) — the
other 3 items are BF-route figures ASP/SSP/VISL don't produce.
"""
import datetime as _dt

from page_records import generate_group_records, HIGHLIGHT_ITEMS, HIGHLIGHT_LABELS

_GROUPS = [('sail5', 'SAIL (5 Plants)'), ('all8', 'SAIL (8 Plants)')]

_ALL8_ITEMS = {'Total Crude Steel', 'Finished Steel', 'Saleable Steel'}

_PERIOD_KEYS = ['month', 'quarter', 'half', 'fy', 'cy']


def _q_end(fy_start: int, qnum: int) -> str:
    if qnum == 4:
        return f"{fy_start + 1}-03"
    return f"{fy_start}-{qnum * 3 + 3:02d}"


def _top2(rows: list) -> dict:
    rows = sorted(rows, key=lambda r: r['total'] if r['total'] is not None else float('-inf'),
                  reverse=True)
    return {'best': rows[0] if rows else None, 'second': rows[1] if len(rows) > 1 else None}


def _months_ago(latest: str, end: str):
    if not latest or not end:
        return None
    ly, lm = int(latest[:4]), int(latest[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    return (ly - ey) * 12 + (lm - em)


def _is_fresh(latest: str, rec) -> bool:
    if not rec:
        return False
    ago = _months_ago(latest, rec.get('end'))
    return ago is not None and 0 <= ago <= 3


def _period_records(grp: dict, key: str, latest_month: str) -> dict:
    """Best/2nd-best for one item across all 5 period types, each entry
    {total, period, fresh} or None — mirrors the frontend's recordRows
    useMemo in frontend/src/app/reports/highlights/page.js."""
    mon_flat = [
        {'period': r['period'], 'total': r['total'], 'end': r['month']}
        for rows in grp['cal_months'].get(key, {}).values()
        for r in rows if r['total'] is not None
    ]
    q_flat = [
        {'period': f"{r['period']} {label}", 'total': r['total'],
         'end': _q_end(r['fy_start'], int(label[1]))}
        for label, rows in grp['fy_quarters'].get(key, {}).items()
        for r in rows if r['total'] is not None
    ]
    h_flat = [
        {'period': f"{label} {r['period']}", 'total': r['total'],
         'end': (f"{r['fy_start']}-09" if label.startswith('H1') else f"{r['fy_start'] + 1}-03")}
        for label, rows in grp['fy_halves'].get(key, {}).items()
        for r in rows if r['total'] is not None
    ]
    fy_rows = [
        {**r, 'end': f"{int(r['period'].split('-')[0]) + 1}-03"}
        for r in grp['top5_fy'].get(key, [])
    ]
    cy_rows = [
        {**r, 'end': f"{r['period']}-12"}
        for r in grp['top5_cy'].get(key, [])
    ]

    periods = {
        'month':   _top2(mon_flat),
        'quarter': _top2(q_flat),
        'half':    _top2(h_flat),
        'fy':      {'best': fy_rows[0] if fy_rows else None, 'second': fy_rows[1] if len(fy_rows) > 1 else None},
        'cy':      {'best': cy_rows[0] if cy_rows else None, 'second': cy_rows[1] if len(cy_rows) > 1 else None},
    }
    # Report unit is T (tonnes); production_table stores everything except
    # Oven Pushing in '000 T, so every item but Oven Pushing (already a
    # nos/day rate, not a tonnage) is scaled up ×1000 here — the one place
    # both the PDF and the web preview's numbers come from.
    scale = 1 if key == 'Oven Pushing (nos/day)' else 1000
    for pk in _PERIOD_KEYS:
        for slot in ('best', 'second'):
            rec = periods[pk][slot]
            if rec is not None:
                rec['fresh'] = _is_fresh(latest_month, rec)
                if rec['total'] is not None:
                    rec['total'] *= scale
    return periods


def generate_best_ever_highlights(report_month: str) -> dict:
    data = generate_group_records(HIGHLIGHT_ITEMS)
    latest_month = data.get('latest_month')

    month_label = _dt.datetime.strptime(report_month, "%Y-%m").strftime("%B %Y")

    groups = []
    for gkey, glabel in _GROUPS:
        grp = data.get(gkey, {})
        items = [i for i in HIGHLIGHT_ITEMS if gkey != 'all8' or i in _ALL8_ITEMS]
        rows = [
            {
                'label': HIGHLIGHT_LABELS.get(item, item),
                'key': item,
                'periods': _period_records(grp, item, latest_month),
            }
            for item in items
        ]
        groups.append({'key': gkey, 'label': glabel, 'rows': rows})

    return {
        'type': 'best_ever_highlights',
        'title': 'Production Highlights — Best-Ever Records',
        'month_label': month_label,
        'latest_month': latest_month,
        'unit_note': 'Unit: T, except Oven Pushing – Nos./day',
        'groups': groups,
    }
