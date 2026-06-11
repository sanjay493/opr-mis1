"""
Category Wise Production of Saleable Steel — pages 15, 16, 17.
Unit: '000 Tonnes. Monthly data vs annual plan, monthly plan, CPLY.
"""
import math
import sqlite3
import db

# ── helpers ──────────────────────────────────────────────────────────────────

def _fmt(v):
    return "" if v is None else str(int(round(v)))

def _ipct(a, b):
    if a is None or b is None or b == 0:
        return ""
    return str(int(math.floor(a / b * 100 + 0.5)))

def _igr(cur_v, prev_v):
    if cur_v is None or prev_v is None or prev_v == 0:
        return ""
    return str(int(math.floor((cur_v - prev_v) / abs(prev_v) * 100 + 0.5)))

def _one(cur, table, plant, item, month):
    if not item:
        return None
    tbl = "production_table" if table == "act" else "production_plan_table"
    cur.execute(
        f"SELECT month_actual FROM {tbl} WHERE plant_name=? AND item_name=? AND report_month=?",
        (plant, item, month)
    )
    r = cur.fetchone()
    return r[0] if r and r[0] is not None else None

def _ann(cur, plant, item, fy_months):
    if not item:
        return None
    tot, ok = 0.0, False
    for m in fy_months:
        v = _one(cur, "plan", plant, item, m)
        if v is not None:
            tot += v; ok = True
    return tot if ok else None

def _sum_items(cur, table, plant, items, month):
    """Sum actuals/plan for a list of DB items."""
    tot, ok = 0.0, False
    for it in items:
        v = _one(cur, table, plant, it, month)
        if v is not None:
            tot += v; ok = True
    return tot if ok else None

def _ann_sum(cur, plant, items, fy_months):
    tot, ok = 0.0, False
    for it in items:
        v = _ann(cur, plant, it, fy_months)
        if v is not None:
            tot += v; ok = True
    return tot if ok else None

def _row(label, rtype, ann, m_plan, m_act, cply, indent=0):
    if rtype == "pct":
        return {"label": label, "type": rtype, "indent": indent,
                "ann_plan": ann or "", "m_plan": m_plan or "",
                "m_act": m_act or "", "m_pct": "", "cply_act": cply or "", "m_growth": ""}
    return {"label": label, "type": rtype, "indent": indent,
            "ann_plan": _fmt(ann), "m_plan": _fmt(m_plan),
            "m_act": _fmt(m_act), "m_pct": _ipct(m_act, m_plan),
            "cply_act": _fmt(cply), "m_growth": _igr(m_act, cply)}

def _zero_row(label, ann=None, m_plan=None, rtype="data", indent=0):
    return {"label": label, "type": rtype, "indent": indent,
            "ann_plan": _fmt(ann) if ann is not None else "0",
            "m_plan": _fmt(m_plan) if m_plan is not None else "0",
            "m_act": "0", "m_pct": "", "cply_act": "0", "m_growth": ""}

def _sep():
    return {"label": "", "type": "separator"}

def _section_hdr(label):
    return {"label": label, "type": "section-hdr"}


# ── plant-specific row builders ───────────────────────────────────────────────

def _bsp(cur, rm, pm, fy):
    rows = []

    for label, item in [
        ("Wire Rods",           "WIRERODS"),
        ("Rounds & Bars (MM)",  "MM"),
        ("Rounds & Bars (BRM)", "BARS&RODMILL"),
        ("Rail (RSM)",          "RSM_RAIL"),
        ("Rail (URM)",          "URM_RAIL"),
    ]:
        rows.append(_row(label, "data",
                         _ann(cur, "BSP", item, fy),
                         _one(cur, "plan", "BSP", item, rm),
                         _one(cur, "act",  "BSP", item, rm),
                         _one(cur, "act",  "BSP", item, pm)))

    # Hy.Struls – no production at BSP (show zeros)
    rows.append(_zero_row("Hy.Struls."))

    for label, item in [
        ("Plates",      "PLATEMILL"),
        ("Semis Total", "Saleable Semis"),
    ]:
        rows.append(_row(label, "data",
                         _ann(cur, "BSP", item, fy),
                         _one(cur, "plan", "BSP", item, rm),
                         _one(cur, "act",  "BSP", item, rm),
                         _one(cur, "act",  "BSP", item, pm)))

    rows.append(_sep())
    flat_items = ["PLATEMILL"]
    rows.append(_row("Total Flat products", "subtotal",
                     _ann_sum(cur, "BSP", flat_items, fy),
                     _sum_items(cur, "plan", "BSP", flat_items, rm),
                     _sum_items(cur, "act",  "BSP", flat_items, rm),
                     _sum_items(cur, "act",  "BSP", flat_items, pm)))

    return _append_totals(rows, cur, "BSP", rm, pm, fy)


