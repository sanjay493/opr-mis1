"""
Production record statistics — best/2nd-best by calendar month, FY quarter,
FY half, and top-5 FY / calendar years for the major production items.
Computed for the SAIL group aggregates ('sail5', 'all8') and for every
individual plant/unit (keyed by plant code, e.g. 'BSP', 'ASP').
Used by the /api/production-records endpoint.
"""
import db
from page_production_fy_export import is_rate_item

ITEMS = ['Total Sinter', 'Hot Metal', 'Total Crude Steel',
         'Saleable Steel', 'Pig Iron', 'Finished Steel']
SAIL5 = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP']
ALL8  = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP', 'VISL']

_MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

_Q_LABELS = {1: 'Q1', 2: 'Q2', 3: 'Q3', 4: 'Q4'}
_H_LABELS = {1: 'H1', 2: 'H2'}


def _ph(lst):
    return ','.join('?' * len(lst))


def _mon_label(ym):
    m = int(ym[5:7])
    return f"{_MON[m]}'{ym[2:4]}"


def _fy_label(fy_start):
    return f"{fy_start}-{str(fy_start + 1)[2:]}"


def _fy_pos_expr():
    """report_month's position within its financial year: 0 = April … 11 = March."""
    return ("CASE WHEN CAST(SUBSTR(report_month,6,2) AS INTEGER) >= 4 "
            "THEN CAST(SUBSTR(report_month,6,2) AS INTEGER) - 4 "
            "ELSE CAST(SUBSTR(report_month,6,2) AS INTEGER) + 8 END")


def _pos_to_mon(pos: int) -> int:
    """FY position (0 = Apr) -> calendar month number (1-12)."""
    return pos + 4 if pos < 9 else pos - 8


def _fy_expr():
    return ("CASE WHEN CAST(SUBSTR(report_month,6,2) AS INTEGER)>=4 "
            "THEN CAST(SUBSTR(report_month,1,4) AS INTEGER) "
            "ELSE CAST(SUBSTR(report_month,1,4) AS INTEGER)-1 END")


def _q_expr():
    return ("CASE "
            "WHEN CAST(SUBSTR(report_month,6,2) AS INTEGER) IN (4,5,6)    THEN 1 "
            "WHEN CAST(SUBSTR(report_month,6,2) AS INTEGER) IN (7,8,9)    THEN 2 "
            "WHEN CAST(SUBSTR(report_month,6,2) AS INTEGER) IN (10,11,12) THEN 3 "
            "ELSE 4 END")


def _days_expr():
    """Days in report_month's calendar month — used to weight rate items
    (Oven Pushing (nos/day), COB#* battery counts) by days-in-month when
    combining months into a quarter/half/FY/CY, instead of summing an
    already-daily-average figure like it was tonnage."""
    return ("CASE CAST(SUBSTR(report_month,6,2) AS INTEGER) "
            "WHEN 1 THEN 31 WHEN 3 THEN 31 WHEN 5 THEN 31 WHEN 7 THEN 31 "
            "WHEN 8 THEN 31 WHEN 10 THEN 31 WHEN 12 THEN 31 "
            "WHEN 4 THEN 30 WHEN 6 THEN 30 WHEN 9 THEN 30 WHEN 11 THEN 30 "
            "ELSE CASE WHEN CAST(SUBSTR(report_month,1,4) AS INTEGER) % 4 = 0 "
            "AND (CAST(SUBSTR(report_month,1,4) AS INTEGER) % 100 != 0 "
            "OR CAST(SUBSTR(report_month,1,4) AS INTEGER) % 400 = 0) "
            "THEN 29 ELSE 28 END END")


def _period_value(item, total, wsum, wdays):
    """Plain sum for tonnage items; days-in-month-weighted average for rate
    items (nos/day, COB#*) — a quarter's Oven Pushing figure must stay a
    nos/day rate, not the sum of 3 monthly averages."""
    if is_rate_item(item) and wdays:
        return float(wsum) / float(wdays)
    return total


