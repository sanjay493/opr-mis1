"""
Auto-generated "SAIL achieved best ... production" highlights for Page 3.

Scoped to ALL_PLANTS (all 8 plants) and, for Finished Steel, the extra
SAIL-level "Conversion" figure — matching exactly what compute_item_row /
db.get_sail_production_actual use for the production_table actuals shown
directly above this section, so the "at X MT" figures here always agree
with the ACT column on the same page.

Only one monthly total per item is fetched from the DB; every period
(calendar month / FY quarter / FY half / full FY) is then aggregated from
that in Python, so a single query does for all of it (and Conversion only
has to be merged in once).

For each of the four headline items:
  - Monthly: a highlight only appears if `month` is the best-ever actual for
    that calendar month name across all years (e.g. best June ever). If it's
    ALSO the best of ANY month ever (any month name), the stronger "best
    ever month" headline is used instead of "best <Month>".
  - Quarter / Half / FY: only checked when `month` is that period's closing
    month (Jun/Sep/Dec/Mar for quarters, Sep/Mar for halves, Mar for FY),
    and only produces a line when this year's period total (summed only
    from periods with a complete set of months) tops every prior year's
    same period. A quarter-end month can carry both a monthly AND a
    quarterly highlight for the same item.
Items/periods without a record are simply omitted; if nothing is a record
this month, an empty list is returned.
"""
import datetime as _dt

import db
from constants import ALL_PLANTS

# (db item_name, display name)
_ITEMS = [
    ('Hot Metal', 'Hot Metal'),
    ('Total Crude Steel', 'Crude Steel'),
    ('Saleable Steel', 'Saleable Steel'),
    ('Finished Steel', 'Finished Steel'),
]

_MON_FULL = ['', 'January', 'February', 'March', 'April', 'May', 'June',
             'July', 'August', 'September', 'October', 'November', 'December']
_MON_SHORT = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

_Q_LABELS = {1: 'Q1 (Apr-Jun)', 2: 'Q2 (Jul-Sep)', 3: 'Q3 (Oct-Dec)', 4: 'Q4 (Jan-Mar)'}
_H_LABELS = {1: 'H1 (Apr-Sep)', 2: 'H2 (Oct-Mar)'}
_QNUM_OF_MONTH = {4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3, 12: 3, 1: 4, 2: 4, 3: 4}


def _mon_label(ym):
    return f"{_MON_SHORT[int(ym[5:7])]}'{ym[2:4]}"


