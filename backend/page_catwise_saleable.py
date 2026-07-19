"""
Category Wise Production of Saleable Steel — pages 15, 16, 17.
Unit: '000 Tonnes. Monthly + Apr-Month cumulative data vs CPLY.
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

def _ytd_one(cur, table, plant, item, months):
    if not item:
        return None
    tot, ok = 0.0, False
    for m in months:
        v = _one(cur, table, plant, item, m)
        if v is not None:
            tot += v; ok = True
    return tot if ok else None

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
    tot, ok = 0.0, False
    for it in items:
        v = _one(cur, table, plant, it, month)
        if v is not None:
            tot += v; ok = True
    return tot if ok else None

def _ytd_sum_items(cur, table, plant, items, months):
    tot, ok = 0.0, False
    for it in items:
        v = _ytd_one(cur, table, plant, it, months)
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


def _row(label, rtype, ann, m_plan, m_act, cply,
         cum_plan=None, cum_act=None, cum_cply=None, indent=0, category=""):
    if rtype == "pct":
        return {"label": label, "type": rtype, "indent": indent,
                "ann_plan": ann or "", "m_plan": m_plan or "",
                "m_act": m_act or "", "m_pct": "",
                "cply_act": cply or "", "m_growth": "",
                "cum_plan": cum_plan or "", "cum_act": cum_act or "", "cum_pct": "",
                "cum_cply": cum_cply or "", "cum_growth": "",
                "category": category}
    return {"label": label, "type": rtype, "indent": indent,
            "ann_plan":   _fmt(ann),
            "m_plan":     _fmt(m_plan),
            "m_act":      _fmt(m_act),
            "m_pct":      _ipct(m_act, m_plan),
            "cply_act":   _fmt(cply),
            "m_growth":   _igr(m_act, cply),
            "cum_plan":   _fmt(cum_plan),
            "cum_act":    _fmt(cum_act),
            "cum_pct":    _ipct(cum_act, cum_plan),
            "cum_cply":   _fmt(cum_cply),
            "cum_growth": _igr(cum_act, cum_cply),
            "category":   category}

def _zero_row(label, ann=None, m_plan=None, rtype="data", indent=0, category=""):
    return {"label": label, "type": rtype, "indent": indent,
            "ann_plan": _fmt(ann) if ann is not None else "0",
            "m_plan":   _fmt(m_plan) if m_plan is not None else "0",
            "m_act": "0", "m_pct": "", "cply_act": "0", "m_growth": "",
            "cum_plan": "0", "cum_act": "0", "cum_pct": "",
            "cum_cply": "0", "cum_growth": "",
            "category": category}

def _sep():
    return {"label": "", "type": "separator", "category": ""}

def _section_hdr(label):
    return {"label": label, "type": "section-hdr", "category": ""}


def _is_nil(row):
    if row.get("type") != "data":
        return False
    def z(v): return v in ("", "0", None)
    return (z(row.get("m_act")) and z(row.get("m_plan")) and
            z(row.get("cum_act")) and z(row.get("cum_plan")) and
            z(row.get("cply_act")))


def _compute_cat_rowspans(rows):
    i = 0
    while i < len(rows):
        cat = rows[i].get("category", "")
        if cat:
            j = i + 1
            while j < len(rows) and rows[j].get("category", "") == cat:
                j += 1
            span = j - i
            for k in range(i, j):
                rows[k]["cat_first"]   = (k == i)
                rows[k]["cat_rowspan"] = span if k == i else 0
            i = j
        else:
            rows[i]["cat_first"]   = False
            rows[i]["cat_rowspan"] = 0
            i += 1
    return rows


# ── plant-specific row builders ───────────────────────────────────────────────

def _bsp(cur, rm, pm, fy, ytd, cply_ytd):
    rows = []

    # Wire Rod Mill and Merchant Mill each split into two product groups —
    # WRM's split is manual (source report only has a WRM total; TMT Coils is
    # entered and Others derived — see data-entry/bsp-mm-wrm-split), MM's is
    # extracted directly from two source cells (excel_extractor_bsp.py), with
    # "MM" itself re-derived as their sum. The mill row stays the on-report
    # total in both cases; the two group rows underneath break it down.
    for label, item, sub in [
        ("Wire Rods",           "WIRERODS", [("&nbsp;&nbsp;TMT Coils (WRM)", "TMT COILS(WRM)"),
                                              ("&nbsp;&nbsp;Others (WRM)",    "OTHERS(WRM)")]),
        ("Rounds & Bars (MM)",  "MM",       [("&nbsp;&nbsp;TMT Bars (MM)",   "TMT BARS(MM)"),
                                              ("&nbsp;&nbsp;Lt Strs (MM)",    "LT STRS(MM)")]),
        ("Rounds & Bars (BRM)", "BARS&RODMILL", []),
        ("Rail (RSM)",          "RSM_RAIL", []),
        ("Rail (URM)",          "URM_RAIL", []),
    ]:
        rows.append(_row(label, "data",
                         _ann(cur, "BSP", item, fy),
                         _one(cur, "plan", "BSP", item, rm),
                         _one(cur, "act",  "BSP", item, rm),
                         _one(cur, "act",  "BSP", item, pm),
                         _ytd_one(cur, "plan", "BSP", item, ytd),
                         _ytd_one(cur, "act",  "BSP", item, ytd),
                         _ytd_one(cur, "act",  "BSP", item, cply_ytd),
                         category="LONG"))
        for sub_label, sub_item in sub:
            rows.append(_row(sub_label, "data",
                             _ann(cur, "BSP", sub_item, fy),
                             _one(cur, "plan", "BSP", sub_item, rm),
                             _one(cur, "act",  "BSP", sub_item, rm),
                             _one(cur, "act",  "BSP", sub_item, pm),
                             _ytd_one(cur, "plan", "BSP", sub_item, ytd),
                             _ytd_one(cur, "act",  "BSP", sub_item, ytd),
                             _ytd_one(cur, "act",  "BSP", sub_item, cply_ytd),
                             category="LONG"))

    rows.append(_zero_row("Hy.Struls.", category="LONG"))

    rows.append(_row("Plates", "data",
                     _ann(cur, "BSP", "PLATEMILL", fy),
                     _one(cur, "plan", "BSP", "PLATEMILL", rm),
                     _one(cur, "act",  "BSP", "PLATEMILL", rm),
                     _one(cur, "act",  "BSP", "PLATEMILL", pm),
                     _ytd_one(cur, "plan", "BSP", "PLATEMILL", ytd),
                     _ytd_one(cur, "act",  "BSP", "PLATEMILL", ytd),
                     _ytd_one(cur, "act",  "BSP", "PLATEMILL", cply_ytd),
                     category="FLAT"))

    rows.append(_row("Semis Total", "data",
                     _ann(cur, "BSP", "Saleable Semis", fy),
                     _one(cur, "plan", "BSP", "Saleable Semis", rm),
                     _one(cur, "act",  "BSP", "Saleable Semis", rm),
                     _one(cur, "act",  "BSP", "Saleable Semis", pm),
                     _ytd_one(cur, "plan", "BSP", "Saleable Semis", ytd),
                     _ytd_one(cur, "act",  "BSP", "Saleable Semis", ytd),
                     _ytd_one(cur, "act",  "BSP", "Saleable Semis", cply_ytd),
                     category="SEMIS"))

    rows.append(_sep())
    flat_items = ["PLATEMILL"]
    rows.append(_row("Total Flat products", "subtotal",
                     _ann_sum(cur, "BSP", flat_items, fy),
                     _sum_items(cur, "plan", "BSP", flat_items, rm),
                     _sum_items(cur, "act",  "BSP", flat_items, rm),
                     _sum_items(cur, "act",  "BSP", flat_items, pm),
                     _ytd_sum_items(cur, "plan", "BSP", flat_items, ytd),
                     _ytd_sum_items(cur, "act",  "BSP", flat_items, ytd),
                     _ytd_sum_items(cur, "act",  "BSP", flat_items, cply_ytd)))

    return _append_totals(rows, cur, "BSP", rm, pm, fy, ytd, cply_ytd)


def _dsp(cur, rm, pm, fy, ytd, cply_ytd):
    rows = []

    rows.append(_row("SEMIS", "section-data",
                     _ann(cur, "DSP", "Saleable Semis", fy),
                     _one(cur, "plan", "DSP", "Saleable Semis", rm),
                     _one(cur, "act",  "DSP", "Saleable Semis", rm),
                     _one(cur, "act",  "DSP", "Saleable Semis", pm),
                     _ytd_one(cur, "plan", "DSP", "Saleable Semis", ytd),
                     _ytd_one(cur, "act",  "DSP", "Saleable Semis", ytd),
                     _ytd_one(cur, "act",  "DSP", "Saleable Semis", cply_ytd)))

    rows.append(_section_hdr("FINISHED STEEL"))

    for label, item in [
        ("Rounds-Total",        "MM"),
        ("  Merchant Mill-TMT", "MM"),
    ]:
        rows.append(_row(label, "data",
                         _ann(cur, "DSP", "MM", fy),
                         _one(cur, "plan", "DSP", "MM", rm),
                         _one(cur, "act",  "DSP", "MM", rm),
                         _one(cur, "act",  "DSP", "MM", pm),
                         _ytd_one(cur, "plan", "DSP", "MM", ytd),
                         _ytd_one(cur, "act",  "DSP", "MM", ytd),
                         _ytd_one(cur, "act",  "DSP", "MM", cply_ytd),
                         category="LONG"))

    for label, item in [
        ("Med.Structurals Total", "MSM"),
        ("  MSM",                 "MSM"),
    ]:
        rows.append(_row(label, "data",
                         _ann(cur, "DSP", "MSM", fy),
                         _one(cur, "plan", "DSP", "MSM", rm),
                         _one(cur, "act",  "DSP", "MSM", rm),
                         _one(cur, "act",  "DSP", "MSM", pm),
                         _ytd_one(cur, "plan", "DSP", "MSM", ytd),
                         _ytd_one(cur, "act",  "DSP", "MSM", ytd),
                         _ytd_one(cur, "act",  "DSP", "MSM", cply_ytd),
                         category="LONG"))

    rows.append(_row("Wheel & Axles", "data",
                     _ann(cur, "DSP", "WAP", fy),
                     _one(cur, "plan", "DSP", "WAP", rm),
                     _one(cur, "act",  "DSP", "WAP", rm),
                     _one(cur, "act",  "DSP", "WAP", pm),
                     _ytd_one(cur, "plan", "DSP", "WAP", ytd),
                     _ytd_one(cur, "act",  "DSP", "WAP", ytd),
                     _ytd_one(cur, "act",  "DSP", "WAP", cply_ytd),
                     category="LONG"))

    rows.append(_zero_row("Total Flat products", ann=0, m_plan=0, rtype="subtotal"))

    return _append_totals(rows, cur, "DSP", rm, pm, fy, ytd, cply_ytd,
                          saleable_label="Total Saleable Steel")


def _rsp(cur, rm, pm, fy, ytd, cply_ytd):
    rows = []

    rows.append(_zero_row("SEMIS", ann=0, m_plan=0, rtype="section-data"))
    rows.append(_section_hdr("FINISHED STEEL"))

    flat_items = ["OPM Plate", "NPM Plate", "HSM-2 HR Plate", "HSM-2 HR Coil (Sale)"]
    pet_items  = ["ERW Pipes", "SW Pipes", "CRNO Coils"]

    for label, item in [
        ("PM Plates",     "OPM Plate"),
        ("New PM Plates", "NPM Plate"),
        ("HR Plates",     "HSM-2 HR Plate"),
        ("HR Coils",      "HSM-2 HR Coil (Sale)"),
    ]:
        rows.append(_row(label, "data",
                         _ann(cur, "RSP", item, fy),
                         _one(cur, "plan", "RSP", item, rm),
                         _one(cur, "act",  "RSP", item, rm),
                         _one(cur, "act",  "RSP", item, pm),
                         _ytd_one(cur, "plan", "RSP", item, ytd),
                         _ytd_one(cur, "act",  "RSP", item, ytd),
                         _ytd_one(cur, "act",  "RSP", item, cply_ytd),
                         category="FLAT"))

    rows.append(_zero_row("CR Coils/Sheets", rtype="data", category="FLAT"))
    rows.append(_zero_row("GP/GC Sheets",    rtype="data", category="FLAT"))

    for label, item in [
        ("ERW Pipes", "ERW Pipes"),
        ("SW Pipes",  "SW Pipes"),
    ]:
        rows.append(_row(label, "data",
                         _ann(cur, "RSP", item, fy),
                         _one(cur, "plan", "RSP", item, rm),
                         _one(cur, "act",  "RSP", item, rm),
                         _one(cur, "act",  "RSP", item, pm),
                         _ytd_one(cur, "plan", "RSP", item, ytd),
                         _ytd_one(cur, "act",  "RSP", item, ytd),
                         _ytd_one(cur, "act",  "RSP", item, cply_ytd),
                         category="PET"))

    rows.append(_zero_row("Tin plates", rtype="data", category="PET"))

    rows.append(_row("CRNO", "data",
                     _ann(cur, "RSP", "CRNO Coils", fy),
                     _one(cur, "plan", "RSP", "CRNO Coils", rm),
                     _one(cur, "act",  "RSP", "CRNO Coils", rm),
                     _one(cur, "act",  "RSP", "CRNO Coils", pm),
                     _ytd_one(cur, "plan", "RSP", "CRNO Coils", ytd),
                     _ytd_one(cur, "act",  "RSP", "CRNO Coils", ytd),
                     _ytd_one(cur, "act",  "RSP", "CRNO Coils", cply_ytd),
                     category="PET"))

    rows.append(_sep())
    rows.append(_row("Total Flat products", "subtotal",
                     _ann_sum(cur, "RSP", flat_items, fy),
                     _sum_items(cur, "plan", "RSP", flat_items, rm),
                     _sum_items(cur, "act",  "RSP", flat_items, rm),
                     _sum_items(cur, "act",  "RSP", flat_items, pm),
                     _ytd_sum_items(cur, "plan", "RSP", flat_items, ytd),
                     _ytd_sum_items(cur, "act",  "RSP", flat_items, ytd),
                     _ytd_sum_items(cur, "act",  "RSP", flat_items, cply_ytd)))

    rows.append(_sep())
    rows.append(_row("Total PET", "subtotal",
                     _ann_sum(cur, "RSP", pet_items, fy),
                     _sum_items(cur, "plan", "RSP", pet_items, rm),
                     _sum_items(cur, "act",  "RSP", pet_items, rm),
                     _sum_items(cur, "act",  "RSP", pet_items, pm),
                     _ytd_sum_items(cur, "plan", "RSP", pet_items, ytd),
                     _ytd_sum_items(cur, "act",  "RSP", pet_items, ytd),
                     _ytd_sum_items(cur, "act",  "RSP", pet_items, cply_ytd)))

    return _append_totals(rows, cur, "RSP", rm, pm, fy, ytd, cply_ytd,
                          saleable_label="Total Saleable Steel")


def _bsl(cur, rm, pm, fy, ytd, cply_ytd):
    rows = []

    rows.append(_row("SEMIS", "section-data",
                     _ann(cur, "BSL", "Saleable Semis", fy),
                     _one(cur, "plan", "BSL", "Saleable Semis", rm),
                     _one(cur, "act",  "BSL", "Saleable Semis", rm),
                     _one(cur, "act",  "BSL", "Saleable Semis", pm),
                     _ytd_one(cur, "plan", "BSL", "Saleable Semis", ytd),
                     _ytd_one(cur, "act",  "BSL", "Saleable Semis", ytd),
                     _ytd_one(cur, "act",  "BSL", "Saleable Semis", cply_ytd)))

    rows.append(_section_hdr("FINISHED STEEL"))

    flat_items_bsl = ["HSM HR Coil (Sale)", "HSM HR Plate", "HR Sheet",
                      "CRC&S(1&2)", "CRC(3)", "GP/GC", "GPC3"]

    for label, item in [
        ("HR Coils",               "HSM HR Coil (Sale)"),
        ("HR Plates",              "HSM HR Plate"),
        ("HR Sheets",              "HR Sheet"),
        ("CR Coils",               "CRC&S(1&2)"),
        ("New CR Coils",           "CRC(3)"),
    ]:
        rows.append(_row(label, "data",
                         _ann(cur, "BSL", item, fy),
                         _one(cur, "plan", "BSL", item, rm),
                         _one(cur, "act",  "BSL", item, rm),
                         _one(cur, "act",  "BSL", item, pm),
                         _ytd_one(cur, "plan", "BSL", item, ytd),
                         _ytd_one(cur, "act",  "BSL", item, ytd),
                         _ytd_one(cur, "act",  "BSL", item, cply_ytd),
                         category="FLAT"))

    rows.append(_zero_row("CR Sheets",    rtype="data", category="FLAT"))
    rows.append(_zero_row("New CR Sheet", rtype="data", category="FLAT"))

    rows.append(_row("Thick Plates", "data",
                     _ann(cur, "BSL", "CRSALE", fy),
                     _one(cur, "plan", "BSL", "CRSALE", rm),
                     _one(cur, "act",  "BSL", "CRSALE", rm),
                     _one(cur, "act",  "BSL", "CRSALE", pm),
                     _ytd_one(cur, "plan", "BSL", "CRSALE", ytd),
                     _ytd_one(cur, "act",  "BSL", "CRSALE", ytd),
                     _ytd_one(cur, "act",  "BSL", "CRSALE", cply_ytd),
                     category="FLAT"))

    for label, item in [
        ("GP/GC Sheets",           "GP/GC"),
        ("GP/GC Sheets (New CRM)", "GPC3"),
    ]:
        rows.append(_row(label, "data",
                         _ann(cur, "BSL", item, fy),
                         _one(cur, "plan", "BSL", item, rm),
                         _one(cur, "act",  "BSL", item, rm),
                         _one(cur, "act",  "BSL", item, pm),
                         _ytd_one(cur, "plan", "BSL", item, ytd),
                         _ytd_one(cur, "act",  "BSL", item, ytd),
                         _ytd_one(cur, "act",  "BSL", item, cply_ytd),
                         category="FLAT"))

    rows.append(_zero_row("TMBP", rtype="data", category="FLAT"))

    rows.append(_sep())
    rows.append(_row("Total Flat products", "subtotal",
                     _ann_sum(cur, "BSL", flat_items_bsl, fy),
                     _sum_items(cur, "plan", "BSL", flat_items_bsl, rm),
                     _sum_items(cur, "act",  "BSL", flat_items_bsl, rm),
                     _sum_items(cur, "act",  "BSL", flat_items_bsl, pm),
                     _ytd_sum_items(cur, "plan", "BSL", flat_items_bsl, ytd),
                     _ytd_sum_items(cur, "act",  "BSL", flat_items_bsl, ytd),
                     _ytd_sum_items(cur, "act",  "BSL", flat_items_bsl, cply_ytd)))

    return _append_totals(rows, cur, "BSL", rm, pm, fy, ytd, cply_ytd,
                          saleable_label="Total Saleable Steel")


def _isp(cur, rm, pm, fy, ytd, cply_ytd):
    rows = []

    rows.append(_row("SEMIS", "section-data",
                     _ann(cur, "ISP", "Saleable Semis", fy),
                     _one(cur, "plan", "ISP", "Saleable Semis", rm),
                     _one(cur, "act",  "ISP", "Saleable Semis", rm),
                     _one(cur, "act",  "ISP", "Saleable Semis", pm),
                     _ytd_one(cur, "plan", "ISP", "Saleable Semis", ytd),
                     _ytd_one(cur, "act",  "ISP", "Saleable Semis", ytd),
                     _ytd_one(cur, "act",  "ISP", "Saleable Semis", cply_ytd)))

    rows.append(_section_hdr("FINISHED STEEL"))

    for label, item in [
        ("Rounds & Bars",  "BARMILL"),
        ("Wire rods",      "WRMILL"),
        ("Hy Structurals", "USMILL"),
    ]:
        rows.append(_row(label, "data",
                         _ann(cur, "ISP", item, fy),
                         _one(cur, "plan", "ISP", item, rm),
                         _one(cur, "act",  "ISP", item, rm),
                         _one(cur, "act",  "ISP", item, pm),
                         _ytd_one(cur, "plan", "ISP", item, ytd),
                         _ytd_one(cur, "act",  "ISP", item, ytd),
                         _ytd_one(cur, "act",  "ISP", item, cply_ytd),
                         category="LONG"))

    rows.append(_zero_row("Lt Structurals",  rtype="data", category="LONG"))
    rows.append(_zero_row("Med.Structurals", rtype="data", category="LONG"))
    rows.append(_zero_row("Light Rails",     rtype="data", category="LONG"))
    rows.append(_zero_row("Total Flat products", ann=0, m_plan=0, rtype="subtotal"))

    return _append_totals(rows, cur, "ISP", rm, pm, fy, ytd, cply_ytd,
                          saleable_label="Total Saleable Steel")


def _append_totals(rows, cur, plant, rm, pm, fy, ytd, cply_ytd,
                   saleable_label="Saleable Steel"):
    fs_ann       = _ann(cur, plant, "Finished Steel", fy)
    fs_plan      = _one(cur, "plan", plant, "Finished Steel", rm)
    fs_act       = _one(cur, "act",  plant, "Finished Steel", rm)
    fs_cply      = _one(cur, "act",  plant, "Finished Steel", pm)
    fs_ytd_plan  = _ytd_one(cur, "plan", plant, "Finished Steel", ytd)
    fs_ytd_act   = _ytd_one(cur, "act",  plant, "Finished Steel", ytd)
    fs_ytd_cply  = _ytd_one(cur, "act",  plant, "Finished Steel", cply_ytd)

    ss_ann       = _ann(cur, plant, "Saleable Steel", fy)
    ss_plan      = _one(cur, "plan", plant, "Saleable Steel", rm)
    ss_act       = _one(cur, "act",  plant, "Saleable Steel", rm)
    ss_cply      = _one(cur, "act",  plant, "Saleable Steel", pm)
    ss_ytd_plan  = _ytd_one(cur, "plan", plant, "Saleable Steel", ytd)
    ss_ytd_act   = _ytd_one(cur, "act",  plant, "Saleable Steel", ytd)
    ss_ytd_cply  = _ytd_one(cur, "act",  plant, "Saleable Steel", cply_ytd)

    rows = [r for r in rows if not _is_nil(r)]

    rows.append(_sep())
    rows.append(_row("Total Finished Steel", "subtotal",
                     fs_ann, fs_plan, fs_act, fs_cply,
                     fs_ytd_plan, fs_ytd_act, fs_ytd_cply))

    def _pp(a, b): return "" if not a or not b or b == 0 else str(int(math.floor(a / b * 100 + 0.5)))
    rows.append({
        "label": "(% of Tot. Sal. Steel)", "type": "pct", "indent": 0,
        "ann_plan":   _pp(fs_ann, ss_ann),
        "m_plan":     _pp(fs_plan, ss_plan),
        "m_act":      _pp(fs_act, ss_act),      "m_pct": "",
        "cply_act":   _pp(fs_cply, ss_cply),    "m_growth": "",
        "cum_plan":   _pp(fs_ytd_plan, ss_ytd_plan),
        "cum_act":    _pp(fs_ytd_act, ss_ytd_act), "cum_pct": "",
        "cum_cply":   _pp(fs_ytd_cply, ss_ytd_cply), "cum_growth": "",
        "category": ""
    })

    rows.append(_sep())
    rows.append(_row(saleable_label, "total",
                     ss_ann, ss_plan, ss_act, ss_cply,
                     ss_ytd_plan, ss_ytd_act, ss_ytd_cply))

    _compute_cat_rowspans(rows)
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
    prev_month  = db.get_cply_month(report_month)
    fy_months   = db.get_fy_months(report_month)
    ytd_months  = db.get_ytd_months(report_month)
    cply_ytd    = [f"{int(m[:4])-1}{m[4:]}" for m in ytd_months]

    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()
    try:
        result = []
        for plant in plants:
            fn = _BUILDERS.get(plant)
            if fn:
                rows = fn(cur, report_month, prev_month, fy_months, ytd_months, cply_ytd)
                result.append({"plant": plant, "label": _PLANT_LABELS[plant], "rows": rows})
        return result
    finally:
        conn.close()
