"""
Special Steel Report — pages 19-24.

Pages 19-22: Plant detail (BSP/DSP/RSP/BSL) — Quality/Grade-wise orders & actual.
Page 23:     ISP — one row per mill, no Quality/Grade column: ISP's source data
             arrives as a single consolidated figure per mill with no
             grade-level split.
Page 24:     SAIL consolidated, plant-wise.

Data source: special_steel_orders table
  (report_month, plant_name, product, quality_grade, sort_order, order_qty, actual_despatch)
ABP (Annual Business Plan) source: special_steel_abp_table for the per-plant
rows (report_month, plant_name, abp_qty), production_plan_table for the
"Saleable Steel production" summary row (existing ABP-plan infrastructure).
Page 24 shows only the FY ABP column — ISP and DSP don't carry a monthly
special-steel plan, only an FY one, so the month/till-month ABP columns
were dropped.

Each page carries two period sets side-by-side:
  • Month    : current month vs CPLY month
  • Cumulative: Apr→current month vs CPLY same range (Apr last-year → CPLY month)
"""
import re
import math
import datetime as _dt
import db


# ── grade clubbing ──────────────────────────────────────────────────────────
# Some product groups (esp. RSP's "New PM PLATES" / "HR PLATES SSL") list so
# many near-duplicate quality-grade spec variants that the page spills onto
# a second sheet. Clubbing lets a few of them be displayed as one combined
# row (figures summed) instead of hardcoding the combined text per case.
# Editor/admin-managed via /data-entry/special-steel-grade-clubs and
# api_special_steel_clubs.py — see special_steel_grade_clubs table. Rows
# sharing (plant_name, product, club_label) are members of one club; a grade
# can belong to at most one club per plant+product. Members not present in a
# given month/YTD just contribute zero, same as an ungrouped grade with no
# data that period.
_CLUB_TOKEN_RE = re.compile(r'\s+|[A-Za-z0-9]+|[^\sA-Za-z0-9]')
_CLUB_SUBTOKEN_RE = re.compile(r'\d+|[A-Za-z]+')


def _auto_club_label_pair(g1: str, g2: str, min_subtoken_prefix: int = 4) -> str:
    """Merge two quality-grade strings into one label: shared prefix +
    '/'-joined differing parts + shared suffix, e.g.
    'ASME SA387 GR11 CL2 (N & T)' + 'ASME SA387 GR12 CL2 (N & T)'
    -> 'ASME SA387 GR11/GR12 CL2 (N & T)'.

    Tokenizes on whitespace/alnum-run/punctuation boundaries so a shared
    prefix or suffix only absorbs *whole* codes (never splits a spec number
    like GR11/GR12 into a shared "GR1" + differing "1"/"2" — that reads as
    ambiguous). The one exception: when two whole tokens differ but one is a
    literal prefix of the other with at least `min_subtoken_prefix` shared
    leading letters/digits (e.g. "IS2041" is a prefix of "IS2041R355"), that
    shared lead is still folded into the prefix, since it's the same case as
    your worked IS2041 example.

    This is a formatting convenience for when the grade-clubbing UI doesn't
    get an explicit label — it is NOT a similarity detector. Run on
    arbitrary grade pairs it will happily produce nonsense (e.g. merging two
    unrelated ASTM standards into one confusing row), which is exactly why
    clubs are picked explicitly by a person rather than auto-detected."""
    t1, t2 = _CLUB_TOKEN_RE.findall(g1), _CLUB_TOKEN_RE.findall(g2)
    n1, n2 = len(t1), len(t2)

    i = 0
    while i < n1 and i < n2 and t1[i] == t2[i]:
        i += 1
    j = 0
    while j < (n1 - i) and j < (n2 - i) and t1[n1 - 1 - j] == t2[n2 - 1 - j]:
        j += 1

    prefix = "".join(t1[:i])
    suffix = "".join(t1[n1 - j:]) if j else ""
    mid1, mid2 = t1[i:n1 - j], t2[i:n2 - j]

    extra1 = extra2 = ""
    if mid1 and mid2:
        a, b = mid1[0], mid2[0]
        if a != b and a.isalnum() and b.isalnum():
            sa, sb = _CLUB_SUBTOKEN_RE.findall(a), _CLUB_SUBTOKEN_RE.findall(b)
            k = 0
            subpfx = ""
            while k < len(sa) and k < len(sb) and sa[k] == sb[k]:
                subpfx += sa[k]
                k += 1
            if subpfx and len(subpfx) >= min_subtoken_prefix:
                prefix += subpfx
                extra1, extra2 = a[len(subpfx):], b[len(subpfx):]
                mid1, mid2 = mid1[1:], mid2[1:]

    remainder1 = extra1 + "".join(mid1)
    remainder2 = extra2 + "".join(mid2)
    if not remainder1 and not remainder2:
        return prefix + suffix

    sep = " " if (remainder1 and prefix and prefix[-1:].isalnum() and remainder1[0].isalnum()) else ""
    return f"{prefix}{sep}{remainder1}/{remainder2}{suffix}"


def _auto_club_label(grades: list) -> str:
    """Fold _auto_club_label_pair across 3+ grades left to right."""
    label = grades[0]
    for g in grades[1:]:
        label = _auto_club_label_pair(label, g)
    return label


def _resolve_clubs(plant: str, product: str) -> tuple:
    """Return (grade_to_club_index, club_specs) for this (plant, product),
    where club_specs[i] = (member_grades, display_label). Reads
    special_steel_grade_clubs — see module-level grade-clubbing note."""
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT quality_grade, club_label FROM special_steel_grade_clubs "
        "WHERE plant_name=? AND product=? ORDER BY club_label, quality_grade",
        (plant, product),
    )
    rows = cur.fetchall()
    conn.close()

    grade_to_club = {}
    club_specs = []
    label_to_idx = {}
    for grade, label in rows:
        idx = label_to_idx.setdefault(label, len(club_specs))
        if idx == len(club_specs):
            club_specs.append(([], label))
        club_specs[idx][0].append(grade)
        grade_to_club[grade] = idx
    return grade_to_club, club_specs