def _item_sort_key():
    """Process-order sort for item names; alphabetical fallback if main's
    helpers aren't importable (lazy import avoids a circular import — main
    imports this module at startup, we only need main at request time)."""
    try:
        from main import normalize_item_name, production_item_sort_key
        return lambda n: production_item_sort_key(normalize_item_name(n))
    except Exception:
        return lambda n: n


def _compute_group_records(cur, items: list, where: str, args: list) -> dict:
    """Best/2nd-best by calendar month, FY quarter, FY half, and top-5 FY /
    calendar-year, for one scope (a plant group or a single plant/unit) and
    item list — extracted out of generate_records()'s per-group loop body so
    generate_group_records() below can reuse the exact same computation for
    a caller-supplied item list (the Best-Ever Highlights / Best Calendar
    Month report pages only want 6 fixed items across the sail5/all8 group
    scopes, not generate_records()'s full per-plant sweep)."""
    grp = {
        'items':        items,
        'cal_months':   {i: {} for i in items},
        'fy_quarters':  {i: {} for i in items},
        'fy_halves':    {i: {} for i in items},
        'top5_fy':      {i: [] for i in items},
        'top5_cy':      {i: [] for i in items},
        'best_month':   {},
        'best_quarter': {},
    }

    # ── Calendar month: top 2 per (item, month number). The global
    #    best/2nd-best month are always contained in this set. ───────
    cur.execute(f"""
        SELECT item_name,
               CAST(SUBSTR(report_month,6,2) AS INTEGER) AS mon_num,
               report_month,
               SUM(month_actual) AS total
        FROM production_table
        WHERE {where}
        GROUP BY item_name, report_month
        ORDER BY item_name, mon_num, total DESC
    """, args)
    for item, mon_num, rm, total in cur.fetchall():
        cal = grp['cal_months'].get(item)
        if cal is None or total is None:
            continue
        rows = cal.setdefault(mon_num, [])
        if len(rows) < 2:
            rows.append({'period': _mon_label(rm), 'month': rm,
                         'total': round(total, 3)})

    # ── FY quarter: top 2 per (item, quarter) — rate items (Oven
    # Pushing, COB#*) are days-in-month-weighted averages, everything
    # else is a plain sum. Sorted in Python (not SQL) since the
    # correct value per row depends on the item. ────────────────────
    cur.execute(f"""
        SELECT item_name,
               {_q_expr()} AS qnum,
               {_fy_expr()} AS fy_start,
               SUM(month_actual) AS total,
               SUM(month_actual * {_days_expr()}) AS wsum,
               SUM({_days_expr()}) AS wdays
        FROM production_table
        WHERE {where}
        GROUP BY item_name, qnum, fy_start
        HAVING COUNT(DISTINCT report_month) = 3
    """, args)
    q_buckets = {}
    for item, qnum, fy_start, total, wsum, wdays in cur.fetchall():
        if item not in grp['fy_quarters'] or total is None:
            continue
        value = _period_value(item, total, wsum, wdays)
        q_buckets.setdefault((item, qnum), []).append(
            {'period': _fy_label(fy_start), 'fy_start': fy_start, 'total': round(value, 3)})
    for (item, qnum), rows in q_buckets.items():
        rows.sort(key=lambda r: r['total'], reverse=True)
        grp['fy_quarters'][item][_Q_LABELS[qnum]] = rows[:2]

    # ── FY half: top 2 per (item, half) ──────────────────────────────
    cur.execute(f"""
        SELECT item_name,
               CASE WHEN CAST(SUBSTR(report_month,6,2) AS INTEGER) BETWEEN 4 AND 9
                    THEN 1 ELSE 2 END AS hnum,
               {_fy_expr()} AS fy_start,
               SUM(month_actual) AS total,
               SUM(month_actual * {_days_expr()}) AS wsum,
               SUM({_days_expr()}) AS wdays
        FROM production_table
        WHERE {where}
        GROUP BY item_name, hnum, fy_start
        HAVING COUNT(DISTINCT report_month) = 6
    """, args)
    h_buckets = {}
    for item, hnum, fy_start, total, wsum, wdays in cur.fetchall():
        if item not in grp['fy_halves'] or total is None:
            continue
        value = _period_value(item, total, wsum, wdays)
        h_buckets.setdefault((item, hnum), []).append(
            {'period': _fy_label(fy_start), 'fy_start': fy_start, 'total': round(value, 3)})
    for (item, hnum), rows in h_buckets.items():
        rows.sort(key=lambda r: r['total'], reverse=True)
        grp['fy_halves'][item][_H_LABELS[hnum]] = rows[:2]

    # ── Top 5 FY per item ────────────────────────────────────────────
    cur.execute(f"""
        SELECT item_name, {_fy_expr()} AS fy_start,
               SUM(month_actual) AS total,
               SUM(month_actual * {_days_expr()}) AS wsum,
               SUM({_days_expr()}) AS wdays
        FROM production_table
        WHERE {where}
        GROUP BY item_name, fy_start
        HAVING COUNT(DISTINCT report_month) = 12
    """, args)
    fy_buckets = {}
    for item, fy_start, total, wsum, wdays in cur.fetchall():
        if item not in grp['top5_fy'] or total is None:
            continue
        value = _period_value(item, total, wsum, wdays)
        fy_buckets.setdefault(item, []).append(
            {'period': _fy_label(fy_start), 'total': round(value, 3)})
    for item, rows in fy_buckets.items():
        rows.sort(key=lambda r: r['total'], reverse=True)
        grp['top5_fy'][item] = rows[:5]

    # ── Top 5 CY per item ────────────────────────────────────────────
    cur.execute(f"""
        SELECT item_name, SUBSTR(report_month,1,4) AS yr,
               SUM(month_actual) AS total,
               SUM(month_actual * {_days_expr()}) AS wsum,
               SUM({_days_expr()}) AS wdays
        FROM production_table
        WHERE {where}
        GROUP BY item_name, yr
        HAVING COUNT(DISTINCT report_month) = 12
    """, args)
    cy_buckets = {}
    for item, yr, total, wsum, wdays in cur.fetchall():
        if item not in grp['top5_cy'] or total is None:
            continue
        value = _period_value(item, total, wsum, wdays)
        cy_buckets.setdefault(item, []).append({'period': yr, 'total': round(value, 3)})
    for item, rows in cy_buckets.items():
        rows.sort(key=lambda r: r['total'], reverse=True)
        grp['top5_cy'][item] = rows[:5]

    # ── Best ever month / quarter, derived from the top-2 sets ───────
    for item in items:
        flat = [r for rows in grp['cal_months'][item].values() for r in rows]
        best = max(flat, key=lambda r: r['total'], default=None)
        grp['best_month'][item] = {
            'period': best['period'] if best else None,
            'month':  best['month'] if best else None,
            'total':  best['total'] if best else None,
        }

        qflat = [(label, r)
                 for label, rows in grp['fy_quarters'][item].items()
                 for r in rows]
        if qflat:
            label, r = max(qflat, key=lambda t: t[1]['total'])
            qnum = int(label[1])
            grp['best_quarter'][item] = {
                'period':   f"{r['period']} {label}",
                'qnum':     qnum,
                'fy_start': r['fy_start'],
                'total':    r['total'],
            }
        else:
            grp['best_quarter'][item] = {
                'period': None, 'qnum': None,
                'fy_start': None, 'total': None,
            }

    return grp


