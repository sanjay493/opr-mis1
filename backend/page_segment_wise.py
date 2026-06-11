"""
Segment Wise Production page — page 18.
Shows FLAT / PET / LONG breakdown across all 5 ISPs.
Unit: '000 Tonnes.
"""
import math
import sqlite3
import db


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

def _ann(cur, plant, item, fy):
    if not item:
        return None
    tot, ok = 0.0, False
    for m in fy:
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

def _ann_sum(cur, plant, items, fy):
    tot, ok = 0.0, False
    for it in items:
        v = _ann(cur, plant, it, fy)
        if v is not None:
            tot += v; ok = True
    return tot if ok else None

def _r(label, rtype, ann, plan, act, cply, indent=0):
    """Build a row dict."""
    if rtype == "pct":
        return {"label": label, "type": rtype, "indent": indent,
                "ann_plan": ann or "", "m_plan": plan or "",
                "m_act": act or "", "m_pct": "", "cply_act": cply or "", "m_growth": ""}
    return {"label": label, "type": rtype, "indent": indent,
            "ann_plan": _fmt(ann), "m_plan": _fmt(plan),
            "m_act": _fmt(act), "m_pct": _ipct(act, plan),
            "cply_act": _fmt(cply), "m_growth": _igr(act, cply)}

def _zero(label, ann=None, plan=None, rtype="data", indent=0):
    return {"label": label, "type": rtype, "indent": indent,
            "ann_plan": _fmt(ann) if ann is not None else "0",
            "m_plan": _fmt(plan) if plan is not None else "0",
            "m_act": "0", "m_pct": "", "cply_act": "0", "m_growth": ""}

def _sep():
    return {"label": "", "type": "separator"}

def _hdr(label):
    return {"label": label, "type": "seg-hdr"}

def _plant_lbl(plant):
    return {"label": plant, "type": "plant-lbl"}