# ── month-label helpers ───────────────────────────────────────────────────────

_MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

def _cum_label(months):
    """'Apr'26' for one month; 'Apr-May'26' for two, etc."""
    if not months:
        return ""
    fm = int(months[0][5:7])
    last = months[-1]
    lm, ly = int(last[5:7]), int(last[:4])
    ys = str(ly)[2:]
    if len(months) == 1:
        return f"{_MON[lm]}'{ys}"
    return f"{_MON[fm]}-{_MON[lm]}'{ys}"


# ── formatters ────────────────────────────────────────────────────────────────

def _fmt(v):
    return "" if (v is None or v == 0) else str(int(round(v)))

def _fmt0(v):
    return "" if v is None else str(int(round(v)))

def _pct(a, b):
    if not a or not b or b == 0:
        return ""
    return str(int(math.floor(a / b * 100 + 0.5)))

def _growth(cur, prev):
    if cur is None or prev is None or prev == 0:
        return ""
    return str(int(math.floor((cur - prev) / abs(prev) * 100 + 0.5)))


# ── row builders ──────────────────────────────────────────────────────────────

def _sep():
    return {"type": "separator"}

def _hdr(label):
    return {"type": "product-hdr", "label": label}

def _grade(label, orders, actual, cply,
           cum_orders=0, cum_actual=0, cum_cply=None):
    o, a   = orders or 0, actual or 0
    co, ca = cum_orders or 0, cum_actual or 0
    return {
        "type": "grade", "label": label,
        "orders": _fmt0(o), "actual": _fmt0(a),
        "pct_ful": _pct(a, o) if o else "",
        "cply": _fmt0(cply), "pct_growth": _growth(a, cply),
        "cum_orders": _fmt0(co), "cum_actual": _fmt0(ca),
        "cum_pct_ful": _pct(ca, co) if co else "",
        "cum_cply": _fmt0(cum_cply), "cum_pct_growth": _growth(ca, cum_cply),
    }

def _total(label, orders, actual, cply, row_type="product-total",
           cum_orders=0, cum_actual=0, cum_cply=None):
    o, a   = orders or 0, actual or 0
    co, ca = cum_orders or 0, cum_actual or 0
    return {
        "type": row_type, "label": label,
        "orders": _fmt0(o), "actual": _fmt0(a),
        "pct_ful": _pct(a, o) if o else "",
        "cply": _fmt0(cply), "pct_growth": _growth(a, cply),
        "cum_orders": _fmt0(co), "cum_actual": _fmt0(ca),
        "cum_pct_ful": _pct(ca, co) if co else "",
        "cum_cply": _fmt0(cum_cply), "cum_pct_growth": _growth(ca, cum_cply),
    }


# ── DB helpers ────────────────────────────────────────────────────────────────

def _fetch_group(cur, month, plant, product):
    cur.execute("""
        SELECT quality_grade, section, order_qty, actual_despatch
        FROM special_steel_orders
        WHERE report_month=? AND plant_name=? AND product=?
        ORDER BY sort_order, quality_grade, section
    """, (month, plant, product))
    return cur.fetchall()

def _fetch_all_grades(cur, all_months, plant, product):
    """Union of (quality_grade, section) pairs that have any record in the given
    months, ordered by sort_order. Covers current month, YTD, CPLY and CPLY-YTD.
    section is '' for plants without a section breakdown."""
    ph = ",".join("?" * len(all_months))
    cur.execute(f"""
        SELECT quality_grade, section, MIN(sort_order)
        FROM special_steel_orders
        WHERE report_month IN ({ph}) AND plant_name=? AND product=?
        GROUP BY quality_grade, section
        ORDER BY MIN(sort_order), quality_grade, section
    """, (*all_months, plant, product))
    return [(r[0], r[1]) for r in cur.fetchall()]

def _fetch_cply(cur, cply_month, plant, product):
    cur.execute("""
        SELECT quality_grade, section, actual_despatch
        FROM special_steel_orders
        WHERE report_month=? AND plant_name=? AND product=?
    """, (cply_month, plant, product))
    return {(r[0], r[1]): r[2] for r in cur.fetchall()}

def _fetch_group_ytd(cur, ytd_months, plant, product):
    """(quality_grade, section) → (sum_order_qty, sum_actual_despatch) across YTD months."""
    ph = ",".join("?" * len(ytd_months))
    cur.execute(f"""
        SELECT quality_grade, section,
               COALESCE(SUM(order_qty),0),
               COALESCE(SUM(actual_despatch),0)
        FROM special_steel_orders
        WHERE report_month IN ({ph}) AND plant_name=? AND product=?
        GROUP BY quality_grade, section
    """, (*ytd_months, plant, product))
    return {(r[0], r[1]): (r[2], r[3]) for r in cur.fetchall()}

def _fetch_cply_ytd(cur, cply_ytd_months, plant, product):
    """(quality_grade, section) → sum_actual_despatch across CPLY YTD months."""
    ph = ",".join("?" * len(cply_ytd_months))
    cur.execute(f"""
        SELECT quality_grade, section, COALESCE(SUM(actual_despatch),0)
        FROM special_steel_orders
        WHERE report_month IN ({ph}) AND plant_name=? AND product=?
        GROUP BY quality_grade, section
    """, (*cply_ytd_months, plant, product))
    return {(r[0], r[1]): r[2] for r in cur.fetchall()}

