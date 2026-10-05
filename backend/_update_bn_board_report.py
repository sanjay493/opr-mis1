"""
One-off: update Report_format/BN_ Production Q-2 and H-1'25-26 R-2.docx (the
21st Board Sub-Committee production-performance deck) from this app's DB,
Q-2'25-26/H-1'25-26 -> Q-1/Q-2/H-1 '26-27, and save as a separate file.

Scope (per explicit user decision on 2026-10-05):
  - Every numeric table (the per-plant/SAIL Q-2 and H-1 ABP/Actual/%Ful/CPLY
    Actual/%Gr tables, the MoU table, the techno-economic table) is
    recomputed from the DB for the new period.
  - The "Production during <period> was X MT (Y% of ABP)..." summary
    sentences and period-label headings tied 1:1 to those tables are updated
    to match.
  - SAIL-level "best ever" bullets (Hot Metal/Crude Steel/Saleable Steel/
    Finished Steel only) are recomputed against all-time quarter/half-year
    history.
  - Per-plant "Highlights" bullets (BF-8, SMS-3, specific mills, etc.) and
    every "why production fell short" narrative (shutdown dates, capital
    repair jobs) are explicitly LEFT AS THE OLD 25-26 TEXT, flagged for
    manual rewrite -- this is plant-specific operational knowledge with no
    source in the DB, and the user chose not to have it guessed or stripped.
  - MoU figures themselves (FY2026-27 MoU not yet available) are left
    untouched; %Ful cells that depend on MoU stay blank, matching the
    template's own existing blanks.

Finished Steel at SAIL level includes Conversion (SAIL* in do_letter.py's
terms) throughout -- current, CPLY and every historical year used for a
best-ever check -- for internal consistency (the already-filled Q-2'26-27
table in the source file uses this convention; the untouched old H-1'25-26
table happens not to, which this script treats as the inconsistency, not
the other way round).
"""
import copy
import docx

import db
import page4
import page_do_letter as pdl
import page_techno as pt
import techno_period as tp

SRC = r"C:\opr-mis1\Report_format\BN_ Production Q-2 and H-1'25-26 R-2.docx"
OUT = r"C:\opr-mis1\Report_format\BN_ Production Q-2 and H-1'26-27.docx"

ITEMS = {i["db_item"]: i for i in page4.PAGE4_ITEMS}
FS_SAIL_SET = ["BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL"]
SPECIAL_STEEL = ["ASP", "SSP", "VISL"]
SMALL_PLANTS = {"ASP", "SSP", "VISL"}

Q1_CUR = ["2026-04", "2026-05", "2026-06"]
Q2_CUR = ["2026-07", "2026-08", "2026-09"]
Q2_CPLY = ["2025-07", "2025-08", "2025-09"]
H1_CUR = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
H1_CPLY = ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]
FY_CUR = [f"2026-{m:02d}" for m in range(4, 13)] + ["2027-01", "2027-02", "2027-03"]


def conn():
    return db.connect()


# --------------------------------------------------------------------------
# Numeric computation
# --------------------------------------------------------------------------

def _period_sum(cur, table, months, plant, db_item):
    cfg = ITEMS.get(db_item, {})
    fp, ss = cfg.get("five_plants", []), cfg.get("sail_set", [])
    total, found = 0.0, False
    for m in months:
        v = page4._p4_get(cur, table, m, plant, db_item, fp, ss)
        if v is not None:
            total += v
            found = True
    return total if found else None


def _conv_sum(cur, months):
    total, found = 0.0, False
    for m in months:
        c = pdl._fetch_conversion(cur, m)
        if c is not None:
            total += c
            found = True
    return total if found else None