def _dsp(cur, rm, pm, fy):
    rows = []

    # 1 SEMIS row
    sem_ann  = _ann(cur, "DSP", "Saleable Semis", fy)
    sem_plan = _one(cur, "plan", "DSP", "Saleable Semis", rm)
    sem_act  = _one(cur, "act",  "DSP", "Saleable Semis", rm)
    sem_cply = _one(cur, "act",  "DSP", "Saleable Semis", pm)
    rows.append({**_row("1   SEMIS", "section-data", sem_ann, sem_plan, sem_act, sem_cply)})

    rows.append(_section_hdr("2   FINISHED STEEL"))

    # Rounds-Total (= MM), then indented Merchant Mill-TMT (same item)
    mm_ann  = _ann(cur, "DSP", "MM", fy)
    mm_plan = _one(cur, "plan", "DSP", "MM", rm)
    mm_act  = _one(cur, "act",  "DSP", "MM", rm)
    mm_cply = _one(cur, "act",  "DSP", "MM", pm)
    rows.append(_row("    Rounds-Total",        "data", mm_ann, mm_plan, mm_act, mm_cply))
    rows.append(_row("      Merchant Mill-TMT", "data", mm_ann, mm_plan, mm_act, mm_cply, indent=1))

    # Med.Structurals Total (= MSM), then indented MSM
    msm_ann  = _ann(cur, "DSP", "MSM", fy)
    msm_plan = _one(cur, "plan", "DSP", "MSM", rm)
    msm_act  = _one(cur, "act",  "DSP", "MSM", rm)
    msm_cply = _one(cur, "act",  "DSP", "MSM", pm)
    rows.append(_row("    Med.Structurals Total", "data", msm_ann, msm_plan, msm_act, msm_cply))
    rows.append(_row("      MSM",                 "data", msm_ann, msm_plan, msm_act, msm_cply, indent=1))

    # Wheel & Axles = WAP
    rows.append(_row("    Wheel & Axles", "data",
                     _ann(cur, "DSP", "WAP", fy),
                     _one(cur, "plan", "DSP", "WAP", rm),
                     _one(cur, "act",  "DSP", "WAP", rm),
                     _one(cur, "act",  "DSP", "WAP", pm)))

    # DSP has no flat products
    rows.append(_zero_row("    Total Flat products", ann=0, m_plan=0, rtype="subtotal"))

    return _append_totals(rows, cur, "DSP", rm, pm, fy, saleable_label="Total Saleable Steel")