def _get_prod(cur, month, plant, item):
    cur.execute(
        "SELECT month_actual FROM production_table"
        " WHERE report_month=? AND plant_name=? AND item_name=?",
        (month, plant, item))
    r = cur.fetchone()
    return r[0] if r and r[0] is not None else None

def _get_prod_ytd(cur, ytd_months, plant, item):
    ph = ",".join("?" * len(ytd_months))
    cur.execute(f"""
        SELECT COALESCE(SUM(month_actual),0)
        FROM production_table
        WHERE report_month IN ({ph}) AND plant_name=? AND item_name=?
    """, (*ytd_months, plant, item))
    r = cur.fetchone()
    return r[0] if r and r[0] else None


_SSPS_PLANTS = ("ASP", "VISL", "SSP")


def _ssps_special_steel(cur, months, item="Total Saleable Steel Despatch"):
    """SSPs carries no order-book rows in special_steel_orders, so its
    'actual' special-steel figure on page 24 is derived instead from
    production_table: Salem Steel Plant's (SSP) own <item> despatch,
    minus SSP's Finished Carbon Steel Despatch (Salem runs both
    stainless/special and ordinary carbon steel off the same lines, so the
    carbon-steel portion of its despatch isn't special steel and must be
    subtracted out). Alloy Steels Plant and VISL are excluded — despite the
    'SSPs' label bundling all three plants elsewhere, only Salem's own
    despatch counts as special steel for this figure. Uses the DESPATCHES
    section figures (pdf_extractor_ssp.py), not SALEABLE PRODUCTION, since
    despatch is what actually leaves the plant.
    production_table stores '000T; this page is in T -> ×1000, same
    convention as ss_cur/ss_abp_fy below."""
    ph = ",".join("?" * len(months))
    cur.execute(f"""
        SELECT COALESCE(SUM(month_actual),0) FROM production_table
        WHERE report_month IN ({ph}) AND plant_name='SSP' AND item_name=?
    """, (*months, item))
    total = (cur.fetchone() or [0])[0]
    cur.execute(f"""
        SELECT COALESCE(SUM(month_actual),0) FROM production_table
        WHERE report_month IN ({ph}) AND plant_name='SSP' AND item_name='Finished Carbon Steel Despatch'
    """, (*months,))
    carbon = (cur.fetchone() or [0])[0]
    return (total - carbon) * 1000


def _get_abp_sum(cur, months, plant):
    """Sum of a plant's Special Steel ABP targets over a set of months —
    used for the 'ABP of FY' column (the only ABP period shown on page 24;
    ISP and DSP don't carry a monthly special-steel plan, only an FY one,
    so the month/till-month ABP columns were dropped).

    special_steel_abp_table.abp_qty is stored in '000T (same convention as
    production_table), but every other column on this page (orders/actual/
    cply, from special_steel_orders) is already in T — so this is scaled
    ×1000 here, same as the Saleable Steel row's own ABP a few lines down
    in generate_special_steel_sail."""
    ph = ",".join("?" * len(months))
    cur.execute(f"""
        SELECT COALESCE(SUM(abp_qty),0)
        FROM special_steel_abp_table
        WHERE report_month IN ({ph}) AND plant_name=?
    """, (*months, plant))
    r = cur.fetchone()
    return r[0] * 1000 if r and r[0] else None


def _gkey(qg, sec):
    """Case/whitespace-normalized (quality_grade, section) dict key.

    Different months' uploads/manual entries have stored the exact same
    grade under different casing (confirmed: BSL HR COIL's "Boiler Quality"
    vs "BOILER QUALITY" — same grade, different month, e.g. 2026-07 was
    entered upper-case while every surrounding month used title case). SQL
    GROUP BY (in _fetch_all_grades/_fetch_group_ytd/_fetch_cply_ytd) already
    merges these correctly under a case-insensitive collation, but a plain
    Python dict keyed on the raw string does not — cur_map.get((qg, sec))
    below silently missed a month whose casing didn't match whichever
    variant _fetch_all_grades happened to pick as its group's representative
    string, showing 0 for that period despite real data existing. Normalize
    every dict key (never the displayed label, which keeps its original
    casing) so a grade matches across months regardless of casing."""
    return ((qg or "").strip().upper(), (sec or "").strip().upper())