def generate_segment_wise(report_month: str) -> dict:
    prev_month = db.get_cply_month(report_month)
    fy         = db.get_fy_months(report_month)

    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()

    rows = []

    try:
        # ── FLAT ─────────────────────────────────────────────────────────────
        rows.append(_hdr("FLAT"))

        # BSP — plates only
        rows.append(_plant_lbl("BSP"))
        rows.append(_r("  Plates", "data",
                       _ann(cur,"BSP","PLATEMILL",fy),
                       _one(cur,"plan","BSP","PLATEMILL",report_month),
                       _one(cur,"act","BSP","PLATEMILL",report_month),
                       _one(cur,"act","BSP","PLATEMILL",prev_month)))

        # RSP — flat rolled items (excluding PET)
        rows.append(_plant_lbl("RSP"))
        rsp_flat_items = ["OPM Plate", "NPM Plate", "HSM-2 HR Plate", "HSM-2 HR Coil (Sale)"]
        rows.append(_zero("  Semis", ann=0, plan=0))
        for label, item in [
            ("  PM Plates",      "OPM Plate"),
            ("  New PM Plates",  "NPM Plate"),
            ("  HR Plates",      "HSM-2 HR Plate"),
            ("  HR Coils",       "HSM-2 HR Coil (Sale)"),
        ]:
            rows.append(_r(label, "data",
                           _ann(cur,"RSP",item,fy),
                           _one(cur,"plan","RSP",item,report_month),
                           _one(cur,"act","RSP",item,report_month),
                           _one(cur,"act","RSP",item,prev_month)))
        rows.append(_zero("  CR Coils/Sheets"))
        rows.append(_zero("  GP/GC Sheets"))

        # BSL — all products (incl. semis as flat plant)
        rows.append(_plant_lbl("BSL"))
        bsl_flat_items = ["HSM HR Coil (Sale)", "HSM HR Plate", "HR Sheet",
                          "CRC&S(1&2)", "CRC(3)", "GP/GC", "GPC3"]
        rows.append(_r("  Semis", "data",
                       _ann(cur,"BSL","Saleable Semis",fy),
                       _one(cur,"plan","BSL","Saleable Semis",report_month),
                       _one(cur,"act","BSL","Saleable Semis",report_month),
                       _one(cur,"act","BSL","Saleable Semis",prev_month)))
        for label, item in [
            ("  HR Coils",              "HSM HR Coil (Sale)"),
            ("  HR Plates",             "HSM HR Plate"),
            ("  HR Sheets",             "HR Sheet"),
            ("  CR Coils",              "CRC&S(1&2)"),
            ("  New CR Coils",          "CRC(3)"),
        ]:
            rows.append(_r(label, "data",
                           _ann(cur,"BSL",item,fy),
                           _one(cur,"plan","BSL",item,report_month),
                           _one(cur,"act","BSL",item,report_month),
                           _one(cur,"act","BSL",item,prev_month)))
        rows.append(_zero("  CR Sheets"))
        rows.append(_r("  Thick Plates", "data",
                       _ann(cur,"BSL","CRSALE",fy),
                       _one(cur,"plan","BSL","CRSALE",report_month),
                       _one(cur,"act","BSL","CRSALE",report_month),
                       _one(cur,"act","BSL","CRSALE",prev_month)))

        # GP/GC total for BSL = GP/GC + GPC3
        gp_ann  = (_ann(cur,"BSL","GP/GC",fy) or 0) + (_ann(cur,"BSL","GPC3",fy) or 0)
        gp_plan = ((_one(cur,"plan","BSL","GP/GC",report_month) or 0) +
                   (_one(cur,"plan","BSL","GPC3",report_month)  or 0))
        gp_act  = ((_one(cur,"act","BSL","GP/GC",report_month) or 0) +
                   (_one(cur,"act","BSL","GPC3",report_month)   or 0))
        gp_cply = ((_one(cur,"act","BSL","GP/GC",prev_month) or 0) +
                   (_one(cur,"act","BSL","GPC3",prev_month)   or 0))
        rows.append(_r("  GP/GC Sheets", "data",
                       gp_ann or None, gp_plan or None, gp_act or None, gp_cply or None))
        rows.append(_zero("  TMBP"))

        # FLAT total — BSL is a flat-products plant; use its Saleable Steel directly
        # to avoid double-counting from overlapping DB items (CRSALE vs CRC items).
        flat_act_bsp  = _one(cur,"act","BSP","PLATEMILL",report_month) or 0
        flat_act_rsp  = _sum_items(cur,"act","RSP",rsp_flat_items,report_month) or 0
        flat_act_bsl  = _one(cur,"act","BSL","Saleable Steel",report_month) or 0
        flat_act_total = flat_act_bsp + flat_act_rsp + flat_act_bsl

        flat_plan_bsp  = _one(cur,"plan","BSP","PLATEMILL",report_month) or 0
        flat_plan_rsp  = _sum_items(cur,"plan","RSP",rsp_flat_items,report_month) or 0
        flat_plan_bsl  = _one(cur,"plan","BSL","Saleable Steel",report_month) or 0
        flat_plan_total = flat_plan_bsp + flat_plan_rsp + flat_plan_bsl

        flat_ann_bsp  = _ann(cur,"BSP","PLATEMILL",fy) or 0
        flat_ann_rsp  = _ann_sum(cur,"RSP",rsp_flat_items,fy) or 0
        flat_ann_bsl  = _ann(cur,"BSL","Saleable Steel",fy) or 0
        flat_ann_total = flat_ann_bsp + flat_ann_rsp + flat_ann_bsl

        flat_cply_bsp  = _one(cur,"act","BSP","PLATEMILL",prev_month) or 0
        flat_cply_rsp  = _sum_items(cur,"act","RSP",rsp_flat_items,prev_month) or 0
        flat_cply_bsl  = _one(cur,"act","BSL","Saleable Steel",prev_month) or 0
        flat_cply_total = flat_cply_bsp + flat_cply_rsp + flat_cply_bsl

        rows.append(_sep())
        rows.append(_r("Total   Flat", "seg-total",
                       flat_ann_total or None, flat_plan_total or None,
                       flat_act_total or None, flat_cply_total or None))

        ss5_ann  = sum(filter(None,(_ann(cur,p,"Saleable Steel",fy) for p in["BSP","DSP","RSP","BSL","ISP"]))) or None
        ss5_plan = sum(filter(None,(_one(cur,"plan",p,"Saleable Steel",report_month) for p in["BSP","DSP","RSP","BSL","ISP"]))) or None
        ss5_cply = sum(filter(None,(_one(cur,"act",p,"Saleable Steel",prev_month) for p in["BSP","DSP","RSP","BSL","ISP"]))) or None

        rows.append({"label": "  Flat %", "type": "seg-pct", "indent": 0,
                     "ann_plan": _ipct(flat_ann_total or None, ss5_ann),
                     "m_plan":   _ipct(flat_plan_total or None, ss5_plan),
                     "m_act":    _ipct(flat_act_total or None,
                                       sum(filter(None,(_one(cur,"act",p,"Saleable Steel",report_month) for p in["BSP","DSP","RSP","BSL","ISP"])))),
                     "m_pct": "",
                     "cply_act": _ipct(flat_cply_total or None, ss5_cply),
                     "m_growth": ""})

        # ── PET ──────────────────────────────────────────────────────────────
        rows.append(_sep())
        rows.append(_hdr("PET"))
        rows.append(_plant_lbl("RSP"))

        pet_items = ["ERW Pipes", "SW Pipes", "CRNO Coils"]
        for label, item in [
            ("  ERW Pipes",   "ERW Pipes"),
            ("  SW Pipes",    "SW Pipes"),
        ]:
            rows.append(_r(label, "data",
                           _ann(cur,"RSP",item,fy),
                           _one(cur,"plan","RSP",item,report_month),
                           _one(cur,"act","RSP",item,report_month),
                           _one(cur,"act","RSP",item,prev_month)))
        rows.append(_zero("  Tin plates"))
        rows.append(_r("  CRNO", "data",
                       _ann(cur,"RSP","CRNO Coils",fy),
                       _one(cur,"plan","RSP","CRNO Coils",report_month),
                       _one(cur,"act","RSP","CRNO Coils",report_month),
                       _one(cur,"act","RSP","CRNO Coils",prev_month)))

        pet_act   = _sum_items(cur,"act","RSP",pet_items,report_month)
        pet_plan  = _sum_items(cur,"plan","RSP",pet_items,report_month)
        pet_ann   = _ann_sum(cur,"RSP",pet_items,fy)
        pet_cply  = _sum_items(cur,"act","RSP",pet_items,prev_month)

        rows.append(_sep())
        rows.append(_r("Total   PET", "seg-total", pet_ann, pet_plan, pet_act, pet_cply))

        ss5_act = sum(filter(None,(_one(cur,"act",p,"Saleable Steel",report_month) for p in["BSP","DSP","RSP","BSL","ISP"])))
        rows.append({"label": "  PET %", "type": "seg-pct", "indent": 0,
                     "ann_plan": _ipct(pet_ann, ss5_ann),
                     "m_plan":   _ipct(pet_plan, ss5_plan),
                     "m_act":    _ipct(pet_act, ss5_act if ss5_act else None),
                     "m_pct": "",
                     "cply_act": _ipct(pet_cply, ss5_cply),
                     "m_growth": ""})

        # ── LONG ─────────────────────────────────────────────────────────────
        rows.append(_sep())
        rows.append(_hdr("LONG"))

        # BSP long products
        rows.append(_plant_lbl("BSP"))
        rows.append(_r("  Semis", "data",
                       _ann(cur,"BSP","Saleable Semis",fy),
                       _one(cur,"plan","BSP","Saleable Semis",report_month),
                       _one(cur,"act","BSP","Saleable Semis",report_month),
                       _one(cur,"act","BSP","Saleable Semis",prev_month)))
        rows.append(_r("  Wire Rods", "data",
                       _ann(cur,"BSP","WIRERODS",fy),
                       _one(cur,"plan","BSP","WIRERODS",report_month),
                       _one(cur,"act","BSP","WIRERODS",report_month),
                       _one(cur,"act","BSP","WIRERODS",prev_month)))
        # Rounds = MM + BARS&RODMILL combined
        rnd_ann  = (_ann(cur,"BSP","MM",fy) or 0)  + (_ann(cur,"BSP","BARS&RODMILL",fy) or 0)
        rnd_plan = ((_one(cur,"plan","BSP","MM",report_month) or 0) +
                    (_one(cur,"plan","BSP","BARS&RODMILL",report_month) or 0))
        rnd_act  = ((_one(cur,"act","BSP","MM",report_month) or 0) +
                    (_one(cur,"act","BSP","BARS&RODMILL",report_month) or 0))
        rnd_cply = ((_one(cur,"act","BSP","MM",prev_month) or 0) +
                    (_one(cur,"act","BSP","BARS&RODMILL",prev_month) or 0))
        rows.append(_r("  Rounds", "data",
                       rnd_ann or None, rnd_plan or None, rnd_act or None, rnd_cply or None))
        rows.append(_zero("  Light Structurals"))
        rows.append(_zero("  Heavy Structural"))
        # Saleable Rails = RSM_RAIL + URM_RAIL
        rail_items = ["RSM_RAIL","URM_RAIL"]
        rows.append(_r("  Saleable Rails", "data",
                       _ann_sum(cur,"BSP",rail_items,fy),
                       _sum_items(cur,"plan","BSP",rail_items,report_month),
                       _sum_items(cur,"act","BSP",rail_items,report_month),
                       _sum_items(cur,"act","BSP",rail_items,prev_month)))

        # DSP long products
        rows.append(_plant_lbl("DSP"))
        rows.append(_r("  Semis", "data",
                       _ann(cur,"DSP","Saleable Semis",fy),
                       _one(cur,"plan","DSP","Saleable Semis",report_month),
                       _one(cur,"act","DSP","Saleable Semis",report_month),
                       _one(cur,"act","DSP","Saleable Semis",prev_month)))
        rows.append(_r("  Rounds", "data",
                       _ann(cur,"DSP","MM",fy),
                       _one(cur,"plan","DSP","MM",report_month),
                       _one(cur,"act","DSP","MM",report_month),
                       _one(cur,"act","DSP","MM",prev_month)))
        rows.append(_r("  Med.Structurals", "data",
                       _ann(cur,"DSP","MSM",fy),
                       _one(cur,"plan","DSP","MSM",report_month),
                       _one(cur,"act","DSP","MSM",report_month),
                       _one(cur,"act","DSP","MSM",prev_month)))
        rows.append(_r("  Wheel & Axles", "data",
                       _ann(cur,"DSP","WAP",fy),
                       _one(cur,"plan","DSP","WAP",report_month),
                       _one(cur,"act","DSP","WAP",report_month),
                       _one(cur,"act","DSP","WAP",prev_month)))

        # ISP long products
        rows.append(_plant_lbl("ISP"))
        rows.append(_r("  Semis", "data",
                       _ann(cur,"ISP","Saleable Semis",fy),
                       _one(cur,"plan","ISP","Saleable Semis",report_month),
                       _one(cur,"act","ISP","Saleable Semis",report_month),
                       _one(cur,"act","ISP","Saleable Semis",prev_month)))
        rows.append(_r("  Bars & Rods", "data",
                       _ann(cur,"ISP","BARMILL",fy),
                       _one(cur,"plan","ISP","BARMILL",report_month),
                       _one(cur,"act","ISP","BARMILL",report_month),
                       _one(cur,"act","ISP","BARMILL",prev_month)))
        rows.append(_zero("  Light Structurals"))
        rows.append(_zero("  Med.Structurals"))
        rows.append(_r("  Wire rods", "data",
                       _ann(cur,"ISP","WRMILL",fy),
                       _one(cur,"plan","ISP","WRMILL",report_month),
                       _one(cur,"act","ISP","WRMILL",report_month),
                       _one(cur,"act","ISP","WRMILL",prev_month)))
        rows.append(_r("  Heavy Structurals", "data",
                       _ann(cur,"ISP","USMILL",fy),
                       _one(cur,"plan","ISP","USMILL",report_month),
                       _one(cur,"act","ISP","USMILL",report_month),
                       _one(cur,"act","ISP","USMILL",prev_month)))
        rows.append(_zero("  Light rails"))

        # LONG total = 5 ISPs SS - FLAT - PET
        ss5_act_full = sum((_one(cur,"act",p,"Saleable Steel",report_month) or 0 for p in["BSP","DSP","RSP","BSL","ISP"]))
        long_act  = ss5_act_full - (flat_act_total or 0) - (pet_act or 0)
        long_plan = (ss5_plan or 0) - (flat_plan_total or 0) - (pet_plan or 0)
        long_ann  = (ss5_ann or 0) - (flat_ann_total or 0) - (pet_ann or 0)
        long_cply = (ss5_cply or 0) - (flat_cply_total or 0) - (pet_cply or 0)

        rows.append(_sep())
        rows.append(_r("Total   Long", "seg-total",
                       long_ann or None, long_plan or None,
                       long_act or None, long_cply or None))
        rows.append({"label": "  Long %", "type": "seg-pct", "indent": 0,
                     "ann_plan": _ipct(long_ann or None, ss5_ann),
                     "m_plan":   _ipct(long_plan or None, ss5_plan),
                     "m_act":    _ipct(long_act or None, ss5_act_full or None),
                     "m_pct": "",
                     "cply_act": _ipct(long_cply or None, ss5_cply),
                     "m_growth": ""})

        # ── Grand totals ──────────────────────────────────────────────────────
        rows.append(_sep())

        # SEMI FINISHED STEEL = sum of Saleable Semis for all 5 plants
        sem_ann  = sum(filter(None,(_ann(cur,p,"Saleable Semis",fy) for p in["BSP","DSP","RSP","BSL","ISP"])))
        sem_plan = sum(filter(None,(_one(cur,"plan",p,"Saleable Semis",report_month) for p in["BSP","DSP","RSP","BSL","ISP"])))
        sem_act  = sum(filter(None,(_one(cur,"act",p,"Saleable Semis",report_month) for p in["BSP","DSP","RSP","BSL","ISP"])))
        sem_cply = sum(filter(None,(_one(cur,"act",p,"Saleable Semis",prev_month) for p in["BSP","DSP","RSP","BSL","ISP"])))
        rows.append(_r("SEMI FINISHED STEEL", "grand-total",
                       sem_ann or None, sem_plan or None, sem_act or None, sem_cply or None))

        # FINISHED STEEL = sum of Finished Steel for all 5 plants
        fs_ann  = sum(filter(None,(_ann(cur,p,"Finished Steel",fy) for p in["BSP","DSP","RSP","BSL","ISP"])))
        fs_plan = sum(filter(None,(_one(cur,"plan",p,"Finished Steel",report_month) for p in["BSP","DSP","RSP","BSL","ISP"])))
        fs_act  = sum(filter(None,(_one(cur,"act",p,"Finished Steel",report_month) for p in["BSP","DSP","RSP","BSL","ISP"])))
        fs_cply = sum(filter(None,(_one(cur,"act",p,"Finished Steel",prev_month) for p in["BSP","DSP","RSP","BSL","ISP"])))
        rows.append(_r("FINISHED STEEL", "grand-total",
                       fs_ann or None, fs_plan or None, fs_act or None, fs_cply or None))

        # 5 ISPs SALEABLE STEEL
        rows.append(_r("5 ISPs  SALEABLE STEEL", "grand-total",
                       ss5_ann, ss5_plan,
                       ss5_act_full or None, ss5_cply))

    finally:
        conn.close()

    return {"rows": rows}