def row_values(cur, plant, db_item, cur_months, cply_months, add_conv=False):
    """(ann, abp_period, act_period, pct_ful, cply_act, pct_gr) for one
    table row. add_conv: only true for SAIL Finished Steel."""
    ann = _period_sum(cur, "plan", FY_CUR, plant, db_item)
    abp = _period_sum(cur, "plan", cur_months, plant, db_item)
    act = _period_sum(cur, "act", cur_months, plant, db_item)
    cply = _period_sum(cur, "act", cply_months, plant, db_item)
    if add_conv:
        cv = _conv_sum(cur, cur_months) or 0.0
        cvp = _conv_sum(cur, cply_months) or 0.0
        act = None if act is None else act + cv
        cply = None if cply is None else cply + cvp
    pct = round(act / abp * 100) if (act is not None and abp) else None
    gr = round((act - cply) / cply * 100) if (act is not None and cply) else None
    return ann, abp, act, pct, cply, gr


def special_steel_plants_total(cur, table, months):
    total, found = 0.0, False
    for p in SPECIAL_STEEL:
        v = _period_sum(cur, table, months, p, "Finished Steel")
        if v is not None:
            total += v
            found = True
    return total if found else None


# -- all-time quarter/half best-ever, SAIL level, 4 core items ------------

def _fy_start_years(cur, lo=1960, hi=2026):
    return range(lo, hi + 1)


def _best_ever(cur, db_item, period_months_fn, cur_fy_start, add_conv=False):
    totals = {}
    for fy in _fy_start_years(cur, 1960, cur_fy_start):
        months = period_months_fn(fy)
        act = _period_sum(cur, "act", months, "SAIL", db_item)
        if act is None:
            continue
        if add_conv:
            cv = _conv_sum(cur, months)
            if cv is None:
                continue
            act += cv
        totals[fy] = act
    cur_v = totals.get(cur_fy_start)
    others = {fy: v for fy, v in totals.items() if fy != cur_fy_start}
    if cur_v is None or not others:
        return None
    best_fy = max(others, key=others.get)
    if cur_v > others[best_fy]:
        return cur_v, others[best_fy], best_fy
    return None


def _q2_months(fy):
    return [f"{fy}-07", f"{fy}-08", f"{fy}-09"]


def _h1_months(fy):
    return [f"{fy}-%02d" % m for m in range(4, 10)]


CORE_ITEMS = [
    ("Hot Metal", "Hot Metal", False),
    ("Crude Steel", "Total Crude Steel", False),
    ("Saleable Steel", "Saleable Steel", False),
    ("Finished Steel", "Finished Steel", True),
]


def sail_best_ever_bullets(cur, period_months_fn, cur_fy_start, style):
    """style: 'q2' -> 'Previous best : X MT in Q-2'YY-ZZ'
              'h1' -> 'Prev. best : X MT in Apr-Sep'YY'"""
    bullets = []
    for label, db_item, add_conv in CORE_ITEMS:
        r = _best_ever(cur, db_item, period_months_fn, cur_fy_start, add_conv)
        if not r:
            continue
        cur_v, prev_v, prev_fy = r
        cur_mt = round(cur_v / 1000.0, 3)
        prev_mt = round(prev_v / 1000.0, 3)
        yy = str(prev_fy)[2:]
        if style == "q2":
            zz = str(prev_fy + 1)[2:]
            bullets.append(f"{label} production of {cur_mt} MT (Previous best : {prev_mt} MT in Q-2'{yy}-{zz})")
        else:
            bullets.append(f"{label} production of {cur_mt} MT (Prev. best : {prev_mt} MT in Apr-Sep'{yy})")
    return bullets


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------

def fmt_tbl(v, plant):
    if v is None:
        return ""
    if plant in SMALL_PLANTS:
        return f"{v:.3f}"
    return str(round(v))


def fmt_ann(v):
    return "" if v is None else str(round(v))


def fmt_pct(v):
    return "" if v is None else str(v)


def fmt_mt(v):
    return f"{v / 1000.0:.3f}"


def fmt_t(v):
    return f"{v * 1000.0:,.0f}"


