"""
Production record statistics — best/2nd-best by calendar month, FY quarter,
FY half, and top-5 FY / calendar years for the major production items.
Computed for the SAIL group aggregates ('sail5', 'all8') and for every
individual plant/unit (keyed by plant code, e.g. 'BSP', 'ASP').
Used by the /api/production-records endpoint.
"""
import db
from page_production_fy_export import is_rate_item
from repo import production as rp

ITEMS = ['Total Sinter', 'Hot Metal', 'Total Crude Steel',
         'Saleable Steel', 'Pig Iron', 'Finished Steel']
SAIL5 = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP']
ALL8  = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP', 'VISL']

# Legacy item_name spellings superseded by a canonical one (main.py's
# normalize_item_name / the BF-N -> BF#N, "Oven Pushing(nos/d)" -> "Oven
# Pushing (nos/day)" cleanup) but not yet fully migrated out of
# production_table — BSL's BF-1..BF-5 still have one un-merged month
# (2026-07, where the old and new spellings genuinely disagree, flagged for
# manual review rather than silently discarded during that cleanup).
# generate_records()'s single-plant sweep below reads DISTINCT item_name
# straight from the table, so these would otherwise show up as their own
# near-empty rows (1 month of history each) right next to the real,
# fully-populated BF#1..BF#5 rows. Excluded here at read time — remove an
# entry once its production_table rows are fully migrated to the canonical
# name.
LEGACY_ITEM_NAMES = {'BF-1', 'BF-2', 'BF-3', 'BF-4', 'BF-5'}

_MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

_Q_LABELS = {1: 'Q1', 2: 'Q2', 3: 'Q3', 4: 'Q4'}
_H_LABELS = {1: 'H1', 2: 'H2'}


def _mon_label(ym):
    m = int(ym[5:7])
    return f"{_MON[m]}'{ym[2:4]}"


def _fy_label(fy_start):
    return f"{fy_start}-{str(fy_start + 1)[2:]}"


def _pos_to_mon(pos: int) -> int:
    """FY position (0 = Apr) -> calendar month number (1-12)."""
    return pos + 4 if pos < 9 else pos - 8


def _cells_period_value(item, plant_cells):
    """plant_cells: {plant: [wsum, wdays, total]} accumulated over a period's
    (plant, month) cells. Tonnage item -> Σ of every plant's total; rate item
    (Oven Pushing nos/day, COB#*) -> Σ of each plant's own day-in-month
    weighted mean = the SAIL nos/day, NOT a per-plant average (grouping the
    days together across plants would divide by plant_count)."""
    if is_rate_item(item):
        return sum(w[0] / w[1] for w in plant_cells.values() if w[1])
    return sum(w[2] for w in plant_cells.values())


def _bucketed_period_values(cur, items: list, scope, bucket: str,
                            required_months: int) -> dict:
    """{(item_name, *bucket): value} for every (item, period bucket) whose
    window has exactly `required_months` distinct report_months.

    scope: rp.records_scope(...). bucket: the period columns, see
    rp.records_bucket_cells ('quarter' -> (qnum, fy_start), 'half' ->
    (hnum, fy_start), 'fy' -> (fy_start,), 'cy' -> (yr,)). Values are
    combined per `_cells_period_value` (rate-item aware)."""
    item_set = set(items)

    acc = {}  # (item, bucket_tuple) -> {'months': set, 'plants': {plant: [wsum, wdays, total]}}
    for row in rp.records_bucket_cells(cur, scope, bucket):
        n = len(row) - 5
        item, bucket = row[0], tuple(row[1:1 + n])
        plant, rm, v, days = row[1 + n], row[2 + n], row[3 + n], row[4 + n]
        if item not in item_set or v is None:
            continue
        d = acc.setdefault((item, bucket), {'months': set(), 'plants': {}})
        d['months'].add(rm)
        p = d['plants'].setdefault(plant, [0.0, 0.0, 0.0])
        p[0] += v * days
        p[1] += days
        p[2] += v

    return {
        (item, *bucket): round(_cells_period_value(item, d['plants']), 3)
        for (item, bucket), d in acc.items()
        if len(d['months']) == required_months
    }


def _item_sort_key():
    """Process-order sort for item names; alphabetical fallback if main's
    helpers aren't importable (lazy import avoids a circular import — main
    imports this module at startup, we only need main at request time)."""
    try:
        from main import normalize_item_name, production_item_sort_key
        return lambda n: production_item_sort_key(normalize_item_name(n))
    except Exception:
        return lambda n: n