def _fy_start_of(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    return y - 1 if m < 4 else y


def _fy_label(fy_start):
    return f"{fy_start}-{str(fy_start + 1)[2:]}"


def _fmt_mt(thousand_tonnes):
    return f"{thousand_tonnes / 1000:.3f}"


def _ph(lst):
    return ','.join('?' * len(lst))


def generate_page3_highlights(month: str) -> list:
    dt = _dt.datetime.strptime(month, "%Y-%m")
    mon_num  = dt.month
    fy_start = _fy_start_of(month)
    qnum     = _QNUM_OF_MONTH[mon_num]
    hnum     = 1 if 4 <= mon_num <= 9 else 2
    is_q_end  = mon_num in (6, 9, 12, 3)
    is_h_end  = mon_num in (9, 3)
    is_fy_end = mon_num == 3

    item_names = [n for n, _ in _ITEMS]
    display_of = dict(_ITEMS)

    conn = db.connect()
    cur = conn.cursor()
    try:
        ph_items, ph_plants = _ph(item_names), _ph(ALL_PLANTS)
        cur.execute(f"""
            SELECT item_name, report_month, SUM(month_actual) AS total
            FROM production_table
            WHERE item_name IN ({ph_items}) AND plant_name IN ({ph_plants})
            GROUP BY item_name, report_month
        """, item_names + ALL_PLANTS)
        monthly = {n: {} for n in item_names}
        for item, rm, total in cur.fetchall():
            if total is None or item not in monthly:
                continue
            monthly[item][rm] = monthly[item].get(rm, 0.0) + total

        # Finished Steel also includes the SAIL-level "Conversion" figure —
        # see db.get_sail_production_actual / _sail_conversion_actual.
        cur.execute("""
            SELECT report_month, SUM(month_actual) AS total
            FROM production_table
            WHERE item_name='Conversion' AND plant_name='SAIL'
            GROUP BY report_month
        """)
        for rm, total in cur.fetchall():
            if total is None:
                continue
            monthly['Finished Steel'][rm] = monthly['Finished Steel'].get(rm, 0.0) + total

        # ── Monthly record check ────────────────────────────────────────────
        month_blocks = {}  # headline -> list of bullet lines
        for item in item_names:
            rows = [{'period': _mon_label(rm), 'month': rm, 'total': t}
                    for rm, t in monthly[item].items()]
            this_row = next((r for r in rows if r['month'] == month), None)
            if this_row is None:
                continue
            same_name = sorted((r for r in rows if int(r['month'][5:7]) == mon_num),
                                key=lambda r: r['total'], reverse=True)
            if not (same_name and same_name[0]['month'] == month):
                continue
            global_rank = sorted(rows, key=lambda r: r['total'], reverse=True)
            is_global_best = global_rank and global_rank[0]['month'] == month
            prev = (global_rank[1] if is_global_best and len(global_rank) > 1
                    else (same_name[1] if len(same_name) > 1 else None))
            if prev is None:
                continue
            headline = 'best ever month' if is_global_best else f'best {_MON_FULL[mon_num]}'
            month_blocks.setdefault(headline, []).append(
                f"{display_of[item]} production at {_fmt_mt(this_row['total'])} MT "
                f"(Previous best {_fmt_mt(prev['total'])} MT in {prev['period']})"
            )

        blocks = []  # list of (headline, [lines])
        for headline, lines in month_blocks.items():
            blocks.append((f"SAIL achieved {headline} production for following", lines))

        def period_totals(n_months_required, key_fn):
            """Groups monthly[item] into buckets keyed by key_fn(report_month)
            (None = excluded), keeping only buckets with a complete set of
            n_months_required distinct months."""
            out = {}
            for item in item_names:
                buckets = {}
                for rm, total in monthly[item].items():
                    key = key_fn(rm)
                    if key is None:
                        continue
                    b = buckets.setdefault(key, {'total': 0.0, 'months': set()})
                    b['total'] += total
                    b['months'].add(rm)
                out[item] = {k: v['total'] for k, v in buckets.items()
                              if len(v['months']) == n_months_required}
            return out

        def period_block(data, current_key, label, prev_label_of):
            lines = []
            for item in item_names:
                rows = sorted(({'key': k, 'total': t} for k, t in data[item].items()),
                               key=lambda r: r['total'], reverse=True)
                if not rows or rows[0]['key'] != current_key or len(rows) < 2:
                    continue
                lines.append(
                    f"{display_of[item]} production at {_fmt_mt(rows[0]['total'])} MT "
                    f"(Previous best {_fmt_mt(rows[1]['total'])} MT in {prev_label_of(rows[1]['key'])})"
                )
            if lines:
                blocks.append((f"SAIL achieved best {label} production for following", lines))

        if is_q_end:
            def qkey(rm):
                m = int(rm[5:7])
                return _fy_start_of(rm) if _QNUM_OF_MONTH[m] == qnum else None
            period_block(period_totals(3, qkey), fy_start,
                         f"{_Q_LABELS[qnum]} {_fy_label(fy_start)}",
                         lambda fy: f"{_Q_LABELS[qnum]} {_fy_label(fy)}")

        if is_h_end:
            def hkey(rm):
                m = int(rm[5:7])
                this_hnum = 1 if 4 <= m <= 9 else 2
                return _fy_start_of(rm) if this_hnum == hnum else None
            period_block(period_totals(6, hkey), fy_start,
                         f"{_H_LABELS[hnum]} {_fy_label(fy_start)}",
                         lambda fy: f"{_H_LABELS[hnum]} {_fy_label(fy)}")

        if is_fy_end:
            period_block(period_totals(12, _fy_start_of), fy_start,
                         _fy_label(fy_start),
                         lambda fy: _fy_label(fy))

        lines = []
        for headline, block_lines in blocks:
            lines.append(f"{headline}:-")
            lines.extend(block_lines)
        return lines
    finally:
        conn.close()