def _build_group(cur, month, cply_month, ytd_months, cply_ytd_months,
                 plant, product_group, total_label, club_sections=False):
    """Return (rows, g_ord, g_act, g_cply, g_cum_ord, g_cum_act, g_cum_cply).

    Lists every quality grade that has data in ANY of: current month,
    YTD months, CPLY month, or CPLY-YTD months.

    club_sections=True collapses a quality grade's separate section/size
    variants into a single row (figures summed across sections) instead of
    one row per (quality_grade, section) pair — used where the section
    breakdown isn't wanted on the printed page."""
    rows     = [_hdr(product_group)]
    cur_map  = {_gkey(qg, sec): (o, a) for qg, sec, o, a in _fetch_group(cur, month, plant, product_group)}
    cply_map = {_gkey(*k): v for k, v in _fetch_cply(cur, cply_month, plant, product_group).items()}
    ytd_map  = {_gkey(*k): v for k, v in _fetch_group_ytd(cur, ytd_months, plant, product_group).items()}
    cytd_map = {_gkey(*k): v for k, v in _fetch_cply_ytd(cur, cply_ytd_months, plant, product_group).items()}

    # ytd_months includes the current month; cply_ytd_months includes cply_month
    all_grades = _fetch_all_grades(cur, ytd_months + cply_ytd_months, plant, product_group)

    if club_sections:
        collapsed_order = []
        for qg, _sec in all_grades:
            if qg not in collapsed_order:
                collapsed_order.append(qg)
        all_grades = [(qg, "") for qg in collapsed_order]

        def _collapse_qty(m):
            out = {}
            for (qg, _sec), (o, a) in m.items():
                oo, aa = out.get(qg, (0, 0))
                out[qg] = (oo + (o or 0), aa + (a or 0))
            return {(qg, ""): v for qg, v in out.items()}

        def _collapse_single(m):
            # Stays None only if every section variant was also None for
            # that period, so has_cply/has_cum_cply still distinguish a
            # real zero from "not reported this period".
            out = {}
            for (qg, _sec), v in m.items():
                if v is None:
                    out.setdefault(qg, None)
                else:
                    out[qg] = (out.get(qg) or 0) + v
            return {(qg, ""): v for qg, v in out.items()}

        cur_map  = _collapse_qty(cur_map)
        ytd_map  = _collapse_qty(ytd_map)
        cply_map = _collapse_single(cply_map)
        cytd_map = _collapse_single(cytd_map)

    g_ord = g_act = g_cply = 0.0
    g_cum_ord = g_cum_act = g_cum_cply = 0.0
    has_cply = has_cum_cply = False

    # See _resolve_clubs — some quality grades are combined into one displayed
    # row (figures summed) instead of one row per grade, to keep dense
    # product groups from spilling onto a second page.
    grade_to_club, club_specs = _resolve_clubs(plant, product_group)
    emitted_clubs = set()

    for qg, sec in all_grades:
        club_idx = grade_to_club.get(qg) if not sec else None
        if club_idx is not None:
            if club_idx in emitted_clubs:
                continue
            emitted_clubs.add(club_idx)
            members, label = club_specs[club_idx]
            o = a = co = ca = 0.0
            c_parts, cc_parts = [], []
            for g in members:
                mo, ma = cur_map.get(_gkey(g, ""), (0, 0))
                o += mo or 0; a += ma or 0
                mco, mca = ytd_map.get(_gkey(g, ""), (0, 0))
                co += mco or 0; ca += mca or 0
                mc = cply_map.get(_gkey(g, ""))
                if mc is not None: c_parts.append(mc)
                mcc = cytd_map.get(_gkey(g, ""))
                if mcc is not None: cc_parts.append(mcc)
            c  = sum(c_parts) if c_parts else None
            cc = sum(cc_parts) if cc_parts else None
        else:
            o, a   = cur_map.get(_gkey(qg, sec), (0, 0))
            o, a   = o or 0, a or 0
            c      = cply_map.get(_gkey(qg, sec))
            co, ca = ytd_map.get(_gkey(qg, sec), (0, 0))
            cc     = cytd_map.get(_gkey(qg, sec))
            label  = f"{qg} {sec}".strip() if sec else qg

        # Hide rows with no activity in current month, YTD, or either CPLY period
        if (o == 0 and a == 0 and
                (co or 0) == 0 and (ca or 0) == 0 and
                not (c or 0) and not (cc or 0)):
            continue

        g_ord += o; g_act += a
        g_cum_ord += co; g_cum_act += ca
        if c  is not None: g_cply     += c;  has_cply     = True
        if cc is not None: g_cum_cply += cc; has_cum_cply = True

        rows.append(_grade(label, o, a, c, co, ca, cc))

    if total_label:
        rows.append(_total(
            total_label, g_ord, g_act,
            g_cply if has_cply else None, "product-total",
            g_cum_ord, g_cum_act,
            g_cum_cply if has_cum_cply else None,
        ))

    return (rows, g_ord, g_act,
            g_cply if has_cply else 0.0,
            g_cum_ord, g_cum_act,
            g_cum_cply if has_cum_cply else 0.0)


# ── plant-specific generators ─────────────────────────────────────────────────

def _gen_bsp(cur, month, cply_month, ytd_months, cply_ytd_months):
    rows = []
    long_o = long_a = long_c = long_co = long_ca = long_cc = 0.0

    for grp, lbl in [
        ("Semis",             "Total Semis"),
        ("Wire Rods",         "Total Wire Rod Mill"),
        ("Merchant Products", "Total Merchant Mill"),
        ("BRM Product",       "Total BRM PRODUCT"),
        ("Rails",             None),
    ]:
        r, o, a, c, co, ca, cc = _build_group(
            cur, month, cply_month, ytd_months, cply_ytd_months, "BSP", grp, lbl)
        rows.extend(r)
        long_o += o; long_a += a; long_c += c
        long_co += co; long_ca += ca; long_cc += cc

    rows.append(_sep())
    rows.append(_total("Total Special Long Products",
                       long_o, long_a, long_c or None, "subtotal",
                       long_co, long_ca, long_cc or None))
    rows.append(_sep())

    r, p_o, p_a, p_c, p_co, p_ca, p_cc = _build_group(
        cur, month, cply_month, ytd_months, cply_ytd_months, "BSP", "Plates", "Total Plates")
    rows.extend(r)
    rows.append(_sep())

    tot_o  = long_o  + p_o;  tot_a  = long_a  + p_a;  tot_c  = long_c  + p_c
    tot_co = long_co + p_co; tot_ca = long_ca + p_ca; tot_cc = long_cc + p_cc
    rows.append(_total("Total special steel",
                       tot_o, tot_a, tot_c or None, "grand-total",
                       tot_co, tot_ca, tot_cc or None))
    return rows, tot_o, tot_a, tot_c, tot_co, tot_ca, tot_cc