def _latest_production_month(cur) -> str:
    """Latest month with production data — lets callers flag records that
    were set just now (period ending at/near this month)."""
    cur.execute("""
        SELECT MAX(report_month) FROM production_table
        WHERE report_month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'
    """)
    return cur.fetchone()[0]


def generate_records() -> dict:
    conn = db.connect()
    cur  = conn.cursor()
    sort_key = _item_sort_key()
    try:
        result = {}
        groups = [('sail5', SAIL5), ('all8', ALL8)] + [(p, [p]) for p in ALL8]
        for group_name, plants in groups:
            ph = _ph(plants)
            # Group scopes keep the summary items (unit-level items don't sum
            # meaningfully across plants); single-plant scopes cover every
            # unit/item that plant has ever reported (BF#1, SMS-2, URM …).
            if len(plants) == 1:
                cur.execute(
                    "SELECT DISTINCT item_name FROM production_table WHERE plant_name=?",
                    plants)
                items = sorted((r[0] for r in cur.fetchall()), key=sort_key)
                where = f"plant_name IN ({ph})"
                args  = list(plants)
            else:
                items = ITEMS
                where = f"item_name IN ({_ph(ITEMS)}) AND plant_name IN ({ph})"
                args  = ITEMS + plants

            result[group_name] = _compute_group_records(cur, items, where, args)

        result['latest_month'] = _latest_production_month(cur)
        return result
    finally:
        conn.close()