def set_cell(cell, text):
    paras = cell.paragraphs
    runs = paras[0].runs
    if runs:
        runs[0].text = text
        for r in runs[1:]:
            r.text = ""
    else:
        paras[0].add_run(text)
    for p in paras[1:]:
        el = p._p
        el.getparent().remove(el)


def set_para(paragraph, text):
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(text)
        return
    runs[0].text = text
    for r in runs[1:]:
        r.text = ""


def replace_in_para(paragraph, replacements):
    """In-place substring replacement across a paragraph's runs, preserving
    each run's own formatting (bold/italic/font) by only ever rewriting
    run.text, never touching run count or paragraph structure."""
    full = "".join(r.text for r in paragraph.runs)
    for old, new in replacements:
        full = full.replace(old, new)
    runs = paragraph.runs
    if not runs:
        return
    runs[0].text = full
    for r in runs[1:]:
        r.text = ""


# --------------------------------------------------------------------------
# Table fill
# --------------------------------------------------------------------------

def fill_period_table(table, plant, item_rows, cur_months, cply_months):
    """item_rows: [(row_index, display_item, db_item, add_conv), ...]."""
    for row_idx, _display, db_item, add_conv in item_rows:
        ann, abp, act, pct, cply, gr = row_values(cur, plant, db_item, cur_months, cply_months, add_conv)
        cells = table.rows[row_idx].cells
        set_cell(cells[1], fmt_ann(ann))
        set_cell(cells[2], fmt_tbl(abp, plant))
        set_cell(cells[3], fmt_tbl(act, plant))
        set_cell(cells[4], fmt_pct(pct))
        set_cell(cells[5], fmt_tbl(cply, plant))
        set_cell(cells[6], fmt_pct(gr))


def set_period_header(table, cur_label, cply_label):
    """Row 0 is the merged period label (repeated over the ABP/Actual/%Ful
    trio of columns); row 1 keeps its own ABP/Actual/% Ful. sub-labels and
    only gets the period-less cply/%Gr labels refreshed."""
    row0, row1 = table.rows[0].cells, table.rows[1].cells
    set_cell(row0[1], "ABP\n2026-27")
    set_cell(row1[1], "ABP\n2026-27")
    for c in (2, 3, 4):
        set_cell(row0[c], cur_label)
    set_cell(row1[2], "ABP")
    set_cell(row1[3], "Actual")
    set_cell(row1[4], "% Ful.")
    set_cell(row0[5], f"{cply_label}\nAct.")
    set_cell(row1[5], f"{cply_label}\nAct.")
    set_cell(row0[6], f"% Gr. w.r.t.\n{cply_label}")
    set_cell(row1[6], f"% Gr. w.r.t.\n{cply_label}")


# ==========================================================================
cur = None  # set in main()