def _gen_dsp(cur, month, cply_month, ytd_months, cply_ytd_months):
    rows = []
    semi_o = semi_a = semi_c = semi_co = semi_ca = semi_cc = 0.0

    for grp, lbl in [
        ("CC BILLET", "Total CC Billet"),
        ("CC Bloom",  "Total CC Bloom"),
        ("CC Round",  "Total CC Round"),
        ("ASP",       None),
    ]:
        r, o, a, c, co, ca, cc = _build_group(
            cur, month, cply_month, ytd_months, cply_ytd_months, "DSP", grp, lbl,
            club_sections=True)
        rows.extend(r)
        semi_o += o; semi_a += a; semi_c += c
        semi_co += co; semi_ca += ca; semi_cc += cc

    rows.append(_sep())
    rows.append(_total("TOTAL SEMI-FINISHED",
                       semi_o, semi_a, semi_c or None, "subtotal",
                       semi_co, semi_ca, semi_cc or None))
    rows.append(_sep())

    fin_o = fin_a = fin_c = fin_co = fin_ca = fin_cc = 0.0
    for grp, lbl in [
        ("Structurals", "Total Structurals"),
        ("TMT",         "Total TMT"),
        ("W & A",       None),
    ]:
        r, o, a, c, co, ca, cc = _build_group(
            cur, month, cply_month, ytd_months, cply_ytd_months, "DSP", grp, lbl,
            club_sections=True)
        rows.extend(r)
        fin_o += o; fin_a += a; fin_c += c
        fin_co += co; fin_ca += ca; fin_cc += cc

    rows.append(_sep())
    rows.append(_total("TOTAL FINISHED STEEL",
                       fin_o, fin_a, fin_c or None, "subtotal",
                       fin_co, fin_ca, fin_cc or None))

    tot_o  = semi_o  + fin_o;  tot_a  = semi_a  + fin_a;  tot_c  = semi_c  + fin_c
    tot_co = semi_co + fin_co; tot_ca = semi_ca + fin_ca; tot_cc = semi_cc + fin_cc
    rows.append(_total("TOTAL SPECIAL STEEL",
                       tot_o, tot_a, tot_c or None, "grand-total",
                       tot_co, tot_ca, tot_cc or None))
    return rows, tot_o, tot_a, tot_c, tot_co, tot_ca, tot_cc


def _gen_rsp(cur, month, cply_month, ytd_months, cply_ytd_months):
    rows = []
    tot_o = tot_a = tot_c = tot_co = tot_ca = tot_cc = 0.0

    for grp, lbl in [
        ("PM PLATES",              "TOTAL"),
        ("New PM PLATES",          "TOTAL"),
        ("HR PLATES SSL",          "TOTAL"),
        ("HR COILS (SALE) -HSM-2", "TOTAL"),
        ("Pipes, CRNO",            "TOTAL"),
        ("SPP",                    "TOTAL"),
    ]:
        r, o, a, c, co, ca, cc = _build_group(
            cur, month, cply_month, ytd_months, cply_ytd_months, "RSP", grp, lbl)
        rows.extend(r)
        tot_o += o; tot_a += a; tot_c += c
        tot_co += co; tot_ca += ca; tot_cc += cc

    rows.append(_sep())
    rows.append(_total("GRAND TOTAL",
                       tot_o, tot_a, tot_c or None, "grand-total",
                       tot_co, tot_ca, tot_cc or None))
    return rows, tot_o, tot_a, tot_c, tot_co, tot_ca, tot_cc


def _gen_bsl(cur, month, cply_month, ytd_months, cply_ytd_months):
    rows = []
    tot_o = tot_a = tot_c = tot_co = tot_ca = tot_cc = 0.0

    for grp, lbl in [
        ("HR COIL",             "TOTAL"),
        ("HR PLATE",            "TOTAL"),
        ("HR SHEET",            "TOTAL"),
        ("CR COIL/SHEET/GP GC", "TOTAL"),
        ("SLAB",                "TOTAL"),
    ]:
        r, o, a, c, co, ca, cc = _build_group(
            cur, month, cply_month, ytd_months, cply_ytd_months, "BSL", grp, lbl)
        rows.extend(r)
        tot_o += o; tot_a += a; tot_c += c
        tot_co += co; tot_ca += ca; tot_cc += cc

    rows.append(_sep())
    rows.append(_total("GRAND TOTAL",
                       tot_o, tot_a, tot_c or None, "grand-total",
                       tot_co, tot_ca, tot_cc or None))
    return rows, tot_o, tot_a, tot_c, tot_co, tot_ca, tot_cc


