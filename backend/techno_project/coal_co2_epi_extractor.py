"""
Coal Consumption & Environmental Performance Indicators (EPI) Extractor —
pulls plant-level monthly figures from the EMD "Major Environmental
Performance Indicators" PDF report (2 pages):

Page 1 — "Major Environmental Performance Indicators (EPIs)" table, one
  3-row-header block per parameter (Sp. CO2 Emission / Sp. Water Consumption
  / Sp. PM Emission), each with exactly 6 data rows (BSP, DSP, RSP, BSL, ISP,
  SAIL) in that fixed order. Column layout (which month columns exist, and
  whether "Target 2026-27" / "Actual <month>" split into Existing
  Calculation# / Additional Emission* sub-columns) varies month to month —
  columns are located by their own header text/position, not fixed indices.
  We only want the "Existing Calculation" figure where a split exists (the
  WSA CO2 baseline methodology), matching the other two params which never
  split.

Page 2 — "Consumption of Coking Coal and CDI Coal" table, left ('000 T
  quantity) half only. Each plant contributes one row per month it appears
  in the report (current month, plus running FY-cumulative rows for months
  after April) - we match on the exact current-month row label (e.g.
  "May'26", not "Apr-May'26") to avoid picking up the cumulative row.

Both pages locate data by text position (`page.get_text("words")`), not by
PyMuPDF's `find_tables()` — table auto-detection was found to be unreliable
across report months here (drops plant labels non-deterministically, splits
one logical table into inconsistent fragments across the 3 sample months).

Values land in techno_data (unit='General', techno_json["month"]) via
db.merge_upsert_techno_data — plant-level only; SAIL is intentionally never
written here. The at-a-glance / major-techno pages compute SAIL for these
params as a Crude-Steel-weighted average across plants (see BF_SAIL_SPECS's
"cs"-weighted entries in page_techno.py), matching how "Specific Energy
Consumption" already works, rather than trusting the report's own SAIL row
(which the report computes with EMD's own, not necessarily identical,
weighting).

Run as a script to (re-)load a folder of these PDFs:
    python coal_co2_epi_extractor.py "D:\\opr-mis1\\Report_format\\Coal_co2"
"""
import re
import sys
from pathlib import Path

PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]

# techno_data["month"] key -> display unit, for the 7 new parameters this
# extractor is the sole source of.
ENVIRO_KEY_UNITS = {
    "sp_co2_emission":      "T/tcs",
    "sp_water_consumption": "m\u00b3/tcs",
    "sp_pm_emission":       "kg/tcs",
}
COAL_KEY_UNITS = {
    "indigenous_pcc":     "'000 T",
    "indigenous_mcc":     "'000 T",
    "imported_hard_coal": "'000 T",
    "imported_soft_coal": "'000 T",
}

# Display param name (as used in generate_major_techno_from_db /
# generate_summary_te_table / techno_plan_fy target JSON) for each of the 3
# enviro parameters, in the fixed top-to-bottom order they appear in the PDF.
ENVIRO_PARAM_ORDER = [
    ("co2",   "Sp. CO2 Emission",         "sp_co2_emission"),
    ("water", "Sp. Water Consumption",    "sp_water_consumption"),
    ("pm",    "Sp. PM Emission",          "sp_pm_emission"),
]

_FNAME_RE = re.compile(r"^([A-Za-z]{3})'?(\d{2})\.pdf$", re.IGNORECASE)
_MONTH_NUM = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
              "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


def report_month_from_filename(fname: str):
    """"Apr'26.pdf" -> ("2026-04", "Apr'26")"""
    m = _FNAME_RE.match(fname)
    if not m:
        return None
    mon, yy = m.group(1).lower(), int(m.group(2))
    if mon not in _MONTH_NUM:
        return None
    year = 2000 + yy
    return f"{year}-{_MONTH_NUM[mon]:02d}", f"{mon.capitalize()}'{yy:02d}"


_MONTH_ABBR = {v: k for k, v in _MONTH_NUM.items()}


def mlabel_from_report_month(report_month: str) -> str:
    """"2026-04" -> "Apr'26" - the exact column-header text this report uses
    for its current-month column, independent of what the uploaded file
    happens to be named. Used so a user-selected report_month drives which
    column is read; if that column isn't on the page at all (wrong month
    selected for this file), extraction fails with a clear error rather
    than silently reading the wrong column."""
    year, mon_num = report_month.split("-")
    abbr = _MONTH_ABBR[int(mon_num)]
    return f"{abbr.capitalize()}'{year[-2:]}"


def _norm(s: str) -> str:
    return s.replace("\u2019", "'")


def _words(page):
    return [(w[0], w[1], w[2], w[3], _norm(w[4])) for w in page.get_text("words")]


