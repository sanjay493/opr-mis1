"""Build backend/parl_annexures_history.json from the Parliament annexures
workbook (Report_format/work/HisParlia_Annexures.xlsx), sheets "hisparlia",
"ProdHIS" and "techhistoryfinal".

Every completed FY in those sheets is copied as it stands (the workbook's
cached values; Excel errors such as #REF! / #N/A / #DIV/0! become null).
The workbook's current-period column(s) (e.g. "Apr-Jun 2026-27" and its
CPLY) are kept under "reference_periods" -- page parl_annexures.py
compares the DB's figures for that period against them and lists the
deviations.

  venv/Scripts/python.exe scripts/build_parl_annexures_history.py [xlsx] [out.json]

Re-run only to re-import the workbook; the JSON is otherwise hand-edited
(add a newly closed FY there, or let the report take it from the DB).
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

DEFAULT_XLSX = r"I:\My Drive\Report_format\work\HisParlia_Annexures.xlsx"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "parl_annexures_history.json"

_FY = re.compile(r"^\d{4}-\d{2}$")
_MON = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
        "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 6)
    return None


def _period_month(fy: str, label: str) -> str:
    """'2026-27' + "Apr-Jun" -> '2026-06' (the period's last month)."""
    end = re.search(r"Apr-([A-Z][a-z]{2})", label).group(1)
    m = _MON[end]
    y = int(fy[:4]) + (1 if m < 4 else 0)
    return f"{y}-{m:02d}"


# ── hisparlia (Annexure-II) ──────────────────────────────────────────────────
# Per item block: CAP, APP, MoU, ACTUAL, %FUL APP, %FUL MoU, %GR, %CU
_PP_ITEMS = {"hm": 4, "cs": 12, "ss": 20}          # first column of each block
_PP_FIELDS = ["cap", "app", "mou", "actual", "ful_app", "ful_mou", "gr", "cu"]


def _pp(ws):
    plants, plan, period = {}, {}, {}
    plant = None
    period_month = None
    for r in range(8, ws.max_row + 1):
        b = ws.cell(r, 2).value
        if isinstance(b, str) and b.strip():
            plant = b.strip()
        year = ws.cell(r, 3).value
        if plant is None or not isinstance(year, str):
            continue
        year = year.strip()
        if year.startswith("Note"):
            break
        rec = {}
        for item, c0 in _PP_ITEMS.items():
            vals = {f: _num(ws.cell(r, c0 + i).value) for i, f in enumerate(_PP_FIELDS)}
            if ws.cell(r, c0 + 2).value == "-":
                vals["mou"] = None
            rec[item] = vals
        if _FY.match(year):
            plants.setdefault(plant, {})[year] = rec
        elif "Plan" in year:
            fy = year[:7]
            plan.setdefault(fy, {})[plant] = {i: {k: v[k] for k in ("cap", "app", "mou")}
                                              for i, v in rec.items()}
        elif "(Apr-" in year:
            fy = year[:7]
            period_month = _period_month(fy, year)
            period.setdefault(plant, rec)
    note = ws.cell(152, 3).value
    return plants, plan, period, period_month, (note or "").strip()


# ── ProdHIS ──────────────────────────────────────────────────────────────────
_PH_SECTIONS = {"HOT METAL": "hm", "CRUDE STEEL": "cs", "SAL.STEEL": "ss", "PIG IRON": "pig_iron"}
_PH_PLANT = {"SAIL -5 PL": "SAIL-5PL", "SAIL-5 PL": "SAIL-5PL"}


def _ph(ws):
    years = {}
    for c in range(4, ws.max_column + 1):
        v = ws.cell(7, c).value
        if isinstance(v, str) and _FY.match(v.strip()):
            years[c] = v.strip()
    cy_col = max(years) + 1                         # "Apr-Jun" / "2026-27"
    cply_col = cy_col + 1                           # "Apr-Jun" / "2025-26"
    label = ws.cell(7, cy_col).value.strip()
    cy_fy, cply_fy = ws.cell(9, cy_col).value.strip(), ws.cell(9, cply_col).value.strip()
    hist, cy, cply = {}, {}, {}
    item = None
    for r in range(10, ws.max_row + 1):
        b = ws.cell(r, 2).value
        if not isinstance(b, str) or not b.strip():
            continue
        b = b.strip()
        if b in _PH_SECTIONS:
            item = _PH_SECTIONS[b]
            continue
        if b.upper().startswith("PRODUCTION OF IRON"):
            break
        if item is None:
            continue
        plant = _PH_PLANT.get(b, b)
        hist.setdefault(item, {})[plant] = {fy: _num(ws.cell(r, c).value) for c, fy in years.items()}
        cy.setdefault(item, {})[plant] = _num(ws.cell(r, cy_col).value)
        cply.setdefault(item, {})[plant] = _num(ws.cell(r, cply_col).value)
    return hist, (_period_month(cy_fy, label), cy), (_period_month(cply_fy, label), cply)


# ── techhistoryfinal (Annexure-III) ──────────────────────────────────────────
_TH_SECTIONS = {"Blast furnace productivity": "bf_productivity", "Coke rate": "coke_rate",
                "Energy Consumption": "energy"}


def _th(ws):
    hist, cy, cply = {}, {}, {}
    months = {}
    r = 1
    while r <= ws.max_row:
        b = ws.cell(r, 2).value
        key = _TH_SECTIONS.get(b.strip()) if isinstance(b, str) else None
        if key is None or r > 60:
            r += 1
            continue
        hdr = r + 2
        years = {c: ws.cell(hdr, c).value.strip() for c in range(3, ws.max_column + 1)
                 if isinstance(ws.cell(hdr, c).value, str) and _FY.match(ws.cell(hdr, c).value.strip())}
        cy_col = max(years) + 1
        label = "Apr-Jun"   # V11 is a formula (=ProdHIS!W7); its period is ProdHIS's
        cy_fy = str(ws.cell(hdr + 1, cy_col).value).strip()
        cply_fy = str(ws.cell(hdr + 1, cy_col + 1).value).strip()
        months[key] = (cy_fy, cply_fy, label)
        rr = hdr + 2
        while rr <= ws.max_row:
            plant = ws.cell(rr, 2).value
            if not isinstance(plant, str) or not plant.strip():
                break
            plant = plant.strip()
            hist.setdefault(key, {})[plant] = {fy: _num(ws.cell(rr, c).value) for c, fy in years.items()}
            cy.setdefault(key, {})[plant] = _num(ws.cell(rr, cy_col).value)
            cply.setdefault(key, {})[plant] = _num(ws.cell(rr, cy_col + 1).value)
            rr += 1
        r = rr
    return hist, cy, cply, months


def build(xlsx: str) -> dict:
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    pp_plants, pp_plan, pp_period, pp_month, note = _pp(wb["hisparlia"])
    ph_hist, (ph_cy_m, ph_cy), (ph_cply_m, ph_cply) = _ph(wb["ProdHIS"])
    th_hist, th_cy, th_cply, _ = _th(wb["techhistoryfinal"])
    # techhistoryfinal's period column is ProdHIS's (its header is =ProdHIS!W7)
    refs = {}
    refs.setdefault(pp_month, {})["production_performance"] = pp_period
    refs.setdefault(ph_cy_m, {})["production_history"] = ph_cy
    refs.setdefault(ph_cply_m, {})["production_history"] = ph_cply
    refs.setdefault(ph_cy_m, {})["techno_history"] = th_cy
    refs.setdefault(ph_cply_m, {})["techno_history"] = th_cply
    return {
        "_doc": ("Hard-coded history for the Parliament annexures (/reports/parliament): every "
                 "completed FY of Report_format/work/HisParlia_Annexures.xlsx, built by "
                 "scripts/build_parl_annexures_history.py. A FY present here is shown as written; "
                 "a later FY is computed from the DB. Units: '000 T; techno: T/CuM/day, Kg/thm, "
                 "Gcal/tcs. null = blank / '-' in the workbook. reference_periods holds the "
                 "workbook's own current-period figures, which the report compares with the DB "
                 "(deviations)."),
        "source": "Report_format/work/HisParlia_Annexures.xlsx",
        "production_performance": {"note": note, "plants": pp_plants, "plan": pp_plan},
        "production_history": ph_hist,
        "techno_history": th_hist,
        "reference_periods": refs,
    }


def main():
    xlsx = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_XLSX
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    data = build(xlsx)
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