def _gen_isp(cur, month, cply_month, ytd_months, cply_ytd_months):
    """ISP: mill-group-wise. The 6 raw source mills (WR COIL, TMT COIL,
    TMT BAR, STRUCTURALS, 150 BLT, 200 BLM — still the literal `product`
    values stored in special_steel_orders, and still what
    page_key_parameters.py's _SEMI_FINISHED_GROUPS['ISP'] matches against)
    are clubbed into 4 displayed rows per direct instruction: Bar Mill
    (TMT COIL + TMT BAR), WR Mill (WR COIL alone, renamed), Semis
    (150 BLT + 200 BLM), US Mill (STRUCTURALS alone, renamed).

    ISP's mill data arrives from the source plant as one consolidated figure
    per mill, with no quality/grade split — so unlike the other four plants
    there's no Quality/Grade column here, just one row per mill group (see
    the 'isp_summary' branch in special_steel.html / SpecialSteelTemplate.js)."""
    mill_groups = [
        ("Bar Mill", ["TMT COIL", "TMT BAR"]),
        ("WR Mill",  ["WR COIL"]),
        ("Semis",    ["150 BLT", "200 BLM"]),
        ("US Mill",  ["STRUCTURALS"]),
    ]
    ph_ytd  = ",".join("?" * len(ytd_months))
    ph_cytd = ",".join("?" * len(cply_ytd_months))
    rows    = []
    tot_o = tot_a = tot_c = tot_co = tot_ca = tot_cc = 0.0

    for label, mills in mill_groups:
        o = a = co = ca = 0.0
        c = cc = None
        for mill in mills:
            cur.execute("""
                SELECT order_qty, actual_despatch FROM special_steel_orders
                WHERE report_month=? AND plant_name='ISP' AND product=?
            """, (month, mill))
            r = cur.fetchone()
            o += (r[0] or 0) if r else 0
            a += (r[1] or 0) if r else 0

            cur.execute("""
                SELECT actual_despatch FROM special_steel_orders
                WHERE report_month=? AND plant_name='ISP' AND product=?
            """, (cply_month, mill))
            rc = cur.fetchone()
            if rc and rc[0] is not None:
                c = (c or 0) + rc[0]

            cur.execute(f"""
                SELECT COALESCE(SUM(order_qty),0), COALESCE(SUM(actual_despatch),0)
                FROM special_steel_orders
                WHERE report_month IN ({ph_ytd}) AND plant_name='ISP' AND product=?
            """, (*ytd_months, mill))
            ry = cur.fetchone()
            co += (ry[0] or 0) if ry else 0
            ca += (ry[1] or 0) if ry else 0

            cur.execute(f"""
                SELECT COALESCE(SUM(actual_despatch),0)
                FROM special_steel_orders
                WHERE report_month IN ({ph_cytd}) AND plant_name='ISP' AND product=?
            """, (*cply_ytd_months, mill))
            ryc = cur.fetchone()
            if ryc and ryc[0]:
                cc = (cc or 0) + ryc[0]

        tot_o += o; tot_a += a; tot_co += co; tot_ca += ca
        if c  is not None: tot_c  += c
        if cc is not None: tot_cc += cc
        rows.append(_grade(label, o, a, c, co, ca, cc))

    rows.append(_total("TOTAL SPECIAL STEEL",
                       tot_o, tot_a, tot_c or None, "grand-total",
                       tot_co, tot_ca, tot_cc or None))
    return rows, tot_o, tot_a, tot_c, tot_co, tot_ca, tot_cc


_GENERATORS = {
    "BSP": _gen_bsp,
    "DSP": _gen_dsp,
    "RSP": _gen_rsp,
    "BSL": _gen_bsl,
    "ISP": _gen_isp,
}

_TITLE_PREFIX = "Special Steel Report for : "

# Plant name split out from the fixed prefix above so the template can
# highlight just the plant name in "steel red" — see plant_display/
# title_prefix in generate_special_steel_plant()'s return dict.
_PLANT_DISPLAY_NAMES = {
    "BSP": "Bhilai Steel Plant",
    "DSP": "Durgapur Steel Plant",
    "RSP": "Rourkela Steel Plant",
    "BSL": "Bokaro Steel Plant",
    "ISP": "ISP",
}

_PLANT_TITLES = {p: _TITLE_PREFIX + name for p, name in _PLANT_DISPLAY_NAMES.items()}


# ── per-page density tiering ──────────────────────────────────────────────────
#
# Row count alone decides the tier — it's what actually governs whether the
# table fits one page vertically. Label length no longer gates the tier
# (BSP has only 36 rows, same ballpark as BSL's 42, but one combined-grade
# label — "TLT/MMn/45C8/Cr5 Grade(Billets)+(SBS-Slab)", 42 chars — used to
# force BSP down to RSP's tightest tier despite BSP using barely half the
# page). Instead, label length only tunes split_label's tail_scale: how hard
# the shrunk remainder of a split label must shrink to still fit the Grade
# column at THIS tier's font size. _TAIL_BUDGET is calibrated against the
# known-working case (tightest tier, 6.7pt, BSP's 42-char label, tail_scale
# 0.82) so plants that don't have an outlier label keep the default 0.82.
_DENSITY_TIERS = [
    # (max_rows, table_fs, label_fs, pad,           line_height, split_at)
    (15,         "10.6pt", "10.3pt", "3.4px 5.5px", "1.3",       999),
    (45,         "9.1pt",  "8.7pt",  "2.4px 5px",   "1.22",      26),
    (60,         "7.8pt",  "7.3pt",  "1.6px 3.3px", "1.16",      22),
]
_DENSITY_TIGHTEST = ("7.1pt", "6.7pt", "1.2px 2.6px", "1.12", 18)
_TAIL_SCALE_DEFAULT = 0.82
_TAIL_BUDGET = 190  # tuned against real rendered output, not pure font-ratio math —
# padding also grows a tier's cell width eats into, which a linear font-size
# ratio alone doesn't capture


def _tail_scale(label_fs: str, max_label_len: int) -> float:
    if not max_label_len:
        return _TAIL_SCALE_DEFAULT
    fs = float(label_fs.rstrip("pt"))
    return round(min(_TAIL_SCALE_DEFAULT, _TAIL_BUDGET / (fs * max_label_len)), 2)


def _compute_density(rows: list) -> dict:
    """Return table_fs/label_fs/pad/lh/split_at/tail_scale for this page's rows."""
    labels = [r.get("label", "") for r in rows if r.get("type") != "separator"]
    nrows = len(labels)
    max_label_len = max((len(l) for l in labels), default=0)

    for max_rows, table_fs, label_fs, pad, lh, split_at in _DENSITY_TIERS:
        if nrows <= max_rows:
            return {"table_fs": table_fs, "label_fs": label_fs, "pad": pad, "lh": lh,
                    "split_at": split_at, "tail_scale": _tail_scale(label_fs, max_label_len)}

    table_fs, label_fs, pad, lh, split_at = _DENSITY_TIGHTEST
    return {"table_fs": table_fs, "label_fs": label_fs, "pad": pad, "lh": lh,
            "split_at": split_at, "tail_scale": _tail_scale(label_fs, max_label_len)}


# ── product-column rowspan helper ────────────────────────────────────────────