def main():
    global cur
    c = conn()
    cur = c.cursor()

    doc = docx.Document(SRC)
    tables = doc.tables
    paras = doc.paragraphs

    BIG5_ITEMS = [
        (2, "Hot Metal", "Hot Metal", False),
        (3, "Crude Steel", "Total Crude Steel", False),
        (4, "Saleable Steel", "Saleable Steel", False),
        (5, "Finished Steel", "Finished Steel", False),
    ]
    SAIL_ITEMS = [
        (2, "Hot Metal", "Hot Metal", False),
        (3, "Crude Steel", "Total Crude Steel", False),
        (4, "Saleable Steel", "Saleable Steel", False),
        (5, "Finished Steel", "Finished Steel", True),
    ]
    SPECIAL2_ITEMS = [
        (2, "Crude Steel", "Total Crude Steel", False),
        (3, "Saleable Steel", "Saleable Steel", False),
        (4, "Finished Steel", "Finished Steel", False),
    ]
    VISL_ITEMS = [
        (2, "Saleable Steel", "Saleable Steel", False),
        (3, "Finished Steel", "Finished Steel", False),
    ]

    # ---- table 2: SAIL H-1'26-27 (table 1, SAIL Q-2, already done) -------
    set_period_header(tables[2], "H-1\u201926-27", "H-1\u2019\n25-26")
    fill_period_table(tables[2], "SAIL", SAIL_ITEMS, H1_CUR, H1_CPLY)

    # ---- plant tables 3-18 ------------------------------------------------
    PLANT_TABLES = [
        ("BSP", 3, 4, BIG5_ITEMS),
        ("DSP", 5, 6, BIG5_ITEMS),
        ("RSP", 7, 8, BIG5_ITEMS),
        ("BSL", 9, 10, BIG5_ITEMS),
        ("ISP", 11, 12, BIG5_ITEMS),
        ("ASP", 13, 14, SPECIAL2_ITEMS),
        ("SSP", 15, 16, SPECIAL2_ITEMS),
        ("VISL", 17, 18, VISL_ITEMS),
    ]
    for plant, q2_idx, h1_idx, item_rows in PLANT_TABLES:
        set_period_header(tables[q2_idx], "Q-2\u201926-27", "Q-2\u2019\n25-26")
        fill_period_table(tables[q2_idx], plant, item_rows, Q2_CUR, Q2_CPLY)
        set_period_header(tables[h1_idx], "H-1\u201926-27", "H-1\u2019\n25-26")
        fill_period_table(tables[h1_idx], plant, item_rows, H1_CUR, H1_CPLY)

    # ---- table 0: Finished Steel vs MoU (Actual columns only) -----------
    t0 = tables[0]
    row_plant = {2: "BSP", 3: "DSP", 4: "RSP", 5: "BSL", 6: "ISP"}
    for ridx, plant in row_plant.items():
        q1 = _period_sum(cur, "act", Q1_CUR, plant, "Finished Steel")
        q2 = _period_sum(cur, "act", Q2_CUR, plant, "Finished Steel")
        h1 = _period_sum(cur, "act", H1_CUR, plant, "Finished Steel")
        cells = t0.rows[ridx].cells
        set_cell(cells[2], fmt_ann(q1))
        set_cell(cells[4], fmt_ann(q2))
        set_cell(cells[7], fmt_ann(h1))
    # "Special Steel Plants" row (ASP+SSP+VISL)
    ssp_q1 = special_steel_plants_total(cur, "act", Q1_CUR)
    ssp_q2 = special_steel_plants_total(cur, "act", Q2_CUR)
    ssp_h1 = special_steel_plants_total(cur, "act", H1_CUR)
    cells = t0.rows[7].cells
    set_cell(cells[2], fmt_ann(ssp_q1))
    set_cell(cells[4], fmt_ann(ssp_q2))
    set_cell(cells[7], fmt_ann(ssp_h1))
    # SAIL row (5 plants + special steel + Conversion)
    sail_q1 = (_period_sum(cur, "act", Q1_CUR, "SAIL", "Finished Steel") or 0) + (_conv_sum(cur, Q1_CUR) or 0)
    sail_q2 = (_period_sum(cur, "act", Q2_CUR, "SAIL", "Finished Steel") or 0) + (_conv_sum(cur, Q2_CUR) or 0)
    sail_h1 = (_period_sum(cur, "act", H1_CUR, "SAIL", "Finished Steel") or 0) + (_conv_sum(cur, H1_CUR) or 0)
    cells = t0.rows[8].cells
    set_cell(cells[2], fmt_ann(sail_q1))
    set_cell(cells[4], fmt_ann(sail_q2))
    set_cell(cells[7], fmt_ann(sail_h1))

    # ---- table 19: techno-economic (Coke/CDI/Fuel Rate, BF Productivity) -
    techno_plants = ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"]
    params = ["Coke Rate", "CDI Rate", "Fuel Rate", "BF Productivity"]
    periods = [
        {"label": "Q2cur", "months": Q2_CUR}, {"label": "Q2cply", "months": Q2_CPLY},
        {"label": "H1cur", "months": H1_CUR}, {"label": "H1cply", "months": H1_CPLY},
    ]
    techno_res = tp.build_period_report(techno_plants, params, periods)
    techno_by_param = {s["parameter"]: s for s in techno_res["sections"]}
    targets = {}
    for plant in ["BSP", "DSP", "RSP", "BSL", "ISP"]:
        raw = pt._get_plant_techno_plan_targets(plant, "2026-09")
        targets[plant] = {k[1]: v for k, v in raw.items()}
    sail_targets_raw = pt.compute_sail_targets("2026-27")
    targets["SAIL"] = {k[1]: v for k, v in sail_targets_raw.items()}
    # Fuel Rate = Coke Rate + Nut Coke Rate + CDI Rate whenever a plant's
    # target set has no direct Fuel Rate entry but has all three components
    # -- same rule techno_aggregates.py applies to actuals.
    for plant, tgt in targets.items():
        if tgt.get("Fuel Rate") is None:
            coke, nut, cdi = tgt.get("Coke Rate"), tgt.get("Nut Coke Rate"), tgt.get("CDI Rate")
            if coke is not None and nut is not None and cdi is not None:
                tgt["Fuel Rate"] = coke + nut + cdi

    def fmt_target(param, v):
        if v is None:
            return None
        return f"{v:.2f}" if param == "BF Productivity" else str(round(v))

    t19 = tables[19]
    set_cell(t19.rows[0].cells[3], "Q-2\u201926-27")
    set_cell(t19.rows[1].cells[3], "Q-2\u201926-27")
    set_cell(t19.rows[0].cells[4], "Q-2\u2019\n25-26")
    set_cell(t19.rows[1].cells[4], "Q-2\u2019\n25-26")
    set_cell(t19.rows[0].cells[5], "H-1\u201926-27")
    set_cell(t19.rows[1].cells[5], "H-1\u201926-27")
    set_cell(t19.rows[0].cells[6], "H-1\u2019\n25-26")
    set_cell(t19.rows[1].cells[6], "H-1\u2019\n25-26")
    set_cell(t19.rows[0].cells[2], "Target\n26-27")
    set_cell(t19.rows[1].cells[2], "26-27")

    ri = 2
    for param in ["Coke Rate", "CDI Rate", "Fuel Rate", "BF Productivity"]:
        sec = techno_by_param[param]
        row_by_plant = {r["plant"]: r["values"] for r in sec["rows"]}
        for plant in techno_plants:
            cells = t19.rows[ri].cells
            vals = row_by_plant.get(plant, {})

            def disp(label):
                d = vals.get(label)
                return d["display"] if d else ""

            tgt = fmt_target(param, (targets.get(plant) or {}).get(param))
            if tgt is not None:
                set_cell(cells[2], tgt)
            set_cell(cells[3], disp("Q2cur"))
            set_cell(cells[4], disp("Q2cply"))
            set_cell(cells[5], disp("H1cur"))
            set_cell(cells[6], disp("H1cply"))
            ri += 1

    # ======================================================================
    # Paragraph text
    # ======================================================================

    def para(i):
        return paras[i]

    # -- opening Finished-Steel-vs-MoU section (P7-11): keep MoU, refresh Actual/%Ful/Growth
    fs_q2_mou, fs_h1_mou = 4.448, 8.812  # unchanged, as in the template
    _, _, fs_q2_act, _, fs_q2_cply, _ = row_values(cur, "SAIL", "Finished Steel", Q2_CUR, Q2_CPLY, add_conv=True)
    _, _, fs_h1_act, _, fs_h1_cply, _ = row_values(cur, "SAIL", "Finished Steel", H1_CUR, H1_CPLY, add_conv=True)
    fs_q2_mt, fs_h1_mt = fs_q2_act / 1000.0, fs_h1_act / 1000.0
    fs_q2_pct = round(fs_q2_mt / fs_q2_mou * 100)
    fs_h1_pct = round(fs_h1_mt / fs_h1_mou * 100)
    fs_q2_gr = round((fs_q2_act - fs_q2_cply) / fs_q2_cply * 100, 1)
    fs_h1_gr = round((fs_h1_act - fs_h1_cply) / fs_h1_cply * 100, 1)
    set_para(para(9),
             f"The Production of Finished Steel during Q-2\u201926 was {fs_q2_mt:.3f} MT ({fs_q2_pct}% of the "
             f"quarterly MoU of {fs_q2_mou} MT) with a growth of {fs_q2_gr}% over CPLY.")
    set_para(para(11),
             f"The Production of Finished Steel during April-September\u201926 was {fs_h1_mt:.3f} MT ({fs_h1_pct}% "
             f"of the Apr-Sep\u201925 MoU of {fs_h1_mou} MT), with a growth of {fs_h1_gr}% over CPLY. ")

    # -- SAIL H-1'26-27 heading + summary (P35, P37, P38) -------------------
    replace_in_para(para(35), [("H-1\u201925-26", "H-1\u201926-27")])
    replace_in_para(para(37), [("H-1\u201925-26", "H-1\u201926-27")])
    _, h1_hm_abp, h1_hm_act, h1_hm_pct, _, _ = row_values(cur, "SAIL", "Hot Metal", H1_CUR, H1_CPLY)
    _, h1_cs_abp, h1_cs_act, h1_cs_pct, _, _ = row_values(cur, "SAIL", "Total Crude Steel", H1_CUR, H1_CPLY)
    _, h1_ss_abp, h1_ss_act, h1_ss_pct, _, _ = row_values(cur, "SAIL", "Saleable Steel", H1_CUR, H1_CPLY)
    set_para(para(38),
             f"Hot Metal production during H-1\u201926-27 was {fmt_mt(h1_hm_act)} MT ({h1_hm_pct}% of ABP), Crude "
             f"Steel production was {fmt_mt(h1_cs_act)} MT ({h1_cs_pct}% of ABP) and Saleable Steel production "
             f"was {fmt_mt(h1_ss_act)} MT ({h1_ss_pct}% of ABP). ")

    # -- SAIL H-1 best-ever bullets (P43-45, template has 3 slots) ----------
    h1_bullets = sail_best_ever_bullets(cur, _h1_months, 2026, style="h1")
    slots = [43, 44, 45]
    for i, slot in enumerate(slots):
        if i < len(h1_bullets):
            set_para(para(slot), h1_bullets[i])
        else:
            # leave any unused template slot's text untouched rather than
            # delete, since paragraph indices below are addressed by number
            pass
    if len(h1_bullets) > len(slots):
        ref = para(slots[-1])
        for extra in h1_bullets[len(slots):]:
            new_p_el = copy.deepcopy(ref._p)
            ref._p.addnext(new_p_el)
            from docx.text.paragraph import Paragraph
            new_p = Paragraph(new_p_el, ref._parent)
            set_para(new_p, extra)
            ref = new_p

    # -- P48 plant-wise section title --------------------------------------
    replace_in_para(para(48), [("Q-2\u201925-26", "Q-2\u201926-27"), ("H-1\u201925-26", "H-1\u201926-27")])

    # -- per-plant Q-2/H-1 headings + summary sentences ---------------------
    def plant_summary_big(plant, months, cply_months):
        _, _, hm, hm_pct, _, _ = row_values(cur, plant, "Hot Metal", months, cply_months)
        _, _, cs, cs_pct, _, _ = row_values(cur, plant, "Total Crude Steel", months, cply_months)
        _, _, ss, ss_pct, _, _ = row_values(cur, plant, "Saleable Steel", months, cply_months)
        return (f"Hot Metal production during {{P}} was {fmt_mt(hm)} MT ({hm_pct}% of ABP), Crude Steel "
                f"production was {fmt_mt(cs)} MT ({cs_pct}% of ABP) and Saleable Steel production was "
                f"{fmt_mt(ss)} MT ({ss_pct}% of ABP). ")

    def plant_summary_small(plant, months, cply_months):
        _, _, cs, cs_pct, _, _ = row_values(cur, plant, "Total Crude Steel", months, cply_months)
        _, _, ss, ss_pct, _, _ = row_values(cur, plant, "Saleable Steel", months, cply_months)
        return (f"Crude Steel production during {{P}} was {fmt_t(cs)} T ({cs_pct}% of ABP) and Saleable Steel "
                f"production was {fmt_t(ss)} T ({ss_pct}% of ABP).")

    def plant_summary_visl(plant, months, cply_months):
        _, _, ss, ss_pct, _, _ = row_values(cur, plant, "Saleable Steel", months, cply_months)
        return f"Saleable Steel production during {{P}} was {fmt_t(ss)} T ({ss_pct}% of ABP). "

    PLANT_PARAS = {
        # plant: (q2_heading_idx, q2_summary_idx, h1_heading_idx, h1_summary_idx, summary_fn)
        "BSP": (52, 53, 73, 74, plant_summary_big),
        "DSP": (96, 97, 116, 117, plant_summary_big),
        "RSP": (129, 130, 159, 160, plant_summary_big),
        "BSL": (173, 174, 214, 215, plant_summary_big),
        "ISP": (232, 233, 264, 265, plant_summary_big),
        "ASP": (282, 283, 289, 290, plant_summary_small),
        "SSP": (295, 296, 309, 310, plant_summary_small),
        "VISL": (314, 316, 323, 325, plant_summary_visl),
    }
    for plant, (qh, qs, hh, hs, fn) in PLANT_PARAS.items():
        replace_in_para(para(qh), [("Q-2\u201925-26", "Q-2\u201926-27")])
        set_para(para(qs), fn(plant, Q2_CUR, Q2_CPLY).replace("{P}", "Q-2\u201926-27"))
        replace_in_para(para(hh), [("H-1\u201925-26", "H-1\u201926-27")])
        set_para(para(hs), fn(plant, H1_CUR, H1_CPLY).replace("{P}", "H-1\u201926-27"))

    # -- techno section title + improvement commentary ---------------------
    replace_in_para(para(329), [("Q-2\u201925-26", "Q-2\u201926-27"), ("H-1\u201925-26", "H-1\u201926-27")])
    replace_in_para(para(331), [("H-1\u201925-26", "H-1\u201926-27")])

    def improvement_pct(param, higher_is_better=False):
        sec = techno_by_param[param]
        row = next(r for r in sec["rows"] if r["plant"] == "SAIL")
        cur_v = row["values"]["H1cur"]["value"]
        cply_v = row["values"]["H1cply"]["value"]
        if higher_is_better:
            return round((cur_v - cply_v) / cply_v * 100)
        return round((cply_v - cur_v) / cply_v * 100)

    coke_imp = improvement_pct("Coke Rate")
    cdi_imp = improvement_pct("CDI Rate")
    fuel_imp = improvement_pct("Fuel Rate")
    bfp_imp = improvement_pct("BF Productivity", higher_is_better=True)

    def imp_phrase(v):
        return f"an improvement of {v}%" if v >= 0 else f"a decline of {abs(v)}%"

    set_para(para(332), f"Coke Rate: SAIL registered {imp_phrase(coke_imp)} w.r.t. CPLY.")
    set_para(para(333), f"CDI Rate: SAIL registered {imp_phrase(cdi_imp)} w.r.t. CPLY.")
    set_para(para(334), f"Fuel Rate: SAIL registered {imp_phrase(fuel_imp)} w.r.t. CPLY.")
    set_para(para(335), f"BF Productivity: SAIL registered {imp_phrase(bfp_imp)} w.r.t. CPLY.")

    doc.save(OUT)
    print("Saved:", OUT)
    c.close()


if __name__ == "__main__":
    main()