# Items shown on the Best-Ever Highlights / Best Calendar Month report
# pages — a fixed 6-item subset (per direct instruction), narrower than
# ITEMS above (drops Pig Iron, adds Oven Pushing). "Oven Pushing (nos/day)"
# is the canonical item name (5/5 plants, full history); "Oven Pushing(nos/d)"
# is a legacy duplicate name with sparse coverage (2 plants, a handful of
# months) predating the canonical name's rollout — excluded here to avoid
# double-counting the same physical figure under two different item_names.
HIGHLIGHT_ITEMS = [
    'Oven Pushing (nos/day)', 'Total Sinter', 'Hot Metal',
    'Total Crude Steel', 'Finished Steel', 'Saleable Steel',
]
HIGHLIGHT_LABELS = {
    'Oven Pushing (nos/day)': 'Oven Pushing (nos/day)',
    'Total Sinter':           'Sinter',
    'Hot Metal':              'Hot Metal',
    'Total Crude Steel':      'Crude Steel',
    'Finished Steel':         'Finished Steel',
    'Saleable Steel':         'Saleable Steel',
}


# "Major" production items for the Best-Period query (process order).
MAJOR_ITEMS = [
    'Total Sinter', 'Hot Metal', 'Pig Iron', 'Total Crude Steel',
    'Finished Steel', 'Saleable Steel', 'Oven Pushing (nos/day)',
]

_BEST_PERIOD_SCOPES = {
    'sail5':  [('SAIL (5 Plants)', SAIL5)],
    'all8':   [('SAIL (8 Plants)', ALL8)],
    'plants': [(p, [p]) for p in ALL8],   # each plant / unit its own column
}


def _compute_best_period(cur, items: list, where: str, args: list,
                         s_pos: int, e_pos: int, top_n: int) -> dict:
    """Top-`top_n` financial years by production over the FY-relative month
    window [s_pos, e_pos] (0 = Apr … 11 = Mar), per item. Only FYs whose
    window is complete (all window_len months present) are ranked.

    Tonnage items: sum of every member plant's window total.
    Rate items (Oven Pushing, COB#*): sum of each member plant's own
    days-in-month-weighted mean over the window — i.e. the SAIL total
    nos/day, not a per-plant average. Output keyed in `items` order,
    items with no complete window omitted."""
    window_len = e_pos - s_pos + 1
    item_set = set(items)
    cur.execute(f"""
        SELECT item_name, {_fy_expr()} AS fy_start, plant_name, report_month,
               SUM(month_actual)     AS v,
               MAX({_days_expr()})   AS days
        FROM production_table
        WHERE {where} AND ({_fy_pos_expr()}) BETWEEN ? AND ?
        GROUP BY item_name, fy_start, plant_name, report_month
    """, list(args) + [s_pos, e_pos])

    # (item, fy_start) -> {'months': set, 'plants': {plant: [wsum, wdays, total]}}
    acc: dict = {}
    for item, fy_start, plant, rm, v, days in cur.fetchall():
        if item not in item_set or v is None:
            continue
        d = acc.setdefault((item, fy_start), {'months': set(), 'plants': {}})
        d['months'].add(rm)
        p = d['plants'].setdefault(plant, [0.0, 0.0, 0.0])
        p[0] += v * days
        p[1] += days
        p[2] += v

    buckets: dict = {}
    for (item, fy_start), d in acc.items():
        if len(d['months']) != window_len:
            continue
        if is_rate_item(item):
            value = sum(w[0] / w[1] for w in d['plants'].values() if w[1])
        else:
            value = sum(w[2] for w in d['plants'].values())
        buckets.setdefault(item, []).append(
            {'fy': _fy_label(fy_start), 'fy_start': fy_start, 'total': round(value, 3)})

    out = {}
    for item in items:
        rows = buckets.get(item)
        if not rows:
            continue
        rows.sort(key=lambda r: r['total'], reverse=True)
        out[item] = rows[:top_n]
    return out