def _add_product_spans(rows):
    """Remove product-hdr rows; annotate grade/product-total rows with
    product_name, prod_first, prod_rowspan so the frontend can render a
    merged, vertically-labelled Product column."""
    out = []
    cur_prod = ""
    grp = []   # indices into out[] for the current product group

    def flush():
        if grp and cur_prod:
            for k, idx in enumerate(grp):
                out[idx]["product_name"] = cur_prod
                out[idx]["prod_first"]   = (k == 0)
                out[idx]["prod_rowspan"] = len(grp) if k == 0 else 0

    for row in rows:
        t = row.get("type", "")
        if t == "product-hdr":
            flush(); grp.clear(); cur_prod = row["label"]
        elif t in ("grade", "product-total"):
            grp.append(len(out))
            out.append(dict(row))
        else:
            flush(); grp.clear(); cur_prod = ""
            out.append(dict(row))

    flush()
    return out


# ── public API ────────────────────────────────────────────────────────────────

def generate_special_steel_plant(report_month: str, plant: str) -> dict:
    """Pages 19-23: single-plant special steel report."""
    cply_month      = db.get_cply_month(report_month)
    ytd_months      = db.get_ytd_months(report_month)
    cply_ytd_months = [db.get_cply_month(m) for m in ytd_months]

    conn = db.connect()
    cur  = conn.cursor()
    try:
        gen = _GENERATORS.get(plant)
        if gen:
            rows, tot_o, tot_a, tot_c, tot_co, tot_ca, tot_cc = gen(
                cur, report_month, cply_month, ytd_months, cply_ytd_months)
            rows = _add_product_spans(rows)
        else:
            rows = []
            tot_o = tot_a = tot_c = tot_co = tot_ca = tot_cc = 0

        # production_table stores values in '000T; page unit is T → ×1000
        _t = lambda v: v * 1000 if v is not None else None
        ss_cur  = _t(_get_prod(cur, report_month, plant, "Saleable Steel"))
        ss_cply = _t(_get_prod(cur, cply_month,   plant, "Saleable Steel"))
        ss_cum  = _t(_get_prod_ytd(cur, ytd_months,      plant, "Saleable Steel"))
        ss_ccum = _t(_get_prod_ytd(cur, cply_ytd_months, plant, "Saleable Steel"))

        return {
            "title":         _PLANT_TITLES.get(plant, f"Special Steel — {plant}"),
            "title_prefix":  _TITLE_PREFIX,
            "plant_display": _PLANT_DISPLAY_NAMES.get(plant, plant),
            "unit":    "Tonnes",
            "plant":   plant,
            "variant": "isp_summary" if plant == "ISP" else "plant_detail",
            "rows":    rows,
            "density": _compute_density(rows),
            "cum_label":      _cum_label(ytd_months),
            "cum_cply_label": _cum_label(cply_ytd_months),
            "saleable_production": {
                "current":        _fmt(ss_cur),
                "cply":           _fmt(ss_cply),
                "cum_current":    _fmt(ss_cum),
                "cum_cply":       _fmt(ss_ccum),
                "cum_pct_growth": _growth(ss_cum, ss_ccum),
            },
            "special_pct": {
                "current":     _pct(tot_a,  ss_cur),
                "cply":        _pct(tot_c,  ss_cply),
                "cum_current": _pct(tot_ca, ss_cum),
                "cum_cply":    _pct(tot_cc, ss_ccum),
            },
        }
    finally:
        conn.close()