def _find(words, text, x_min=None, x_max=None, y_min=None, y_max=None):
    out = []
    for w in words:
        if w[4] != text:
            continue
        if x_min is not None and w[0] < x_min:
            continue
        if x_max is not None and w[0] > x_max:
            continue
        if y_min is not None and w[1] < y_min:
            continue
        if y_max is not None and w[1] > y_max:
            continue
        out.append(w)
    return out


def _col_center(words, label_variants, y_max=145):
    """x-center of the value column for a top-level header (identified by
    label_variants, e.g. the month string or "2026-27"). When that header
    has split into Existing-Calculation / Additional-Emission sub-columns
    (only ever seen for Sp. CO2 Emission, and only in some report months),
    return the Existing-Calculation sub-column's center instead - picked as
    the "Existing" sub-header word nearest this header's own center, since
    two different top-level headers can each have their own "Existing"
    sub-label only ~100pt apart and a fixed window risks grabbing the wrong
    one."""
    hits = []
    for lbl in label_variants:
        hits += _find(words, lbl, y_max=y_max)
    if not hits:
        raise ValueError(f"header label not found: {label_variants}")
    hw = sorted(hits, key=lambda w: w[1])[0]
    lx0, lx1, ly1 = hw[0], hw[2], hw[3]
    label_center = (lx0 + lx1) / 2
    exist_hits = [w for w in words if w[4] == "Existing" and ly1 <= w[1] <= ly1 + 40]
    if exist_hits:
        ew = min(exist_hits, key=lambda w: abs((w[0] + w[2]) / 2 - label_center))
        ew_center = (ew[0] + ew[2]) / 2
        if abs(ew_center - label_center) < 90:
            return ew_center
    return label_center


def _nearest_in_row(words, row_y0, row_y1, col_x, tol=40, x_max=None):
    cands = []
    for w in words:
        if not (row_y0 <= w[1] <= row_y1):
            continue
        if x_max is not None and w[0] > x_max:
            continue
        cx = (w[0] + w[2]) / 2
        if abs(cx - col_x) <= tol:
            cands.append((abs(cx - col_x), w[4]))
    if not cands:
        return None
    cands.sort(key=lambda t: t[0])
    return cands[0][1]


def extract_page1_enviro(page, mlabel) -> dict:
    """-> {"co2": {"month": {plant: val}, "target": {plant: val}}, "water": ..., "pm": ...}
    (plant keys include "SAIL" - callers should drop it; SAIL here is only
    useful as a cross-check against the plant sum, not for storage.)"""
    words = _words(page)

    label_words = [w for w in words if w[4] in (PLANTS + ["SAIL"]) and w[1] > 140 and w[0] < 350]
    label_words.sort(key=lambda w: w[1])
    if len(label_words) != 18:
        raise ValueError(f"expected 18 plant-row labels on the EPI page, got {len(label_words)}: "
                          f"{[(w[4], round(w[1], 1)) for w in label_words]}")

    target_col_x = _col_center(words, ["2026-27"])
    month_col_x = _col_center(words, [mlabel])

    blocks = {"co2": label_words[0:6], "water": label_words[6:12], "pm": label_words[12:18]}

    out = {}
    for key, row_words in blocks.items():
        month_vals, target_vals = {}, {}
        for w in row_words:
            plant = w[4]
            ry0, ry1 = w[1] - 3, w[3] + 3
            mv = _nearest_in_row(words, ry0, ry1, month_col_x)
            tv = _nearest_in_row(words, ry0, ry1, target_col_x)
            if mv is not None:
                try:
                    month_vals[plant] = float(mv)
                except ValueError:
                    pass
            if tv is not None:
                try:
                    target_vals[plant] = float(tv)
                except ValueError:
                    pass
        out[key] = {"month": month_vals, "target": target_vals}
    return out


def extract_page2_coal(page, mlabel) -> dict:
    """-> {plant: {"pcc":.., "mcc":.., "hard":.., "soft":..}} (Indigenous
    PCC/MCC, Imported Hard/Soft coking coal, '000 T) for the exact current
    month's row (not any FY-cumulative row also on the page). Includes SAIL
    (the report's own total) as a cross-check only."""
    words = _words(page)

    def hdr_x(text):
        hits = _find(words, text, x_max=400, y_max=110)
        if not hits:
            raise ValueError(f"coal-table header not found: {text}")
        w = hits[0]
        return (w[0] + w[2]) / 2

    pcc_x, mcc_x, hard_x, soft_x = hdr_x("PCC"), hdr_x("MCC"), hdr_x("Hard"), hdr_x("Soft")

    expected = PLANTS + ["SAIL"]
    month_row_hits = sorted(_find(words, mlabel, x_max=110), key=lambda w: w[1])
    if len(month_row_hits) != len(expected):
        raise ValueError(f"expected {len(expected)} '{mlabel}' rows on the coal page, got "
                          f"{len(month_row_hits)}: {[round(w[1], 1) for w in month_row_hits]}")

    out = {}
    for plant, mw in zip(expected, month_row_hits):
        ry0, ry1 = mw[1] - 3, mw[3] + 3
        vals = {}
        for name, cx in [("pcc", pcc_x), ("mcc", mcc_x), ("hard", hard_x), ("soft", soft_x)]:
            v = _nearest_in_row(words, ry0, ry1, cx, tol=25, x_max=400)
            if v is not None:
                try:
                    vals[name] = float(v)
                except ValueError:
                    pass
        out[plant] = vals
    return out