def _compute_group_records(cur, items: list, scope) -> dict:
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
        'top5_months':  {i: [] for i in items},
        'best_month':   {},
        'best_quarter': {},
    }

    # ── Calendar month: top 2 per (item, month number). The global
    #    best/2nd-best month are always contained in this set. ───────
    all_months = {}
    for item, mon_num, rm, total in rp.records_calendar_month_totals(cur, scope):
        cal = grp['cal_months'].get(item)
        if cal is None or total is None:
            continue
        rows = cal.setdefault(mon_num, [])
        if len(rows) < 2:
            rows.append({'period': _mon_label(rm), 'month': rm,
                         'total': round(total, 3)})
        all_months.setdefault(item, []).append((total, rm))

    # Top 5 single months ever (any calendar month) — the /records page's
    # all-time podium. Not derivable from cal_months' top-2-per-month set:
    # a month name can hold more than two of the overall top 5.
    for item, rows in all_months.items():
        rows.sort(reverse=True)
        grp['top5_months'][item] = [
            {'period': _mon_label(rm), 'month': rm, 'total': round(t, 3)}
            for t, rm in rows[:5]
        ]

    # ── FY quarter / half / top-5 FY / top-5 CY. Tonnage items are a
    # plain sum; rate items (Oven Pushing, COB#*) are the sum of each
    # plant's own days-in-month-weighted mean over the period — the SAIL
    # nos/day, not a per-plant average. Only complete periods (3 / 6 / 12
    # months present) count. ───────────────────────────────────────────
    q_buckets = {}
    for (item, qnum, fy_start), value in _bucketed_period_values(
            cur, items, scope, 'quarter', 3).items():
        q_buckets.setdefault((item, qnum), []).append(
            {'period': _fy_label(fy_start), 'fy_start': fy_start, 'total': value})
    for (item, qnum), rows in q_buckets.items():
        rows.sort(key=lambda r: r['total'], reverse=True)
        grp['fy_quarters'][item][_Q_LABELS[qnum]] = rows[:2]

    h_buckets = {}
    for (item, hnum, fy_start), value in _bucketed_period_values(
            cur, items, scope, 'half', 6).items():
        h_buckets.setdefault((item, hnum), []).append(
            {'period': _fy_label(fy_start), 'fy_start': fy_start, 'total': value})
    for (item, hnum), rows in h_buckets.items():
        rows.sort(key=lambda r: r['total'], reverse=True)
        grp['fy_halves'][item][_H_LABELS[hnum]] = rows[:2]

    fy_buckets = {}
    for (item, fy_start), value in _bucketed_period_values(
            cur, items, scope, 'fy', 12).items():
        fy_buckets.setdefault(item, []).append(
            {'period': _fy_label(fy_start), 'total': value})
    for item, rows in fy_buckets.items():
        rows.sort(key=lambda r: r['total'], reverse=True)
        grp['top5_fy'][item] = rows[:5]

    cy_buckets = {}
    for (item, yr), value in _bucketed_period_values(
            cur, items, scope, 'cy', 12).items():
        cy_buckets.setdefault(item, []).append({'period': yr, 'total': value})
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
    return rp.records_latest_month(cur)


def generate_records() -> dict:
    conn = db.connect()
    cur  = conn.cursor()
    sort_key = _item_sort_key()
    try:
        result = {}
        groups = [('sail5', SAIL5), ('all8', ALL8)] + [(p, [p]) for p in ALL8]
        for group_name, plants in groups:
            # Group scopes keep the summary items (unit-level items don't sum
            # meaningfully across plants); single-plant scopes cover every
            # unit/item that plant has ever reported (BF#1, SMS-2, URM …).
            if len(plants) == 1:
                items = sorted(
                    (r[0] for r in rp.distinct_items(cur, "actual", plants[0])
                     if r[0] not in LEGACY_ITEM_NAMES),
                    key=sort_key)
                scope = rp.records_scope(plants)
            else:
                items = ITEMS
                scope = rp.records_scope(plants, ITEMS)

            result[group_name] = _compute_group_records(cur, items, scope)

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


def _compute_best_period(cur, items: list, scope,
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
    # (item, fy_start) -> {'months': set, 'plants': {plant: [wsum, wdays, total]}}
    acc: dict = {}
    for item, fy_start, plant, rm, v, days in rp.records_fy_window_cells(cur, scope, s_pos, e_pos):
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
        buckets.setdefault(item, []).append(
            {'fy': _fy_label(fy_start), 'fy_start': fy_start,
             'total': round(_cells_period_value(item, d['plants']), 3)})

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
            if items_mode == 'all':
                items = sorted((r[0] for r in rp.records_plants_items_in(cur, plants)), key=sort_key)
            else:
                items = MAJOR_ITEMS
            scope = rp.records_scope(plants, items)
            results[col_key] = _compute_best_period(
                cur, items, scope, s_pos, e_pos, top_n)

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


def generate_group_records(items: list = HIGHLIGHT_ITEMS, upto_month: str = None) -> dict:
    """Like generate_records(), but only the two plant-group scopes
    (sail5/all8) and a caller-supplied item list — used by the Best-Ever
    Highlights and Best Calendar Month report pages, which don't need
    generate_records()'s full per-plant/unit sweep.

    upto_month ('YYYY-MM'): ignore data after this month, so a report for
    an earlier month never shows records from months after it (e.g. a May
    report must not list Jul/Aug, nor a Q1/H1 that isn't complete yet —
    quarters/halves only count once all their months are present).
    latest_month is capped to it too."""
    conn = db.connect()
    cur  = conn.cursor()
    try:
        result = {}
        for group_name, plants in [('sail5', SAIL5), ('all8', ALL8)]:
            scope = rp.records_scope(plants, items, upto_month)
            result[group_name] = _compute_group_records(cur, items, scope)

        latest = _latest_production_month(cur)
        result['latest_month'] = min(latest, upto_month) if (latest and upto_month) else (upto_month or latest)
        return result
    finally:
        conn.close()