def generate_special_steel_sail(report_month: str) -> dict:
    """Page 24: SAIL consolidated plant-wise special steel."""
    cply_month      = db.get_cply_month(report_month)
    ytd_months      = db.get_ytd_months(report_month)
    cply_ytd_months = [db.get_cply_month(m) for m in ytd_months]
    fy_months       = db.get_fy_months(report_month)
    fy_label        = db.get_fy_for_month(report_month)[2:]  # '2026-27' -> '26-27'

    conn = db.connect()
    cur  = conn.cursor()
    try:
        plants  = ["BSP", "DSP", "RSP", "BSL", "ISP"]
        rows    = []
        ph_ytd  = ",".join("?" * len(ytd_months))
        ph_cytd = ",".join("?" * len(cply_ytd_months))
        sail_o = sail_a = sail_c = sail_co = sail_ca = sail_cc = 0.0
        sail_abp_fy = 0.0

        for plant in plants:
            cur.execute("""
                SELECT COALESCE(SUM(order_qty),0), COALESCE(SUM(actual_despatch),0)
                FROM special_steel_orders WHERE report_month=? AND plant_name=?
            """, (report_month, plant))
            o, a = cur.fetchone()

            cur.execute("""
                SELECT COALESCE(SUM(actual_despatch),0)
                FROM special_steel_orders WHERE report_month=? AND plant_name=?
            """, (cply_month, plant))
            c = (cur.fetchone() or [0])[0]

            cur.execute(f"""
                SELECT COALESCE(SUM(order_qty),0), COALESCE(SUM(actual_despatch),0)
                FROM special_steel_orders WHERE report_month IN ({ph_ytd}) AND plant_name=?
            """, (*ytd_months, plant))
            co, ca = cur.fetchone()

            cur.execute(f"""
                SELECT COALESCE(SUM(actual_despatch),0)
                FROM special_steel_orders WHERE report_month IN ({ph_cytd}) AND plant_name=?
            """, (*cply_ytd_months, plant))
            cc = (cur.fetchone() or [0])[0]

            abp_fy = _get_abp_sum(cur, fy_months, plant)

            sail_o += o; sail_a += a; sail_c += c
            sail_co += co; sail_ca += ca; sail_cc += cc
            sail_abp_fy += abp_fy or 0
            rows.append({
                "type": "plant", "label": plant,
                "abp_fy": _fmt(abp_fy),
                "orders": _fmt(o), "actual": _fmt(a),
                "pct_ful": _pct(a, o), "cply": _fmt(c), "pct_growth": _growth(a, c),
                "cum_orders": _fmt(co), "cum_actual": _fmt(ca),
                "cum_pct_ful": _pct(ca, co), "cum_cply": _fmt(cc),
                "cum_pct_growth": _growth(ca, cc),
            })

        # SSPs row — no order-book data (special_steel_orders has no rows
        # for 'SSPs'), so "orders"/"cum_orders" stay blank ('-' below) while
        # "actual"/"cply"/"cum_actual"/"cum_cply" are derived from
        # production_table via _ssps_special_steel (see its docstring).
        cur.execute("""
            SELECT COALESCE(SUM(order_qty),0) FROM special_steel_orders
            WHERE report_month=? AND plant_name='SSPs'
        """, (report_month,))
        ssps_o = (cur.fetchone() or [0])[0]
        cur.execute(f"""
            SELECT COALESCE(SUM(order_qty),0) FROM special_steel_orders
            WHERE report_month IN ({ph_ytd}) AND plant_name='SSPs'
        """, (*ytd_months,))
        ssps_co = (cur.fetchone() or [0])[0]

        ssps_a  = _ssps_special_steel(cur, [report_month])
        ssps_c  = _ssps_special_steel(cur, [cply_month])
        ssps_ca = _ssps_special_steel(cur, ytd_months)
        ssps_cc = _ssps_special_steel(cur, cply_ytd_months)

        ssps_abp_fy = _get_abp_sum(cur, fy_months, "SSPs")
        sail_abp_fy += ssps_abp_fy or 0

        rows.append({
            "type": "plant", "label": "SSPs",
            "abp_fy": _fmt(ssps_abp_fy),
            "orders": "-" if not ssps_o else _fmt(ssps_o),
            "actual": _fmt(ssps_a), "pct_ful": "",
            "cply": _fmt(ssps_c), "pct_growth": _growth(ssps_a, ssps_c),
            "cum_orders": "-" if not ssps_co else _fmt(ssps_co),
            "cum_actual": _fmt(ssps_ca), "cum_pct_ful": "",
            "cum_cply": _fmt(ssps_cc), "cum_pct_growth": _growth(ssps_ca, ssps_cc),
        })

        sail_at  = sail_a  + ssps_a;  sail_ct  = sail_c  + ssps_c
        sail_cat = sail_ca + ssps_ca; sail_cct = sail_cc + ssps_cc
        rows.append({
            "type": "sail-total", "label": "SAIL",
            "abp_fy": _fmt(sail_abp_fy),
            "orders": _fmt(sail_o),
            "actual": _fmt(sail_at), "pct_ful": _pct(sail_at, sail_o),
            "cply": _fmt(sail_ct), "pct_growth": _growth(sail_at, sail_ct),
            "cum_orders": _fmt(sail_co), "cum_actual": _fmt(sail_cat),
            "cum_pct_ful": _pct(sail_cat, sail_co),
            "cum_cply": _fmt(sail_cct), "cum_pct_growth": _growth(sail_cat, sail_cct),
        })

        # production_table stores values in '000T; page unit is T → ×1000.
        # Summed via db.get_sail_production_actual/_ytd_actual (all 8 plants —
        # the 5 integrated plants here PLUS ASP/SSP/VISL, same PLANTS list
        # get_sail_production_plan below already uses for the ABP figure)
        # rather than looping the local 5-plant `plants` list above: this row
        # is overall SAIL saleable steel production, not special-steel-only,
        # so it must include the SSPs group like the ABP column already does
        # — looping `plants` here previously left the actual/cply/cum/cply-cum
        # columns 3 plants short of the ABP column they sit next to.
        _t = lambda v: v * 1000 if v is not None else None
        ss_cur  = _t(db.get_sail_production_actual(report_month, "Saleable Steel"))
        ss_cply = _t(db.get_sail_production_actual(cply_month,   "Saleable Steel"))
        ss_cum  = _t(db.get_sail_production_ytd_actual(ytd_months,      "Saleable Steel"))
        ss_ccum = _t(db.get_sail_production_ytd_actual(cply_ytd_months, "Saleable Steel"))

        # Saleable Steel production ABP (FY only — see _get_abp_sum): existing
        # production_plan_table ABP-plan data (same source as page 3's
        # Production Performance Summary), not special_steel_abp_table — this
        # row is overall saleable steel, not special steel specifically.
        ss_abp_fy = sum(v * 1000 for m in fy_months for v in [db.get_sail_production_plan(m, "Saleable Steel")] if v)

        return {
            "title":   "Special Steel Performance of SAIL",
            "unit":    "Tonnes",
            "plant":   "SAIL",
            "variant": "sail_summary",
            "rows":    rows,
            "density": _compute_density(rows),
            "fy_label":       fy_label,
            "cum_label":      _cum_label(ytd_months),
            "cum_cply_label": _cum_label(cply_ytd_months),
            "saleable_production": {
                "abp_fy":         _fmt(ss_abp_fy),
                "current":        _fmt(ss_cur),
                "cply":           _fmt(ss_cply),
                "pct_growth":     _growth(ss_cur, ss_cply),
                "cum_current":    _fmt(ss_cum),
                "cum_cply":       _fmt(ss_ccum),
                "cum_pct_growth": _growth(ss_cum, ss_ccum),
            },
            "special_pct": {
                "abp":         _pct(sail_abp_fy, ss_abp_fy),
                "current":     _pct(sail_at,  ss_cur),
                "cply":        _pct(sail_ct,  ss_cply),
                "cum_current": _pct(sail_cat, ss_cum),
                "cum_cply":    _pct(sail_cct, ss_ccum),
            },
        }
    finally:
        conn.close()