def _rsp(cur, rm, pm, fy):
    rows = []

    # 1 SEMIS – RSP has no semis
    rows.append(_zero_row("1   SEMIS", ann=0, m_plan=0, rtype="section-data"))
    rows.append(_section_hdr("2   FINISHED STEEL"))

    flat_items = ["OPM Plate", "NPM Plate", "HSM-2 HR Plate", "HSM-2 HR Coil (Sale)",
                  "ERW Pipes", "SW Pipes", "CRNO Coils"]

    for label, item in [
        ("    PM Plates",        "OPM Plate"),
        ("    New PM Plates",    "NPM Plate"),
        ("    HR Plates",        "HSM-2 HR Plate"),
        ("    HR Coils",         "HSM-2 HR Coil (Sale)"),
        ("    ERW Pipes",        "ERW Pipes"),
        ("    SW Pipes",         "SW Pipes"),
    ]:
        rows.append(_row(label, "data",
                         _ann(cur, "RSP", item, fy),
                         _one(cur, "plan", "RSP", item, rm),
                         _one(cur, "act",  "RSP", item, rm),
                         _one(cur, "act",  "RSP", item, pm)))

    rows.append(_zero_row("    CR Coils/Sheets", rtype="data"))
    rows.append(_zero_row("    GP/GC Sheets",    rtype="data"))
    rows.append(_zero_row("    Tin plates",      rtype="data"))

    rows.append(_row("    CRNO", "data",
                     _ann(cur, "RSP", "CRNO Coils", fy),
                     _one(cur, "plan", "RSP", "CRNO Coils", rm),
                     _one(cur, "act",  "RSP", "CRNO Coils", rm),
                     _one(cur, "act",  "RSP", "CRNO Coils", pm)))

    rows.append(_sep())
    rows.append(_row("    Total Flat products", "subtotal",
                     _ann_sum(cur, "RSP", flat_items, fy),
                     _sum_items(cur, "plan", "RSP", flat_items, rm),
                     _sum_items(cur, "act",  "RSP", flat_items, rm),
                     _sum_items(cur, "act",  "RSP", flat_items, pm)))

    return _append_totals(rows, cur, "RSP", rm, pm, fy, saleable_label="Total Saleable Steel")


def _bsl(cur, rm, pm, fy):
    rows = []

    sem_ann  = _ann(cur, "BSL", "Saleable Semis", fy)
    sem_plan = _one(cur, "plan", "BSL", "Saleable Semis", rm)
    sem_act  = _one(cur, "act",  "BSL", "Saleable Semis", rm)
    sem_cply = _one(cur, "act",  "BSL", "Saleable Semis", pm)
    rows.append({**_row("1   SEMIS", "section-data", sem_ann, sem_plan, sem_act, sem_cply)})

    rows.append(_section_hdr("2   FINISHED STEEL"))

    flat_items_bsl = ["HSM HR Coil (Sale)", "HSM HR Plate", "HR Sheet",
                      "CRC&S(1&2)", "CRC(3)", "GP/GC", "GPC3"]

    for label, item in [
        ("    HR Coils",                "HSM HR Coil (Sale)"),
        ("    HR Plates",               "HSM HR Plate"),
        ("    HR Sheets",               "HR Sheet"),
        ("    CR Coils",                "CRC&S(1&2)"),
        ("    New CR Coils",            "CRC(3)"),
    ]:
        rows.append(_row(label, "data",
                         _ann(cur, "BSL", item, fy),
                         _one(cur, "plan", "BSL", item, rm),
                         _one(cur, "act",  "BSL", item, rm),
                         _one(cur, "act",  "BSL", item, pm)))

    rows.append(_zero_row("    CR Sheets",    rtype="data"))
    rows.append(_zero_row("    New CR Sheet", rtype="data"))

    # Thick Plates — CRSALE is the closest DB item
    rows.append(_row("    Thick Plates", "data",
                     _ann(cur, "BSL", "CRSALE", fy),
                     _one(cur, "plan", "BSL", "CRSALE", rm),
                     _one(cur, "act",  "BSL", "CRSALE", rm),
                     _one(cur, "act",  "BSL", "CRSALE", pm)))

    for label, item in [
        ("    GP/GC Sheets",         "GP/GC"),
        ("    GP/GC Sheets (New CRM)", "GPC3"),
    ]:
        rows.append(_row(label, "data",
                         _ann(cur, "BSL", item, fy),
                         _one(cur, "plan", "BSL", item, rm),
                         _one(cur, "act",  "BSL", item, rm),
                         _one(cur, "act",  "BSL", item, pm)))

    rows.append(_zero_row("    TMBP", rtype="data"))

    rows.append(_sep())
    rows.append(_row("    Total Flat products", "subtotal",
                     _ann_sum(cur, "BSL", flat_items_bsl, fy),
                     _sum_items(cur, "plan", "BSL", flat_items_bsl, rm),
                     _sum_items(cur, "act",  "BSL", flat_items_bsl, rm),
                     _sum_items(cur, "act",  "BSL", flat_items_bsl, pm)))

    return _append_totals(rows, cur, "BSL", rm, pm, fy, saleable_label="Total Saleable Steel")


