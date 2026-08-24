"""
Best Calendar Month — items (rows) x calendar months Jan-Dec (columns)
matrix of best/2nd-best-ever production, for SAIL (5 Plants) then SAIL (8
Plants). A print version of the /reports/records-matrix on-screen tool
(same cal_months/best_month data page_records.py already computes),
narrowed to just the two plant-group scopes and the 6-item highlight list
per direct instruction. SAIL (8 Plants) is further narrowed to just Crude
Steel/Finished Steel/Saleable Steel (see _ALL8_ITEMS) — the other 3 items
are BF-route figures ASP/SSP/VISL don't produce.
"""
import datetime as _dt

from page_records import generate_group_records, HIGHLIGHT_ITEMS, HIGHLIGHT_LABELS

_GROUPS = [('sail5', 'SAIL (5 Plants)'), ('all8', 'SAIL (8 Plants)')]

# SAIL (8 Plants) only makes sense for the 3 steel-stage items — Oven
# Pushing/Sinter/Hot Metal are 5-plant (BF route) items ASP/SSP/VISL don't
# produce, so per direct instruction the 8-plant block is narrowed to these.
_ALL8_ITEMS = {'Total Crude Steel', 'Finished Steel', 'Saleable Steel'}

_MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _month_cell(rows: list, best_month: str):
    """rows = grp['cal_months'][item][month_num] (already top-2, sorted
    desc — see page_records.py's _compute_group_records); best_month =
    grp['best_month'][item]['month'], the single all-time-best month
    across all 12 — used to flag which calendar month's #1 IS that
    all-time best (mirrors records-matrix's isAllTimeBest)."""
    if not rows:
        return None
    best, second = rows[0], rows[1] if len(rows) > 1 else None
    return {
        'best':   {'total': best['total'], 'year': best['month'][:4],
                    'is_all_time_best': best['month'] == best_month},
        'second': {'total': second['total'], 'year': second['month'][:4]} if second else None,
    }


def generate_best_calendar_month(report_month: str) -> dict:
    data = generate_group_records(HIGHLIGHT_ITEMS)
    month_label = _dt.datetime.strptime(report_month, "%Y-%m").strftime("%B %Y")

    groups = []
    for gkey, glabel in _GROUPS:
        grp = data.get(gkey, {})
        rows = []
        items = [i for i in HIGHLIGHT_ITEMS if gkey != 'all8' or i in _ALL8_ITEMS]
        for item in items:
            cal = grp.get('cal_months', {}).get(item, {})
            best_month = grp.get('best_month', {}).get(item, {}).get('month')
            months = {
                mnum: _month_cell(cal.get(mnum, []), best_month)
                for mnum in range(1, 13)
            }
            rows.append({'label': HIGHLIGHT_LABELS.get(item, item), 'key': item, 'months': months})
        groups.append({'key': gkey, 'label': glabel, 'rows': rows})

    return {
        'type': 'best_calendar_month',
        'title': 'Production Highlights — Best Calendar Month (Best & 2nd Best)',
        'month_label': month_label,
        'unit': "'000 T",
        'month_names': _MONTH_NAMES,
        'groups': groups,
    }
