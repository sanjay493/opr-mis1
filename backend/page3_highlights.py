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

Every item/period combination that's a record is scored by how prestigious
the record is — annual best-ever ranks highest, then an all-time monthly
record (any month), then half-yearly, then quarterly, then merely "best for
this calendar month name" (weakest, since it doesn't have to beat other
months) — and only the top MAX_HIGHLIGHTS candidates are kept, so the
section never runs longer than that regardless of how many items/periods
happen to be records this month. Quarter/half/FY are only even checked when
`month` is that period's closing month (Jun/Sep/Dec/Mar for quarters,
Sep/Mar for halves, Mar for FY).
"""
import datetime as _dt

import db
from constants import ALL_PLANTS

MAX_HIGHLIGHTS = 2

# Lower = more prestigious record, wins a spot over a higher-numbered tier
# when there are more candidates than MAX_HIGHLIGHTS.
_TIER_ANNUAL     = 1
_TIER_MONTH_EVER = 2
_TIER_HALF       = 3
_TIER_QUARTER    = 4
_TIER_MONTH_SAME = 5

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

        # candidates: list of {tier, headline, line}, one per item/period record.
        candidates = []

        # ── Monthly record check ────────────────────────────────────────────
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
            if is_global_best:
                tier, headline = _TIER_MONTH_EVER, "SAIL achieved best ever month production for following"
            else:
                tier, headline = _TIER_MONTH_SAME, f"SAIL achieved best {_MON_FULL[mon_num]} production for following"
            candidates.append({
                'tier': tier, 'headline': headline,
                'line': f"{display_of[item]} production at {_fmt_mt(this_row['total'])} MT "
                        f"(Previous best {_fmt_mt(prev['total'])} MT in {prev['period']})",
            })

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

        def period_candidates(data, current_key, tier, headline, prev_label_of):
            for item in item_names:
                rows = sorted(({'key': k, 'total': t} for k, t in data[item].items()),
                               key=lambda r: r['total'], reverse=True)
                if not rows or rows[0]['key'] != current_key or len(rows) < 2:
                    continue
                candidates.append({
                    'tier': tier, 'headline': headline,
                    'line': f"{display_of[item]} production at {_fmt_mt(rows[0]['total'])} MT "
                            f"(Previous best {_fmt_mt(rows[1]['total'])} MT in {prev_label_of(rows[1]['key'])})",
                })

        if is_q_end:
            def qkey(rm):
                m = int(rm[5:7])
                return _fy_start_of(rm) if _QNUM_OF_MONTH[m] == qnum else None
            period_candidates(
                period_totals(3, qkey), fy_start, _TIER_QUARTER,
                f"SAIL achieved best {_Q_LABELS[qnum]} {_fy_label(fy_start)} production for following",
                lambda fy: f"{_Q_LABELS[qnum]} {_fy_label(fy)}")

        if is_h_end:
            def hkey(rm):
                m = int(rm[5:7])
                this_hnum = 1 if 4 <= m <= 9 else 2
                return _fy_start_of(rm) if this_hnum == hnum else None
            period_candidates(
                period_totals(6, hkey), fy_start, _TIER_HALF,
                f"SAIL achieved best {_H_LABELS[hnum]} {_fy_label(fy_start)} production for following",
                lambda fy: f"{_H_LABELS[hnum]} {_fy_label(fy)}")

        if is_fy_end:
            period_candidates(
                period_totals(12, _fy_start_of), fy_start, _TIER_ANNUAL,
                f"SAIL achieved best {_fy_label(fy_start)} production for following",
                lambda fy: _fy_label(fy))

        # Stable sort — within a tier, candidates keep the item order they
        # were generated in (Hot Metal, Crude Steel, Saleable Steel, Finished
        # Steel), so ties are broken deterministically.
        candidates.sort(key=lambda c: c['tier'])
        selected = candidates[:MAX_HIGHLIGHTS]

        lines = []
        last_headline = None
        for c in selected:
            if c['headline'] != last_headline:
                lines.append(f"{c['headline']}:-")
                last_headline = c['headline']
            lines.append(c['line'])
        return lines
    finally:
        conn.close()