def _isp(cur, rm, pm, fy):
    rows = []

    sem_ann  = _ann(cur, "ISP", "Saleable Semis", fy)
    sem_plan = _one(cur, "plan", "ISP", "Saleable Semis", rm)
    sem_act  = _one(cur, "act",  "ISP", "Saleable Semis", rm)
    sem_cply = _one(cur, "act",  "ISP", "Saleable Semis", pm)
    rows.append({**_row("SEMIS", "section-data", sem_ann, sem_plan, sem_act, sem_cply)})

    rows.append(_section_hdr("FINISHED STEEL"))

    for label, item in [
        ("    Rounds & Bars",       "BARMILL"),
        ("    Wire rods",           "WRMILL"),
        ("    Hy Structurals",      "USMILL"),
    ]:
        rows.append(_row(label, "data",
                         _ann(cur, "ISP", item, fy),
                         _one(cur, "plan", "ISP", item, rm),
                         _one(cur, "act",  "ISP", item, rm),
                         _one(cur, "act",  "ISP", item, pm)))

    rows.append(_zero_row("    Lt Structurals",  rtype="data"))
    rows.append(_zero_row("    Med.Structurals", rtype="data"))
    rows.append(_zero_row("    Light Rails",     rtype="data"))
    rows.append(_zero_row("    Total Flat products", ann=0, m_plan=0, rtype="subtotal"))

    return _append_totals(rows, cur, "ISP", rm, pm, fy, saleable_label="Total Saleable Steel")


def _append_totals(rows, cur, plant, rm, pm, fy, saleable_label="Saleable Steel"):
    """Append Total Finished Steel, % row, and Saleable Steel rows."""
    fs_ann  = _ann(cur, plant, "Finished Steel", fy)
    fs_plan = _one(cur, "plan", plant, "Finished Steel", rm)
    fs_act  = _one(cur, "act",  plant, "Finished Steel", rm)
    fs_cply = _one(cur, "act",  plant, "Finished Steel", pm)

    ss_ann  = _ann(cur, plant, "Saleable Steel", fy)
    ss_plan = _one(cur, "plan", plant, "Saleable Steel", rm)
    ss_act  = _one(cur, "act",  plant, "Saleable Steel", rm)
    ss_cply = _one(cur, "act",  plant, "Saleable Steel", pm)

    rows.append(_sep())
    rows.append(_row("Total Finished Steel", "subtotal", fs_ann, fs_plan, fs_act, fs_cply))

    def _pp(a, b): return "" if not a or not b or b == 0 else str(int(math.floor(a / b * 100 + 0.5)))
    rows.append({
        "label": "(% of Tot. Sal. Steel)", "type": "pct", "indent": 0,
        "ann_plan": _pp(fs_ann, ss_ann), "m_plan": _pp(fs_plan, ss_plan),
        "m_act": _pp(fs_act, ss_act), "m_pct": "",
        "cply_act": _pp(fs_cply, ss_cply), "m_growth": ""
    })

    rows.append(_sep())
    rows.append(_row(saleable_label, "total", ss_ann, ss_plan, ss_act, ss_cply))
    return rows


# ── plant labels ─────────────────────────────────────────────────────────────

_PLANT_LABELS = {
    "BSP": "BHILAI STEEL PLANT",
    "DSP": "DURGAPUR STEEL PLANT",
    "RSP": "ROURKELA STEEL PLANT",
    "BSL": "BOKARO STEEL PLANT",
    "ISP": "IISCO STEEL PLANT",
}

_BUILDERS = {"BSP": _bsp, "DSP": _dsp, "RSP": _rsp, "BSL": _bsl, "ISP": _isp}


# ── public API ────────────────────────────────────────────────────────────────

def generate_catwise_saleable(report_month: str, plants: list) -> list:
    """Return list of plant sections for the given plant list."""
    prev_month = db.get_cply_month(report_month)
    fy_months  = db.get_fy_months(report_month)

    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()
    try:
        result = []
        for plant in plants:
            fn = _BUILDERS.get(plant)
            if fn:
                rows = fn(cur, report_month, prev_month, fy_months)
                result.append({"plant": plant, "label": _PLANT_LABELS[plant], "rows": rows})
        return result
    finally:
        conn.close()