def generate_best_period(start_mon: int, end_mon: int, scope: str = 'sail5',
                         items_mode: str = 'major', top_n: int = 5) -> dict:
    """Best `top_n` financial years for a caller-defined month window
    (`start_mon`..`end_mon`, calendar month numbers, interpreted within the
    financial year Apr→Mar so e.g. Oct→Feb spans the year boundary).

      scope      : 'sail5' | 'all8' (group aggregates) | 'plants' (per plant)
      items_mode : 'major' (MAJOR_ITEMS) | 'all' (every item the scope reports)

    Response:
      { window: {...}, scope, items_mode, column_order: [...],
        results: { <column>: { <item_name>: [ {fy, fy_start, total}, ... ] } },
        latest_month }
    """
    if not (1 <= start_mon <= 12 and 1 <= end_mon <= 12):
        raise ValueError("start_mon and end_mon must be 1-12")
    s_pos = start_mon - 4 if start_mon >= 4 else start_mon + 8
    e_pos = end_mon - 4 if end_mon >= 4 else end_mon + 8
    if e_pos < s_pos:
        raise ValueError("end month must not precede start month within the "
                         "financial year (Apr → Mar order)")
    if scope not in _BEST_PERIOD_SCOPES:
        raise ValueError(f"unknown scope {scope!r} (sail5 | all8 | plants)")
    if items_mode not in ('major', 'all'):
        raise ValueError(f"unknown items mode {items_mode!r} (major | all)")

    columns = _BEST_PERIOD_SCOPES[scope]
    conn = db.connect()
    cur = conn.cursor()
    sort_key = _item_sort_key()
    try:
        results = {}
        for col_key, plants in columns:
            ph = _ph(plants)
            if items_mode == 'all':
                cur.execute(
                    f"SELECT DISTINCT item_name FROM production_table WHERE plant_name IN ({ph})",
                    list(plants))
                items = sorted((r[0] for r in cur.fetchall()), key=sort_key)
            else:
                items = MAJOR_ITEMS
            where = f"item_name IN ({_ph(items)}) AND plant_name IN ({ph})"
            args = list(items) + list(plants)
            results[col_key] = _compute_best_period(
                cur, items, where, args, s_pos, e_pos, top_n)

        window_months = [_MON[_pos_to_mon(p)] for p in range(s_pos, e_pos + 1)]
        return {
            'window': {
                'start_mon': start_mon, 'end_mon': end_mon,
                'start_label': _MON[start_mon], 'end_label': _MON[end_mon],
                'length': e_pos - s_pos + 1,
                'months': window_months,
                'spans_year_end': e_pos > 8 >= s_pos or (s_pos >= 9),
            },
            'scope': scope,
            'items_mode': items_mode,
            'column_order': [c[0] for c in columns],
            'results': results,
            'latest_month': _latest_production_month(cur),
        }
    finally:
        conn.close()


def generate_group_records(items: list = HIGHLIGHT_ITEMS) -> dict:
    """Like generate_records(), but only the two plant-group scopes
    (sail5/all8) and a caller-supplied item list — used by the Best-Ever
    Highlights and Best Calendar Month report pages, which don't need
    generate_records()'s full per-plant/unit sweep."""
    conn = db.connect()
    cur  = conn.cursor()
    try:
        result = {}
        for group_name, plants in [('sail5', SAIL5), ('all8', ALL8)]:
            ph = _ph(plants)
            where = f"item_name IN ({_ph(items)}) AND plant_name IN ({ph})"
            args  = items + plants
            result[group_name] = _compute_group_records(cur, items, where, args)

        result['latest_month'] = _latest_production_month(cur)
        return result
    finally:
        conn.close()