def extract_pdf(pdf_path, report_month: str, mlabel: str) -> dict:
    """Full extraction for one month's report.
    -> {"enviro": {...from extract_page1_enviro}, "coal": {...from extract_page2_coal}}"""
    import fitz
    doc = fitz.open(pdf_path)
    return {
        "enviro": extract_page1_enviro(doc[0], mlabel),
        "coal": extract_page2_coal(doc[1], mlabel),
    }


def plant_techno_json(enviro: dict, coal: dict, plant: str) -> dict:
    """techno_data["month"] dict for one plant from one month's extraction
    (SAIL deliberately excluded - see module docstring)."""
    out = {}
    for key, _label, json_key in ENVIRO_PARAM_ORDER:
        v = enviro[key]["month"].get(plant)
        if v is not None:
            out[json_key] = v
    cvals = coal.get(plant, {})
    for src_key, json_key in [("pcc", "indigenous_pcc"), ("mcc", "indigenous_mcc"),
                               ("hard", "imported_hard_coal"), ("soft", "imported_soft_coal")]:
        v = cvals.get(src_key)
        if v is not None:
            out[json_key] = v
    return out


def load_folder(folder: str, write: bool = True) -> dict:
    """Extract every "<Mon>'YY.pdf" in folder and (if write=True) merge into
    techno_data (per plant, unit='General') and techno_plan_fy (per plant +
    SAIL, unit='Shop', FY of the LAST month processed - the annual target
    column is FY-constant so any month's PDF carries the same figures).
    Returns {report_month: {"enviro":..., "coal":...}} for inspection either
    way."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import db  # noqa: E402

    results = {}
    for path in sorted(Path(folder).glob("*.pdf")):
        parsed = report_month_from_filename(path.name)
        if not parsed:
            continue
        report_month, mlabel = parsed
        results[report_month] = extract_pdf(str(path), report_month, mlabel)

    if not write:
        return results

    for report_month, blob in sorted(results.items()):
        for plant in PLANTS:
            month_json = plant_techno_json(blob["enviro"], blob["coal"], plant)
            if month_json:
                db.merge_upsert_techno_data(plant, report_month, "General",
                                             {"month": month_json, "till_month": {}},
                                             source_file=f"Coal_co2/{Path(folder).name}")

    if results:
        last_month = max(results)
        fy_num = int(last_month[:4]) if int(last_month[5:7]) >= 4 else int(last_month[:4]) - 1
        target_fy = f"{fy_num}-{(fy_num + 1) % 100:02d}"
        enviro = results[last_month]["enviro"]

        for plant in PLANTS:
            plan = db.get_techno_plant_plan(plant, target_fy)
            plan_data = dict(plan.get("data") or {})
            for key, label, _jk in ENVIRO_PARAM_ORDER:
                v = enviro[key]["target"].get(plant)
                if v is not None:
                    plan_data[label] = {"value": v, "unit": ENVIRO_KEY_UNITS[_jk]}
            db.save_techno_plant_plan(plant, target_fy, plan_data,
                                       is_user_supplied=plan.get("is_user_supplied", False),
                                       created_by="coal_co2_epi_extractor")

        sail_plan = db.get_sail_techno_plan(target_fy)
        sail_plan_data = dict(sail_plan.get("data") or {})
        for key, label, _jk in ENVIRO_PARAM_ORDER:
            v = enviro[key]["target"].get("SAIL")
            if v is not None:
                sail_plan_data[label] = {"value": v, "unit": ENVIRO_KEY_UNITS[_jk]}
        db.save_sail_techno_plan(target_fy, sail_plan_data,
                                  is_user_supplied=sail_plan.get("is_user_supplied", False),
                                  created_by="coal_co2_epi_extractor")

    return results


if __name__ == "__main__":
    import json as _json
    folder_arg = sys.argv[1] if len(sys.argv) > 1 else r"D:\opr-mis1\Report_format\Coal_co2"
    dry_run = "--dry-run" in sys.argv
    res = load_folder(folder_arg, write=not dry_run)
    print(_json.dumps(res, indent=2))
