"""
Opening Stock at SAIL Plants and Stockyards — page 25.

Data source: stock_table
  (stock_month 'YYYY-MM' = stock as on 1st of that month,
   plant_name, item_type, stock_type, stock in tonnes)

Stored item_types : SLABS, BLOOM/BILLETS, FINISHED STEEL, PIG IRON
Stored stock_types: INPROCESS / FOR SALE  (SLABS, BLOOM/BILLETS only), '' otherwise.

Section numbering:
  1 SLABS
  2 BLOOM/BILLETS
  3 SEMIS (For Sale)   = 1b + 2b
  4 SEMIS (In process) = 1a + 2a
  5 SEMIS (Total)      = 3 + 4
  6 FINISHED STEEL
  7 SALEABLE STEEL     = 3 + 6
  8 TOTAL STEEL INV.   = 4 + 7

Column selection for a report month:
  • 1st Jan of last two FYs
  • 1st Apr of current FY  (mandatory)
  • 1st of report month and 1st of next month (mandatory)
  • highest / lowest SAIL total-inventory months in between
  • Var. column = (1st of next month) − (1st Apr of same FY)
"""
import sqlite3
import db

PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
TARGET_MONTH_COLS = 6


# ── month helpers ─────────────────────────────────────────────────────────────

def _add_months(ym: str, delta: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    t = y * 12 + (m - 1) + delta
    return f"{t // 12}-{t % 12 + 1:02d}"

def _col_label(ym: str) -> str:
    return f"1.{int(ym[5:7])}.{ym[2:4]}"


# ── value helpers ─────────────────────────────────────────────────────────────

def _nsum(*vals):
    vs = [v for v in vals if v is not None]
    return sum(vs) if vs else None

def _fmt(v):
    return "" if v is None else str(int(round(v)))


# ── data access ───────────────────────────────────────────────────────────────

def _load_stock(cur, months):
    ph = ",".join("?" * len(months))
    cur.execute(f"""
        SELECT stock_month, plant_name, item_type, stock_type, stock
        FROM stock_table WHERE stock_month IN ({ph})
    """, months)
    data = {}
    for m, p, it, st, v in cur.fetchall():
        data.setdefault(m, {}).setdefault(p, {}).setdefault(it, {})[st or ""] = v
    return data

def _g(data, m, p, item, st=""):
    return data.get(m, {}).get(p, {}).get(item, {}).get(st)


def _derived(data, m, p):
    sl_a = _g(data, m, p, "SLABS",         "INPROCESS")
    sl_b = _g(data, m, p, "SLABS",         "FOR SALE")
    bb_a = _g(data, m, p, "BLOOM/BILLETS", "INPROCESS")
    bb_b = _g(data, m, p, "BLOOM/BILLETS", "FOR SALE")
    fin  = _g(data, m, p, "FINISHED STEEL")
    pig  = _g(data, m, p, "PIG IRON")

    semis_sale = _nsum(sl_b, bb_b)
    semis_inp  = _nsum(sl_a, bb_a)
    semis_tot  = _nsum(semis_sale, semis_inp)
    saleable   = _nsum(semis_sale, fin)
    tot_inv    = _nsum(semis_inp, saleable)

    return {
        "sl_a": sl_a, "sl_b": sl_b, "bb_a": bb_a, "bb_b": bb_b,
        "fin": fin, "pig": pig,
        "semis_sale": semis_sale, "semis_inp": semis_inp, "semis_tot": semis_tot,
        "saleable": saleable, "tot_inv": tot_inv,
    }


# ── column selection ──────────────────────────────────────────────────────────

def _select_months(cur, report_month):
    y, m = int(report_month[:4]), int(report_month[5:7])
    fy_start = y if m >= 4 else y - 1

    jan1 = f"{fy_start - 1}-01"
    jan2 = f"{fy_start}-01"
    apr  = f"{fy_start}-04"
    rep  = report_month
    nxt  = _add_months(report_month, 1)

    fy_cols = [apr]
    mid = []
    cm = _add_months(apr, 1)
    while cm < rep:
        mid.append(cm)
        cm = _add_months(cm, 1)

    if rep != apr:
        fy_cols.append(rep)
    fy_cols.append(nxt)

    free = TARGET_MONTH_COLS - 2 - len(fy_cols)

    if mid and free > 0:
        if len(mid) <= free:
            keep = mid
        else:
            data = _load_stock(cur, mid)
            inv = {}
            for mm in mid:
                tot = _nsum(*[_derived(data, mm, p)["tot_inv"] for p in PLANTS])
                inv[mm] = tot if tot is not None else 0
            hi = max(mid, key=lambda x: inv[x])
            lo = min(mid, key=lambda x: inv[x])
            keep = {hi, lo}
            for mm in reversed(mid):
                if len(keep) >= free:
                    break
                keep.add(mm)
            keep = sorted(keep)
        fy_cols = sorted(set(fy_cols) | set(keep))
        free = TARGET_MONTH_COLS - 2 - len(fy_cols)

    pad = []
    pm = _add_months(apr, -1)
    while free > 0 and pm > jan2:
        pad.insert(0, pm)
        pm = _add_months(pm, -1)
        free -= 1

    months = [jan1, jan2] + pad + sorted(set(fy_cols))
    return months, apr, nxt


# ── section assembly ──────────────────────────────────────────────────────────

def _row(sub, plant, vals, apr_i, nxt_i, bold=False, sail=False):
    var = None
    if vals[nxt_i] is not None and vals[apr_i] is not None:
        var = vals[nxt_i] - vals[apr_i]
    return {
        "sub": sub, "plant": plant, "bold": bold, "sail": sail,
        "values": [_fmt(v) for v in vals],
        "var": _fmt(var) if var is not None else "",
    }


def generate_opening_stock(report_month: str) -> dict:
    conn = db.connect()
    cur  = conn.cursor()
    try:
        months, apr, nxt = _select_months(cur, report_month)
        apr_i, nxt_i = months.index(apr), months.index(nxt)
        data = _load_stock(cur, months)

        D = {m: {p: _derived(data, m, p) for p in PLANTS} for m in months}
        for m in months:
            D[m]["SAIL"] = {k: _nsum(*[D[m][p][k] for p in PLANTS])
                            for k in D[m][PLANTS[0]]}

        def vals(p, key):
            return [D[m][p][key] for m in months]

        def simple_section(label, code, key):
            rows = [_row("", p, vals(p, key), apr_i, nxt_i) for p in PLANTS]
            rows.append(_row("", "SAIL", vals("SAIL", key), apr_i, nxt_i,
                             bold=True, sail=True))
            for r in rows:
                r["plant_rowspan"] = 1
            return {"label": label, "code": code, "rows": rows}

        def split_section(label, code, key_a, key_b, item):
            sp = [p for p in PLANTS
                  if any(_g(data, m, p, item, st) is not None
                         for m in months for st in ("INPROCESS", "FOR SALE"))]
            rows = []
            for p in sp + ["SAIL"]:
                is_sail = p == "SAIL"
                va, vb = vals(p, key_a), vals(p, key_b)
                vt = [_nsum(a_, b_) for a_, b_ in zip(va, vb)]
                r_a = _row("[a] INPROCESS", p, va, apr_i, nxt_i, sail=is_sail)
                r_b = _row("[b] FOR SALE",  p, vb, apr_i, nxt_i, sail=is_sail)
                r_t = _row("TOTAL",         p, vt, apr_i, nxt_i, bold=True, sail=is_sail)
                r_a["plant_rowspan"] = 3
                r_b["plant_rowspan"] = 0
                r_t["plant_rowspan"] = 0
                rows.extend([r_a, r_b, r_t])
            return {"label": label, "code": code, "rows": rows}

        sections = [
            split_section("SLABS",                         "1",         "sl_a", "sl_b", "SLABS"),
            split_section("BLOOM/BILLETS",                 "2",         "bb_a", "bb_b", "BLOOM/BILLETS"),
            simple_section("SEMIS (For Sale)",             "3 (1b+2b)", "semis_sale"),
            simple_section("SEMIS (In process)",           "4 (1a+2a)", "semis_inp"),
            simple_section("SEMIS (Total)",                "5 (3+4)",   "semis_tot"),
            simple_section("FINISHED STEEL",               "6",         "fin"),
            simple_section("SALEABLE STEEL (Plant)",       "7 (3+6)",   "saleable"),
            simple_section("TOTAL STEEL INVENTORY (PLANT)","8 (4+7)",   "tot_inv"),
            simple_section("PIG IRON (PLANT)",             "",          "pig"),
        ]

        return {
            "title":      "OPENING STOCK AT SAIL PLANTS AND STOCKYARDS",
            "unit":       "'000T",
            "variant":    "opening_stock",
            "col_labels": [_col_label(m) for m in months],
            "var_label":  f"Var. w.r.t. {_col_label(apr)}",
            "sections":   sections,
        }
    finally:
        conn.close()
