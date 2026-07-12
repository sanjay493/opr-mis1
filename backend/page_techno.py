"""
Techno-Economic Parameter pages — pages 27-35.

Data source: techno_actuals JOIN techno_param (replaces techno_table + techno_param_master)
Display ordering: techno_param_group (group_code, sort_order)
Annual targets:   techno_target JOIN techno_param JOIN techno_param_group

Column layout:
  <FY-2> Actual | <FY-1> Actual | Target <FY> |
  Apr'YY … <report month> | <CPLY month> | Apr-<Mon>'YY | Apr-<Mon>'YY-1

Annual FY value: stored March till_month_actual only (represents full FY Apr-Mar).
                 Empty if March data not in DB (no fallback averaging).
YTD value:       stored till_month_actual if present; else computed from monthly actuals Apr→month.

SAIL row computation (MAJOR page + Summary page te_table):
  BF params (Coal/HM, Coke, Nut Coke, CDI Rate, Fuel, Sinter%, Pellet%):
      weighted average of plant values, weight = plant Hot Metal production
  BF Productivity:
      SAIL = Σ(HM) / Σ(HM / plant_BFprod)
  SMS params (HM Consumption, Scrap, TMI):
      weighted average of shop values, weight = plant Crude Steel / shops_per_plant
  Specific Energy Consumption:
      weighted average of plant values, weight = plant Crude Steel production
"""
import sqlite3
from decimal import Decimal, ROUND_HALF_UP
import db
from techno_cumulative import compute_cumulative_preview, compute_cumulative_from_values

_MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# ---------------------------------------------------------------------------
# Page registry
# ---------------------------------------------------------------------------


TECHNO_PAGES = {
    27: ("MAJOR",       "MAJOR TECHNO-ECONOMIC PARAMETERS", ""),
    28: ("COKE_SINTER", "MONTH-WISE TECHNO-ECONOMIC PARAMETERS", "COKE AND COAL CHEMICALS, SINTER PLANT"),
    29: ("IRON_MAKING", "MONTH-WISE TECHNO-ECONOMIC PARAMETERS", "IRON MAKING"),
    30: ("SMS",         "MONTH-WISE TECHNO-ECONOMIC PARAMETERS", "SMS SHOP"),
    31: ("MILL_BSP",    "MILL WISE TECHNO-ECONOMIC PARAMETERS", "Bhilai Steel Plant"),
    32: ("MILL_DSP",    "MILL WISE TECHNO-ECONOMIC PARAMETERS", "Durgapur Steel Plant"),
    33: ("MILL_RSP",    "MILL WISE TECHNO-ECONOMIC PARAMETERS", "Rourkela Steel Plant"),
    34: ("MILL_BSL",    "MILL WISE TECHNO-ECONOMIC PARAMETERS", "Bokaro Steel Plant"),
    35: ("MILL_ISP",    "MILL WISE TECHNO-ECONOMIC PARAMETERS", "IISCO Steel Plant"),
}

# ---------------------------------------------------------------------------
# SAIL weighted-average constants  (string-based, no param_ids)
# ---------------------------------------------------------------------------

_BF_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]

# BF parameters weighted by Hot Metal production
_BF_HM_PARAMS = [
    "Coal to Hot Metal", "Coke Rate", "Nut Coke Rate",
    "CDI Rate", "Fuel Rate", "Sinter in Burden", "Pellet in Burden",
]

# SMS shops and their plant mapping
_SMS_SHOPS = [
    "BSP SMS-2", "BSP SMS-3", "DSP SMS",
    "RSP SMS-1", "RSP SMS-2",
    "BSL SMS-1", "BSL SMS-2",
    "ISP SMS-1",
]
_SMS_SHOP_PLANT = {
    "BSP SMS-2": "BSP", "BSP SMS-3": "BSP", "DSP SMS": "DSP",
    "RSP SMS-1": "RSP", "RSP SMS-2": "RSP",
    "BSL SMS-1": "BSL", "BSL SMS-2": "BSL", "ISP SMS-1": "ISP",
}
_PLANT_SHOP_CNT = {"BSP": 2, "DSP": 1, "RSP": 2, "BSL": 2, "ISP": 1}

_SMS_PARAMS = ["Hot Metal Consumption", "Scrap Consumption", "TMI"]

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fy_start(report_month):
    y, m = int(report_month[:4]), int(report_month[5:7])
    return y if m >= 4 else y - 1

def _fy_months(fy):
    out = []
    for i in range(12):
        y, m = fy + (4 + i - 1) // 12, (4 + i - 1) % 12 + 1
        out.append(f"{y}-{m:02d}")
    return out

def _fy_label(fy):
    """Full FY key, e.g. "2026-27" — matches the techno_plan_fy.fy DB column
    format, so this must not be shortened (used as a DB lookup key elsewhere)."""
    return f"{fy}-{(fy + 1) % 100:02d}"

def _fy_label_short(fy):
    """Display-only short FY label, e.g. "26-27", for report table headers."""
    return f"{fy % 100:02d}-{(fy + 1) % 100:02d}"

def _mlabel(ym):
    return f"{_MON[int(ym[5:7])]}'{ym[2:4]}"

def _cum_label(months):
    if len(months) == 1:
        return _mlabel(months[0])
    return f"{_MON[int(months[0][5:7])]}-{_mlabel(months[-1])}"

def _fmt(v):
    if v is None:
        return ""
    a = abs(v)
    if a >= 100:
        return str(int(round(v)))
    if a >= 10:
        s = f"{v:.1f}"
    elif a >= 1:
        s = f"{v:.2f}"
    else:
        s = f"{v:.3f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def _round_half_up(v, decimal_places):
    """Round v to decimal_places using standard round-half-up on its DECIMAL
    representation, not its binary float bits.

    Values like 1.825 cannot be represented exactly in binary floating point
    - it's actually stored as 1.82499999999999995559..., so Python's default
    round()/f"{v:.2f}" rounds it DOWN to 1.82 (correct for the binary value,
    wrong for the decimal figure a human entered/expects). Reconstructing a
    Decimal from str(v) recovers the intended decimal digits first, then
    ROUND_HALF_UP rounds .5 the way report readers expect."""
    quantum = Decimal(1).scaleb(-decimal_places)   # e.g. Decimal('0.01') for 2 places
    return Decimal(str(v)).quantize(quantum, rounding=ROUND_HALF_UP)


def _fmt_param(v, param_name):
    """Format value based on parameter type. Hide zero values.
    - BF Productivity & Specific Energy Consumption: 2 decimal places
    - Coal to Hot Metal: 3 decimal places
    - Rest: 0 decimal places
    Always shows the fixed decimal-place count (no trailing-zero stripping).
    """
    if v is None or v == 0:
        return ""

    # Determine decimal places based on parameter
    if param_name in ("BF Productivity", "Specific Energy Consumption"):
        decimal_places = 2
    elif param_name == "Coal to Hot Metal":
        decimal_places = 3
    else:
        decimal_places = 0

    return str(_round_half_up(v, decimal_places))

# ---------------------------------------------------------------------------
# Page 3 summary TE table
# ---------------------------------------------------------------------------

def generate_summary_te_table(report_month: str) -> list:
    """Generate the te_table for the SAIL Performance Summary page (page 3).

    Values are taken from the page-27 MAJOR TECHNO table's SAIL rows so that
    page 3 always matches page 27 by construction. Columns per row:
    [Target FY, report-month actual, CPLY month, YTD cum, CPLY YTD cum].
    """
    # (page-27 section label, display unit on page 3)
    wanted = [
        ("Coke Rate",                   "kg/thm"),
        ("CDI Rate",                    "kg/thm"),
        ("Fuel Rate",                   "kg/thm"),
        ("BF Productivity",             "t/m3/day"),
        ("Specific Energy Consumption", "Gcal/tcs"),
    ]
    try:
        major = generate_major_techno_from_db(report_month)

        sail_by_section = {}
        for sec in major.get("sections", []):
            row = next((r for r in sec.get("rows", []) if r.get("label") == "SAIL"), None)
            if row:
                sail_by_section[sec.get("label")] = row

        result = []
        for name, unit in wanted:
            row    = sail_by_section.get(name, {})
            months = row.get("months") or []
            result.append({
                "parameter": name,
                "unit": unit,
                "values": [
                    row.get("target", ""),
                    months[-1] if months else "",   # last month column = report month
                    row.get("cply", ""),
                    row.get("cum", ""),
                    row.get("cum_cply", ""),
                ],
            })
        return result

    except Exception as e:
        # Return empty structure if error (will show empty table)
        import traceback
        traceback.print_exc()
        return []


# ---------------------------------------------------------------------------
# Auto-calculate and store SAIL actuals (materialized view)
# ---------------------------------------------------------------------------

def calculate_and_store_sail_actuals(report_month: str) -> dict:
    """
    Calculate SAIL techno actuals from plant-level data and store them.
    Works with new techno_data JSON schema.
    Called automatically after plant data extraction/update.

    Returns: {success: bool, message: str, sail_data: {...}, calc_details: {...}}
    """
    import json as _json
    from datetime import datetime

    try:
        fy = _fy_start(report_month)
        ytd = db.get_ytd_months(report_month)
        all_months = sorted(set(ytd) | {report_month})

        conn = sqlite3.connect(db.DB_PATH)
        cur = conn.cursor()

        try:
            # Fetch plant techno data from new JSON schema
            # Expected format: techno_json = {"month": {...}, "till_month": {...}}
            # Units available: BF_Shop (plant shop), BF-1...BF-8 (furnaces), SMS-1...SMS-3, etc.
            plant_data = {}  # {(plant, month, "month"|"till_month"): {param: value}}

            for plant in _BF_PLANTS:
                for month in all_months:
                    # Fetch BF_Shop (BF params) and General (SEC) units
                    for _unit in ("BF_Shop", "General"):
                        cur.execute(
                            "SELECT techno_json FROM techno_data WHERE plant=? AND unit=? AND report_month=?",
                            (plant, _unit, month)
                        )
                        row = cur.fetchone()
                        if row:
                            try:
                                techno_json = _json.loads(row[0])
                                # Merge into plant_data, General keys don't overwrite BF_Shop keys
                                pd_m  = plant_data.setdefault((plant, month, "month"), {})
                                pd_tm = plant_data.setdefault((plant, month, "till_month"), {})
                                for k, v in techno_json.get("month", {}).items():
                                    pd_m.setdefault(k, v)
                                for k, v in techno_json.get("till_month", {}).items():
                                    pd_tm.setdefault(k, v)
                            except (_json.JSONDecodeError, TypeError):
                                pass

            sail_month_data = {}
            sail_ytd_data = {}

            # Map parameter names to their lowercase underscore versions in the data
            param_map = {
                "Coke Rate": "coke_rate",
                "CDI Rate": "cdi",
                "Fuel Rate": "fuel_rate",
                "BF Productivity": "bf_productivity",
                "Specific Energy Consumption": "specific_energy_consumption"
            }

            # SEC is weighted by Crude Steel; all other BF params weighted by Hot Metal
            _SEC_PARAM = "Specific Energy Consumption"

            def _get_weight(plant, rm, item, months_list=None):
                """Get production weight for a plant. Single month or sum over months_list."""
                if months_list:
                    ph = ",".join("?" * len(months_list))
                    cur.execute(
                        f"SELECT SUM(month_actual) FROM production_table WHERE plant_name=? AND item_name=? AND report_month IN ({ph})",
                        [plant, item] + months_list
                    )
                else:
                    cur.execute(
                        "SELECT month_actual FROM production_table WHERE plant_name=? AND item_name=? AND report_month=?",
                        (plant, item, rm)
                    )
                row = cur.fetchone()
                return (row[0] or 0) if row else 0

            # Calculate each parameter
            for param_display, param_key in param_map.items():
                weight_item = "Total Crude Steel" if param_display == _SEC_PARAM else "Hot Metal"

                # Get current month value
                param_values_month = []
                total_wt_month = 0.0

                for plant in _BF_PLANTS:
                    pdata = plant_data.get((plant, report_month, "month"), {})
                    pval = pdata.get(param_key)
                    # Fuel Rate fallback: Coke Rate + Nut Coke Rate + CDI Rate
                    if pval is None and param_key == "fuel_rate":
                        cr = pdata.get("coke_rate")
                        nr = pdata.get("nut_coke_rate")
                        cd = pdata.get("cdi")
                        if cr is not None and cd is not None:
                            pval = cr + (nr or 0) + cd
                    if pval is not None and isinstance(pval, (int, float)):
                        wt = _get_weight(plant, report_month, weight_item)
                        if wt > 0:
                            param_values_month.append((pval, wt))
                            total_wt_month += wt

                # Calculate weighted average for month
                if param_values_month and total_wt_month > 0:
                    if param_display == "BF Productivity":
                        hm_sum = sum(wt / pval for pval, wt in param_values_month if pval > 0)
                        sail_month_data[param_display] = total_wt_month / hm_sum if hm_sum > 0 else None
                    else:
                        sail_month_data[param_display] = sum(pval * wt for pval, wt in param_values_month) / total_wt_month
                elif param_values_month:
                    sail_month_data[param_display] = sum(pval for pval, _ in param_values_month) / len(param_values_month)

                # Calculate YTD value (till_month)
                param_values_ytd = []
                total_wt_ytd = 0.0

                for plant in _BF_PLANTS:
                    pdata = plant_data.get((plant, report_month, "till_month"), {})
                    pval = pdata.get(param_key)
                    # Fuel Rate fallback: Coke Rate + Nut Coke Rate + CDI Rate
                    if pval is None and param_key == "fuel_rate":
                        cr = pdata.get("coke_rate")
                        nr = pdata.get("nut_coke_rate")
                        cd = pdata.get("cdi")
                        if cr is not None and cd is not None:
                            pval = cr + (nr or 0) + cd
                    if pval is not None and isinstance(pval, (int, float)):
                        wt = _get_weight(plant, report_month, weight_item, ytd)
                        if wt > 0:
                            param_values_ytd.append((pval, wt))
                            total_wt_ytd += wt

                # Calculate weighted average for YTD
                if param_values_ytd and total_wt_ytd > 0:
                    if param_display == "BF Productivity":
                        hm_sum = sum(wt / pval for pval, wt in param_values_ytd if pval > 0)
                        sail_ytd_data[param_display] = total_wt_ytd / hm_sum if hm_sum > 0 else None
                    else:
                        sail_ytd_data[param_display] = sum(pval * wt for pval, wt in param_values_ytd) / total_wt_ytd

            # Build SAIL techno_json with display names
            sail_techno_json = {"month": {}, "till_month": {}}

            for param_display in param_map.keys():
                if param_display in sail_month_data and sail_month_data[param_display] is not None:
                    sail_techno_json["month"][param_display] = {
                        "value": round(sail_month_data[param_display], 3),
                        "unit": "kg/thm" if param_display in ["Coke Rate", "CDI Rate", "Fuel Rate"] else ("t/m3/day" if param_display == "BF Productivity" else "Gcal/tcs")
                    }
                if param_display in sail_ytd_data and sail_ytd_data[param_display] is not None:
                    sail_techno_json["till_month"][param_display] = {
                        "value": round(sail_ytd_data[param_display], 3),
                        "unit": ""
                    }

            # Save SAIL actuals
            db.save_sail_techno_actuals(report_month, "Shop", sail_techno_json, {})

            return {
                "success": True,
                "message": f"SAIL actuals calculated and stored for {report_month}",
                "sail_data": sail_techno_json,
                "calc_details": {"method": "weighted_average_by_HM", "calculated_at": datetime.now().isoformat()}
            }

        finally:
            conn.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error calculating SAIL actuals: {str(e)}",
            "sail_data": {},
            "calc_details": {}
        }


# ---------------------------------------------------------------------------
# Page 3 bar chart data
# ---------------------------------------------------------------------------

def _sail_stored_json_value(cur, month, unit, keys, period):
    """Stored SAIL value from techno_data (plant='SAIL', flat snake_case units
    written by the techno-manual entry page). Returns None when absent so the
    caller falls back to the calculated weighted average."""
    import json as _json
    cur.execute(
        "SELECT techno_json FROM techno_data WHERE plant='SAIL' AND unit=? AND report_month=?",
        (unit, month)
    )
    row = cur.fetchone()
    if not row:
        return None
    try:
        period_data = _json.loads(row[0]).get(period) or {}
    except Exception:
        return None
    for k in keys:
        v = period_data.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


# Display param name → (techno_data unit, candidate snake_case keys) for
# manually entered SAIL values.
_SAIL_MANUAL_PARAM_KEYS = {
    "Coke Rate":                   ("BF_Shop", ["coke_rate"]),
    "Nut Coke Rate":               ("BF_Shop", ["nut_coke_rate"]),
    "CDI Rate":                    ("BF_Shop", ["cdi", "cdi_rate"]),
    "Fuel Rate":                   ("BF_Shop", ["fuel_rate"]),
    "BF Productivity":             ("BF_Shop", ["bf_productivity"]),
    "Specific Energy Consumption": ("General", ["specific_energy_consumption", "sp_energy", "specific_energy"]),
}


def _sail_manual_value(param_name, month, period):
    """Manually entered SAIL value for a display param name, or None."""
    spec = _SAIL_MANUAL_PARAM_KEYS.get(param_name)
    if not spec:
        return None
    unit, keys = spec
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return _sail_stored_json_value(conn.cursor(), month, unit, keys, period)
    finally:
        conn.close()


def _sail_sec_value_from_json(cur, month, period='month'):
    """SAIL-level weighted average for Specific Energy Consumption.
    Reads from techno_data 'General' unit (where page 27 stores it).
    Weights by plant Crude Steel production, consistent with page 27 SAIL row logic.
    Tries key aliases: specific_energy_consumption, sp_energy, specific_energy.
    """
    import json as _json
    _SEC_KEYS = ["specific_energy_consumption", "sp_energy", "specific_energy"]
    stored = _sail_stored_json_value(cur, month, 'General', _SEC_KEYS, period)
    if stored is not None:
        return stored
    vals, css = {}, {}
    for plant in _BF_PLANTS:
        cur.execute(
            "SELECT techno_json FROM techno_data WHERE plant=? AND unit='General' AND report_month=?",
            (plant, month)
        )
        row = cur.fetchone()
        if row:
            try:
                d = _json.loads(row[0])
                period_data = d.get(period) or d.get('month') or {}
                for k in _SEC_KEYS:
                    v = period_data.get(k)
                    if v is not None:
                        vals[plant] = float(v)
                        break
            except Exception:
                pass
        cur.execute(
            "SELECT month_actual FROM production_table "
            "WHERE plant_name=? AND item_name='Total Crude Steel' AND report_month=?",
            (plant, month)
        )
        r = cur.fetchone()
        if r and r[0] is not None:
            css[plant] = float(r[0])

    if not vals:
        return None

    num = den = 0.0
    plain = []
    for p, v in vals.items():
        cs = css.get(p)
        if cs and cs > 0:
            num += v * cs
            den += cs
        else:
            plain.append(v)
    if den > 0:
        return num / den
    if plain:
        return sum(plain) / len(plain)
    return None


def _sail_bf_value_from_json(cur, month, json_key, period='month'):
    """Compute SAIL-level weighted average for a BF param from techno_data BF_Shop.
    For BF Productivity uses harmonic mean weighted by HM; others use arithmetic weighted avg.
    period='month' for single month, 'till_month' for annual cumulative (e.g. March = full FY).
    """
    import json as _json
    stored = _sail_stored_json_value(cur, month, 'BF_Shop', [json_key], period)
    if stored is not None:
        return stored
    vals, hms = {}, {}
    for plant in _BF_PLANTS:
        cur.execute(
            "SELECT techno_json FROM techno_data WHERE plant=? AND unit='BF_Shop' AND report_month=?",
            (plant, month)
        )
        row = cur.fetchone()
        if row:
            try:
                d = _json.loads(row[0])
                period_data = d.get(period) or d.get('month') or {}
                v = period_data.get(json_key)
                if v is not None:
                    vals[plant] = float(v)
            except Exception:
                pass
        cur.execute(
            "SELECT month_actual FROM production_table WHERE plant_name=? AND item_name='Hot Metal' AND report_month=?",
            (plant, month)
        )
        r = cur.fetchone()
        if r and r[0] is not None:
            hms[plant] = float(r[0])

    if not vals:
        return None

    if json_key == 'bf_productivity':
        t_hm = t_denom = 0.0
        plain = []
        for p, bfp in vals.items():
            hm = hms.get(p)
            if hm and bfp > 0:
                t_hm += hm
                t_denom += hm / bfp
            elif bfp > 0:
                plain.append(bfp)
        if t_denom > 0:
            return t_hm / t_denom
        if plain:
            d = sum(1.0 / v for v in plain)
            return len(plain) / d if d else None
        return None
    else:
        num = den = 0.0
        plain = []
        for p, v in vals.items():
            hm = hms.get(p)
            if hm and hm > 0:
                num += v * hm
                den += hm
            else:
                plain.append(v)
        if den > 0:
            return num / den
        if plain:
            return sum(plain) / len(plain)
        return None


def generate_summary_chart_data(report_month: str) -> dict:
    """Return chart data for page 3 bar charts using techno_data BF_Shop JSON."""
    fy            = _fy_start(report_month)
    cur_fy_months = [m for m in _fy_months(fy) if m <= report_month]
    past_fys      = [fy - 3, fy - 2, fy - 1]

    # (chart label, unit, json_key in BF_Shop techno_json, plan param name)
    param_specs = [
        ("Coke Rate",       "Kg/THM",    "coke_rate",       "Coke Rate"),
        ("PCI Rate",        "Kg/THM",    "cdi",             "CDI Rate"),
        ("BF Productivity", "T/m³/Day",  "bf_productivity", "BF Productivity"),
        ("Sp. Energy",      "Gcal/TCS",  "sp_energy",       "Specific Energy Consumption"),
    ]

    def fy_label(yr):
        return f"FY{(yr + 1) % 100:02d}"

    conn = sqlite3.connect(db.DB_PATH)
    cur  = conn.cursor()
    try:
        sail_tgt    = _get_techno_plan_targets(f"{fy}-04")
        tgt_by_param = {param.split("|")[-1]: val for (_, param), val in sail_tgt.items()}

        result = []
        for chart_name, unit, json_key, plan_param in param_specs:
            is_sec = (json_key == "sp_energy")

            # Past FY bars — use till_month from March (full-FY cumulative)
            fy_bars = []
            for pfy in past_fys:
                if is_sec:
                    v = _sail_sec_value_from_json(cur, f"{pfy + 1}-03", period='till_month')
                else:
                    v = _sail_bf_value_from_json(cur, f"{pfy + 1}-03", json_key, period='till_month')
                fy_bars.append({
                    "label": fy_label(pfy),
                    "value": round(float(v), 3) if v is not None else None,
                })

            # Target bar from techno_plan_fy
            tgt_v = tgt_by_param.get(plan_param)
            target_bar = {
                "label": f"{fy_label(fy)}\nTarget",
                "value": round(float(tgt_v), 3) if tgt_v is not None else None,
            }

            # Current FY monthly bars — use month value for each month
            monthly_bars = []
            for m in cur_fy_months:
                if is_sec:
                    v = _sail_sec_value_from_json(cur, m, period='month')
                else:
                    v = _sail_bf_value_from_json(cur, m, json_key, period='month')
                monthly_bars.append({
                    "label": _mlabel(m),
                    "value": round(float(v), 3) if v is not None else None,
                })

            result.append({
                "name": chart_name, "unit": unit,
                "fy_bars": fy_bars, "target_bar": target_bar,
                "monthly_bars": monthly_bars,
            })

        return {"params": result}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# SAIL target computation
# ---------------------------------------------------------------------------

def _get_techno_plan_targets(report_month: str) -> dict:
    """
    Fetch techno plan/target data from techno_plan_fy (SAIL/Shop).
    Returns {(row_label, param_name): value} dictionary.
    """
    try:
        fy = db.get_fy_for_month(report_month)
        sail_result = db.get_sail_techno_plan(fy)
        sail_data = sail_result.get('data', {})
        # Convert from {param_name: {value, unit}} to {(row_label, param_name): value}
        tgt = {}
        for param_name, param_obj in sail_data.items():
            value = param_obj.get('value') if isinstance(param_obj, dict) else param_obj
            if value is not None:
                tgt[("SAIL", param_name)] = value
        return tgt
    except Exception:
        return {}


def _get_plant_techno_plan_targets(plant: str, report_month: str) -> dict:
    """
    Fetch plant-level techno plan data from techno_plan_fy (plant/Shop).
    Returns {(row_label, param_name): value} dictionary.
    """
    try:
        fy = db.get_fy_for_month(report_month)
        plan_result = db.get_techno_plant_plan(plant, fy)
        plant_data = plan_result.get('data', {}) if plan_result else {}
        # Convert from {param_name: {value, unit}} to {(plant, param_name): value}
        tgt = {}
        for param_name, param_obj in plant_data.items():
            value = param_obj.get('value') if isinstance(param_obj, dict) else param_obj
            if value is not None:
                tgt[(plant, param_name)] = value
        return tgt
    except Exception:
        return {}


def compute_sail_targets(fy: str) -> dict:
    """
    Compute or retrieve SAIL-level techno targets.
    Uses unified techno_plan_fy table (plant_name='SAIL', unit='Shop').
    Returns {(plant_name, parameter_name): value} for SAIL rows.
    """
    import traceback
    print(f"\n[DEBUG] compute_sail_targets called with fy={fy}")
    try:
        fy_start = int(fy.split("-")[0])
    except (ValueError, IndexError) as e:
        print(f"[ERROR] Failed to parse FY: {e}")
        return {}

    try:
        print(f"[DEBUG] Fetching SAIL plan from techno_plan_fy for fy={fy}")
        # Try to fetch from techno_plan_fy
        sail_result = db.get_sail_techno_plan(fy)
        sail_data = sail_result.get('data', {})
        print(f"[DEBUG] SAIL result retrieved: is_user_supplied={sail_result.get('is_user_supplied')}, data_count={len(sail_data)}")

        # If user-supplied data exists, return it
        if sail_result.get('is_user_supplied') and sail_data:
            result = {}
            for param, param_obj in sail_data.items():
                value = param_obj.get('value') if isinstance(param_obj, dict) else param_obj
                if value is not None:
                    result[("SAIL", param)] = value
            print(f"[DEBUG] Returning user-supplied SAIL targets: {len(result)} params")
            return result

        # If no data, compute from plant-level targets
        print(f"[DEBUG] Computing SAIL from plant-level targets")
        conn = sqlite3.connect(db.DB_PATH)
        cur  = conn.cursor()
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in compute_sail_targets: {e}")
        traceback.print_exc()
        raise

    # Annual production plan weights
    months = (
        [f"{fy_start}-{m:02d}" for m in range(4, 13)] +
        [f"{fy_start + 1}-{m:02d}" for m in range(1, 4)]
    )
    ph = ",".join("?" * len(months))
    cur.execute(f"""
        SELECT plant_name, item_name, SUM(month_actual)
        FROM production_plan_table
        WHERE report_month IN ({ph})
          AND item_name IN ('Hot Metal', 'Total Crude Steel')
          AND plant_name IN ('BSP','DSP','RSP','BSL','ISP')
        GROUP BY plant_name, item_name
    """, months)
    hm_wt = {}
    cs_wt = {}
    for plant, item, val in cur.fetchall():
        if val and val > 0:
            (hm_wt if item == "Hot Metal" else cs_wt)[plant] = val

    try:
        # Fetch plant-level targets from techno_plant_plan
        # Need a report_month to pass to _get_plant_techno_plan_targets (it will convert to FY)
        report_month_for_fy = f"{fy_start}-04"  # Any month from the FY works
        print(f"[DEBUG] Using report_month_for_fy={report_month_for_fy} to fetch plant targets")
        tgt = {}
        for plant in _BF_PLANTS:
            print(f"[DEBUG]   Fetching targets for {plant}")
            plant_tgt = _get_plant_techno_plan_targets(plant, report_month_for_fy)
            tgt.update(plant_tgt)
            print(f"[DEBUG]   Got {len(plant_tgt)} target params for {plant}")
        conn.close()
        print(f"[DEBUG] Total plant targets collected: {len(tgt)} params")
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception fetching plant targets: {e}")
        traceback.print_exc()
        conn.close()
        raise

    out = {}

    # BF params weighted by Hot Metal
    for param in _BF_HM_PARAMS:
        num = den = 0.0
        for p in _BF_PLANTS:
            v = tgt.get((p, param))
            w = hm_wt.get(p)
            if v is not None and w:
                num += v * w
                den += w
        out[("SAIL", param)] = round(num / den, 3) if den > 0 else None

    # BF Productivity: harmonic mean
    t_hm = t_denom = 0.0
    for p in _BF_PLANTS:
        hm  = hm_wt.get(p)
        bfp = tgt.get((p, "BF Productivity"))
        if hm and bfp and bfp > 0:
            t_hm    += hm
            t_denom += hm / bfp
    out[("SAIL", "BF Productivity")] = round(t_hm / t_denom, 3) if t_denom > 0 else None

    # SMS: compute shop TMI = HM + Scrap first, then weight by CS
    for shop in _SMS_SHOPS:
        hm_v    = tgt.get((shop, "Hot Metal Consumption"))
        scrap_v = tgt.get((shop, "Scrap Consumption"))
        if hm_v is not None and scrap_v is not None:
            tgt[(shop, "TMI")] = round(hm_v + scrap_v, 3)

    for param in _SMS_PARAMS:
        num = den = 0.0
        for shop in _SMS_SHOPS:
            plant = _SMS_SHOP_PLANT[shop]
            n     = _PLANT_SHOP_CNT[plant]
            v  = tgt.get((shop, param))
            cs = cs_wt.get(plant)
            if v is not None and cs:
                w = cs / n
                num += v * w
                den += w
        out[("SAIL", param)] = round(num / den, 3) if den > 0 else None

    # Specific Energy Consumption weighted by CS
    num = den = 0.0
    for p in _BF_PLANTS:
        v  = tgt.get((p, "Specific Energy Consumption"))
        cs = cs_wt.get(p)
        if v is not None and cs:
            num += v * cs
            den += cs
    out[("SAIL", "Specific Energy Consumption")] = round(num / den, 3) if den > 0 else None

    # Prepare SAIL data in {param: {value, unit}} format for storage
    sail_data_formatted = {}
    for (rl, pn), val in out.items():
        if val is not None and rl == "SAIL":
            # Store in unified format with value and unit
            sail_data_formatted[pn] = {"value": val, "unit": ""}  # Unit can be added later

    if sail_data_formatted:
        # Save calculated SAIL targets (not user-supplied)
        db.save_sail_techno_plan(fy, sail_data_formatted, is_user_supplied=False,
                                calculated_json=sail_data_formatted, calculation_method={})

    # Return in format expected by callers
    return {pn: val.get('value') if isinstance(val, dict) else val
            for pn, val in sail_data_formatted.items()}


# ---------------------------------------------------------------------------
# Bar chart SVG rendering  (unchanged — operates on computed dicts only)
# ---------------------------------------------------------------------------

_C_FY      = "#FFC000"
_C_TARGET  = "#70AD47"
_C_MONTHLY = "#4472C4"


def _fmt_bar_val(v: float) -> str:
    a = abs(v)
    if a >= 100:
        return str(int(round(v)))
    if a >= 10:
        s = f"{v:.1f}"
    elif a >= 1:
        s = f"{v:.2f}"
    else:
        s = f"{v:.3f}"
    return s.rstrip("0").rstrip(".")


def _param_svg(p: dict, vw: int = 290, vh: int = 165) -> str:
    mt   = 28
    mb   = 32
    ml   = 5
    mr   = 5
    cw, ch = vw - ml - mr, vh - mt - mb
    SEP_W = 4

    bars: list = []
    for b in p.get("fy_bars", []):
        bars.append({"label": b["label"], "value": b["value"], "color": _C_FY})
    bars.append({"sep": True})
    tb = p.get("target_bar", {})
    bars.append({"label": tb.get("label", ""), "value": tb.get("value"), "color": _C_TARGET})
    bars.append({"sep": True})
    for b in p.get("monthly_bars", []):
        bars.append({"label": b["label"], "value": b["value"], "color": _C_MONTHLY})

    valid = [e["value"] for e in bars if not e.get("sep") and e.get("value") is not None]
    if not valid:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}">'
            f'<rect width="{vw}" height="{vh}" fill="#f8fafc" rx="3"/>'
            f'<text x="{vw // 2}" y="{vh // 2}" text-anchor="middle" '
            f'font-size="9" font-family="Arial,sans-serif" fill="#94a3b8">'
            f'{p.get("name", "")} – no data</text></svg>'
        )

    ylo_v, yhi_v = min(valid), max(valid)
    rng    = yhi_v - ylo_v
    pad_lo = rng * 0.66 if rng > 0 else max(abs(yhi_v) * 0.1, 0.5)
    pad_hi = rng * 0.23 if rng > 0 else max(abs(yhi_v) * 0.05, 0.2)
    ylo, yhi = ylo_v - pad_lo, yhi_v + pad_hi
    yspan = yhi - ylo

    def ys(v: float) -> float:
        return mt + ch * (1.0 - (v - ylo) / yspan)

    n_seps  = sum(1 for e in bars if e.get("sep"))
    n_bars  = len(bars) - n_seps
    many    = n_bars > 7
    slot_w  = (cw - n_seps * SEP_W) / max(n_bars, 1)
    bar_w   = max(5.0, slot_w * 0.78)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}">']
    lines.append(
        f'<text x="{vw / 2:.0f}" y="13" text-anchor="middle" '
        f'font-size="8.5" font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">'
        f'{p.get("name", "")} ({p.get("unit", "")})</text>'
    )
    lines.append(
        f'<line x1="{ml}" y1="{mt + ch:.1f}" x2="{vw - mr}" y2="{mt + ch:.1f}" '
        f'stroke="#374151" stroke-width="0.6"/>'
    )

    x = float(ml)
    for e in bars:
        if e.get("sep"):
            x += SEP_W
            continue
        bx    = x + (slot_w - bar_w) / 2
        v     = e.get("value")
        color = e.get("color", "#aaa")
        if v is not None:
            bh  = max(1.0, (v - ylo) / yspan * ch)
            by  = ys(v)
            lines.append(
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" '
                f'height="{bh:.1f}" fill="{color}" rx="1.5"/>'
            )
            val_str = _fmt_bar_val(v)
            vly     = by - 3
            lines.append(
                f'<text x="{bx + bar_w / 2:.1f}" y="{vly:.1f}" text-anchor="middle" '
                f'font-size="7" font-weight="bold" font-family="Arial,sans-serif" '
                f'fill="{color}">{val_str}</text>'
            )

        lbl         = e.get("label", "")
        lx          = bx + bar_w / 2
        label_parts = lbl.split("\n")
        if len(label_parts) == 1:
            if many:
                ly = mt + ch + 7
                lines.append(
                    f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="end" '
                    f'font-size="6" font-family="Arial,sans-serif" fill="#374151" '
                    f'transform="rotate(-40,{lx:.1f},{ly:.1f})">{lbl}</text>'
                )
            else:
                ly = mt + ch + 10
                lines.append(
                    f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                    f'font-size="6.5" font-family="Arial,sans-serif" fill="#374151">'
                    f'{lbl}</text>'
                )
        else:
            ly1 = mt + ch + 10
            ly2 = mt + ch + 19
            lines.append(
                f'<text x="{lx:.1f}" y="{ly1:.1f}" text-anchor="middle" '
                f'font-size="6.5" font-family="Arial,sans-serif" fill="#374151">'
                f'{label_parts[0]}</text>'
            )
            lines.append(
                f'<text x="{lx:.1f}" y="{ly2:.1f}" text-anchor="middle" '
                f'font-size="6.5" font-family="Arial,sans-serif" fill="#374151">'
                f'{label_parts[1]}</text>'
            )
        x += slot_w

    lines.append("</svg>")
    return "\n".join(lines)


def generate_summary_chart_html(chart_data: dict) -> str:
    params = (chart_data or {}).get("params", [])
    if len(params) < 4:
        return ""
    rows_html = ""
    for row_start in (0, 2):
        p0, p1 = params[row_start], params[row_start + 1]
        rows_html += (
            '<div style="display:flex;gap:4px;margin-bottom:2px;">'
            f'<div style="flex:1;border:0.5px solid #e2e8f0;border-radius:3px;padding:2px;">'
            f'{_param_svg(p0)}</div>'
            f'<div style="flex:1;border:0.5px solid #e2e8f0;border-radius:3px;padding:2px;">'
            f'{_param_svg(p1)}</div>'
            "</div>"
        )
    return '<div style="margin-top:6px;">' + rows_html + "</div>"


# ---------------------------------------------------------------------------
# MAJOR page from techno_data table (replaces legacy techno_actuals path)
# ---------------------------------------------------------------------------

def generate_major_techno_from_db(report_month: str) -> dict:
    """
    Generate page 27 (MAJOR TECHNO-ECONOMIC PARAMETERS) from techno_data.
    FY columns use the till_month value from the March row of each past FY,
    which represents the full-year cumulative.
    Also includes 2026-27 plan from techno_plant_plan table.
    """
    import json as _json

    fy         = _fy_start(report_month)
    ytd        = db.get_ytd_months(report_month)
    cply_month = db.get_cply_month(report_month)

    # For plan data, use FY format (e.g., "2026-27" for current FY)
    # This is used to fetch from techno_plan_fy table
    target_fy = f"{fy}-{(fy + 1) % 100:02d}"

    # March month for past FYs: till_month of March = full-year cumulative
    # FY (fy-1) ends March of year fy; FY (fy-2) ends March of year fy-1; etc.
    fy1_march = f"{fy}-03"
    fy2_march = f"{fy - 1}-03"
    fy3_march = f"{fy - 2}-03"

    all_months = sorted(set(ytd) | {cply_month, fy1_march, fy2_march, fy3_march})

    # Production weight lookups (_hm_monthly/_cs_monthly below) must cover every
    # month from April of each relevant FY through its cutoff, not just
    # all_months - a "till_month" (cumulative) SAIL figure has to be weighted
    # by the plant's own cumulative production over the same span (e.g. Apr+May
    # HM for an Apr-May YTD ratio), not just the production of the cutoff month
    # alone.
    _weight_months = sorted(set().union(
        db.get_ytd_months(report_month), db.get_ytd_months(cply_month),
        db.get_ytd_months(fy1_march), db.get_ytd_months(fy2_march), db.get_ytd_months(fy3_march),
    ))

    # store[(plant, month)][unit] = {"month": {...}, "till_month": {...}}
    store = {}
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    try:
        ph = ",".join("?" * len(all_months))
        cur.execute(
            f"SELECT plant, report_month, unit, techno_json FROM techno_data WHERE report_month IN ({ph})",
            all_months,
        )
        for plant, rm, unit, tj in cur.fetchall():
            store.setdefault((plant, rm), {})[unit] = _json.loads(tj)
    finally:
        conn.close()

    # Patch store: compute fuel_rate = coke_rate + nut_coke_rate + cdi where missing
    for (plant, rm), units in store.items():
        for unit_name, unit_data in units.items():
            for period in ("month", "till_month"):
                pd = unit_data.get(period, {})
                if pd.get("fuel_rate") is None:
                    cr = pd.get("coke_rate")
                    nr = pd.get("nut_coke_rate")
                    cd = pd.get("cdi")
                    if cr is not None and cd is not None:
                        pd["fuel_rate"] = cr + (nr or 0) + cd

    # Fetch Total Crude Steel production for SAIL SMS weighted-average computation
    _cs_monthly = {}  # {plant: {month: month_actual}}
    conn3 = sqlite3.connect(db.DB_PATH)
    cur3 = conn3.cursor()
    try:
        ph3 = ",".join("?" * len(_weight_months))
        cur3.execute(
            f"SELECT plant_name, report_month, month_actual FROM production_table "
            f"WHERE report_month IN ({ph3}) AND item_name='Total Crude Steel'",
            _weight_months,
        )
        for _pn, _rm, _val in cur3.fetchall():
            _cs_monthly.setdefault(_pn, {})[_rm] = _val
    finally:
        conn3.close()

    # Fetch Hot Metal production for SAIL BF weighted-average computation
    _hm_monthly = {}  # {plant: {month: month_actual}}
    conn4 = sqlite3.connect(db.DB_PATH)
    cur4 = conn4.cursor()
    try:
        ph4 = ",".join("?" * len(_weight_months))
        cur4.execute(
            f"SELECT plant_name, report_month, month_actual FROM production_table "
            f"WHERE report_month IN ({ph4}) AND item_name='Hot Metal'",
            _weight_months,
        )
        for _pn, _rm, _val in cur4.fetchall():
            _hm_monthly.setdefault(_pn, {})[_rm] = _val
    finally:
        conn4.close()

    def _cum_weight(monthly_dict, plant, ref_month):
        """Sum a plant's monthly production (HM or CS) from April of ref_month's
        FY through ref_month itself - the correct weight for a 'till_month'
        (cumulative) SAIL figure, as opposed to a single month's production."""
        return sum(
            monthly_dict.get(plant, {}).get(m, 0) or 0
            for m in db.get_ytd_months(ref_month)
        )

    # SMS unit mapping and shop counts for SAIL weighting
    _sms_unit_map = {
        "BSP": ["SMS-2", "SMS-3"],
        "DSP": ["SMS"],
        "RSP": ["SMS-1", "SMS-2"],
        "BSL": ["SMS-I", "SMS-II"],
        "ISP": ["SMS"],
    }
    _sms_n_shops = {"BSP": 2, "DSP": 1, "RSP": 2, "BSL": 2, "ISP": 1}

    def _sms_sail(src_key, is_tmi, ref_month, period):
        """Compute SAIL weighted average for an SMS parameter.
        Weight per shop = plant_CS[ref_month] / n_shops.
        Handles alternate key names (e.g. DSP uses hot_metal_consumption).
        Returns None if no data available."""
        _HM_KEYS   = ["specific_hm_consumption", "hot_metal_consumption"]
        _SCRAP_KEYS = ["specific_scrap_consumption", "scrap_consumption"]
        _TMI_KEYS   = ["tmi"]

        def _pick(d, keys):
            for k in keys:
                v = d.get(k)
                if v is not None:
                    return v
            return None

        num = den = 0.0
        for _plant, _shops in _sms_unit_map.items():
            _n  = _sms_n_shops[_plant]
            _cs = (_cum_weight(_cs_monthly, _plant, ref_month) if period == "till_month"
                   else _cs_monthly.get(_plant, {}).get(ref_month, 0))
            _w  = _cs / _n if _cs > 0 else 0
            if _w <= 0:
                continue
            for _su in _shops:
                _pd = store.get((_plant, ref_month), {}).get(_su, {}).get(period, {})
                if is_tmi:
                    _v = _pick(_pd, _TMI_KEYS)
                    if _v is None:
                        _hm = _pick(_pd, _HM_KEYS)
                        _sc = _pick(_pd, _SCRAP_KEYS)
                        if _hm is not None and _sc is not None:
                            _v = _hm + _sc
                else:
                    _alt_keys = _HM_KEYS if src_key == "specific_hm_consumption" else (_SCRAP_KEYS if src_key == "specific_scrap_consumption" else [src_key])
                    _v = _pick(_pd, _alt_keys)
                if _v is not None:
                    num += _v * _w
                    den += _w
        return num / den if den > 0 else None

    _PLANT_ORDER = ["BSP", "DSP", "RSP", "BSL", "ISP"]

    # Include plants that have data in current month OR any past-FY march month, plus plants with targets
    _relevant_months = {report_month, fy1_march, fy2_march, fy3_march}
    plants_from_data = {p for (p, rm) in store if rm in _relevant_months and p != "SAIL"}
    plants_with_targets = set()
    for p in _PLANT_ORDER:
        plan_data = db.get_techno_plant_plan(p, target_fy)
        if plan_data and plan_data.get('data'):
            plants_with_targets.add(p)

    plants_with_data = sorted(
        plants_from_data | plants_with_targets,
        key=lambda p: _PLANT_ORDER.index(p) if p in _PLANT_ORDER else 99,
    )

    # Alternate key names used by different plants for the same parameter
    # Primary key → [legacy/alternate keys] for backward compat with old DB rows
    _KEY_ALIASES = {
        "sinter_in_burden":           ["sinter% in burden"],
        "pellet_in_burden":           ["pellet% in burden"],
        "cdi":                        ["cdi_rate"],
        "specific_energy_consumption": ["sp_energy", "specific_energy"],
        # BF quality (old BSL: si_in_hm/s_in_hm/hot_metal_temp; RSP/ISP: si%_in_hm/s%_in_hm)
        "silicon_in_hm":              ["si_in_hm", "si%_in_hm"],
        "sulphur_in_hm":              ["s_in_hm", "s%_in_hm"],
        "hot_blast_temp":             ["blast_temperature"],
        "avg_hot_metal_temperature":  ["hot_metal_temp"],
        # SMS (old DSP: hot_metal_consumption/scrap_consumption)
        "specific_hm_consumption":    ["hot_metal_consumption"],
        "specific_scrap_consumption": ["scrap_consumption"],
        # Coke Ovens (old RSP/ISP: cog_yield; old DSP: dry_coal_charge_per_oven/dry_coal_charge)
        "coke_oven_gas_yield":        ["cog_yield"],
        "dry_coal_charge_oven":       ["dry_coal_charge", "dry_coal_charge_per_oven"],
    }

    def _gv(plant, rm, unit, key, period="month"):
        d = store.get((plant, rm), {}).get(unit, {}).get(period, {})
        v = d.get(key)
        if v is None:
            for alt in _KEY_ALIASES.get(key, []):
                v = d.get(alt)
                if v is not None:
                    break
        return v

    def _gv_multi(plant, rm, units, key, period="month"):
        """Try each unit in order; return first non-None value."""
        for u in units:
            v = _gv(plant, rm, u, key, period)
            if v is not None:
                return v
        return None

    def _fy_val(plant, march_rm, src_unit, src_key):
        """Full-year value = till_month of March row for that FY."""
        return _gv(plant, march_rm, src_unit, src_key, "till_month")

    def _fy_val_multi(plant, march_rm, src_units, src_key):
        return _gv_multi(plant, march_rm, src_units, src_key, "till_month")

    def _bf_sail(src_key, src_units, ref_month, period, weight_by="hm", harmonic=False,
                 zero_fill_plants=None):
        """Compute SAIL weighted average (or harmonic mean, for BF Productivity)
        across plants for a BF-level parameter.
        weight_by="hm" weights by plant Hot Metal production (BF params);
        weight_by="cs" weights by plant Crude Steel production (Specific
        Energy Consumption). Returns None if no data available.

        zero_fill_plants: plant codes that structurally report NO value for
        this parameter (not a temporary reporting gap) because they don't do
        the thing being measured at all — e.g. DSP for Pellet in Burden: its
        PDF report never carries a pellet figure because its burden mix is
        sinter + iron ore only. For these plants a missing value is treated
        as an actual 0, so their HM weight is still included in the SAIL
        average (weighting it out would inflate the SAIL figure to reflect
        only the pellet-using plants). Plants NOT in this set keep the
        default behavior: a missing value means "not yet reported this
        period" and both the plant and its weight are excluded."""
        weights = _hm_monthly if weight_by == "hm" else _cs_monthly
        num = den = 0.0
        for _plant in _BF_PLANTS:
            w = (_cum_weight(weights, _plant, ref_month) if period == "till_month"
                 else weights.get(_plant, {}).get(ref_month, 0))
            if not w or w <= 0:
                continue
            v = _gv_multi(_plant, ref_month, src_units, src_key, period)
            if v is None:
                if zero_fill_plants and _plant in zero_fill_plants:
                    v = 0.0
                else:
                    continue
            if harmonic:
                if v <= 0:
                    continue
                num += w
                den += w / v
            else:
                num += v * w
                den += w
        return num / den if den > 0 else None

    # Stored SAIL values (techno_data plant='SAIL', written by the techno-manual
    # entry page and /api/techno/manual/sail/calculate) supersede the on-the-fly
    # weighted averages; calculation is the fallback when no stored value exists.
    def _sail_stored(src_key, src_units, ref_month, period):
        v = _gv_multi("SAIL", ref_month, src_units, src_key, period)
        return v if isinstance(v, (int, float)) else None

    def _bf_sail_v(src_key, src_units, ref_month, period, weight_by="hm", harmonic=False,
                   zero_fill_plants=None):
        v = _sail_stored(src_key, src_units, ref_month, period)
        if v is not None:
            return v
        return _bf_sail(src_key, src_units, ref_month, period, weight_by, harmonic, zero_fill_plants)

    def _sms_sail_v(src_key, is_tmi, ref_month, period):
        v = _sail_stored("tmi" if is_tmi else src_key, _SMS_UNIT_ORDER, ref_month, period)
        if v is not None:
            return v
        return _sms_sail(src_key, is_tmi, ref_month, period)

    def _build_row(label, unit_str, month_fn, cum_fn, cply_fn, fy1_fn, fy2_fn, fy3_fn, cum_cply_fn=None, target_fn=None, param_name=""):
        return {
            "label":  label,
            "unit":   unit_str,
            "fy3":    _fmt_param(fy3_fn(), param_name),
            "fy2":    _fmt_param(fy2_fn(), param_name),
            "fy1":    _fmt_param(fy1_fn(), param_name),
            "target": _fmt_param(target_fn(), param_name) if target_fn else "",
            "months":    [_fmt_param(month_fn(m), param_name) for m in ytd],
            "cply":      _fmt_param(cply_fn(), param_name),
            "cum":       _fmt_param(cum_fn(), param_name),
            "cum_cply":  _fmt_param(cum_cply_fn(), param_name) if cum_cply_fn else "",
        }

    def unit_section(param_name, unit_str, src_units, src_key):
        """One row per plant. Searches src_units in order for data."""
        if isinstance(src_units, str):
            src_units = [src_units]
        rows = []
        for p in plants_with_data:
            # Fetch plan data from techno_plan_fy table
            plan_data = db.get_techno_plant_plan(p, target_fy)
            plan_value = None
            if plan_data and 'data' in plan_data and param_name in plan_data['data']:
                val = plan_data['data'][param_name]
                if isinstance(val, dict) and 'value' in val:
                    plan_value = val['value']
                else:
                    plan_value = val

            rows.append(_build_row(
                p, unit_str,
                month_fn     = lambda m,  _p=p, _us=src_units: _gv_multi(_p, m,             _us, src_key),
                cum_fn       = lambda     _p=p, _us=src_units: _gv_multi(_p, report_month,  _us, src_key, "till_month"),
                cply_fn      = lambda     _p=p, _us=src_units: _gv_multi(_p, cply_month,    _us, src_key),
                fy1_fn       = lambda     _p=p, _us=src_units: _fy_val_multi(_p, fy1_march, _us, src_key),
                fy2_fn       = lambda     _p=p, _us=src_units: _fy_val_multi(_p, fy2_march, _us, src_key),
                fy3_fn       = lambda     _p=p, _us=src_units: _fy_val_multi(_p, fy3_march, _us, src_key),
                cum_cply_fn  = lambda     _p=p, _us=src_units: _gv_multi(_p, cply_month,    _us, src_key, "till_month"),
                target_fn    = lambda     _pv=plan_value: _pv,
                param_name   = param_name,
            ))
        return {"label": param_name, "rows": rows}

    # BF shop-level units: BF_Shop (RSP/BSP/BSL/DSP aggregate) or BF-5 (ISP single BF)
    _BF_UNITS = ["BF_Shop", "BF-5"]

    # SMS unit scan order — covers RSP/BSP (SMS-1/2/3), ISP/DSP (SMS), BSL (SMS-I/II)
    _SMS_UNIT_ORDER = ["SMS-1", "SMS-2", "SMS-3", "SMS", "SMS-I", "SMS-II"]

    # Alternate key aliases: DSP uses hot_metal_consumption / scrap_consumption
    _HM_ALIASES    = ["specific_hm_consumption",   "hot_metal_consumption"]
    _SCRAP_ALIASES = ["specific_scrap_consumption", "scrap_consumption"]
    _TMI_ALIASES   = ["tmi"]

    def sms_section(param_name, unit_str, src_key, tmi=False):
        """One row per (plant, SMS-unit) pair that ever reports this parameter
        (not just any data at all) - e.g. BSL's shop-level "SMS" unit only
        holds LD Slag/Lime/Aluminium Consumption, not Hot Metal/Scrap/TMI, so
        it must not produce a blank row in those sections.

        Existence/relevance is checked across all_months (current month, YTD,
        CPLY, and past-FY March cumulatives) rather than report_month alone,
        so a unit that simply hasn't submitted this month's figure yet still
        shows its row (with FY/YTD/target columns populated) instead of
        vanishing from the page - and the whole section disappearing if every
        plant happens to be blank for the current month."""
        rows = []
        _check_aliases = (
            _TMI_ALIASES + _HM_ALIASES + _SCRAP_ALIASES if tmi else
            _HM_ALIASES    if src_key == "specific_hm_consumption"   else
            _SCRAP_ALIASES if src_key == "specific_scrap_consumption" else
            [src_key]
        )
        for p in plants_with_data:
            plant_units = set()
            for _rm in all_months:
                plant_units |= set(store.get((p, _rm), {}).keys())
            for su in _SMS_UNIT_ORDER:
                if su not in plant_units:
                    continue
                if p == "BSL" and su == "SMS":
                    # BSL has only SMS-I/SMS-II, no 3rd "SMS" shop — its
                    # shop-level "SMS" unit is a separate overall figure, not
                    # a per-converter one, and duplicates SMS-I/SMS-II's own
                    # specific_hm_consumption instead of filling a gap (unlike
                    # LD Slag/Lime/Aluminium Consumption, which only exist at
                    # this shop level — those are handled by the "duplicate
                    # onto both real shops" logic in generate_techno_from_db,
                    # not this function). Skip it here to avoid a redundant
                    # third row.
                    continue
                has_data = any(
                    store.get((p, _rm), {}).get(su, {}).get(period, {}).get(k) is not None
                    for _rm in all_months
                    for period in ("month", "till_month")
                    for k in _check_aliases
                )
                if not has_data:
                    continue

                # Fetch plan data from techno_plan table for SMS shops.
                # Plan units in techno_plan_fy may differ from techno_data unit names
                # e.g. ISP stores "ISP SMS-1" in plan but "SMS" in actuals; BSL stores
                # "BSL SMS-1"/"BSL SMS-2" in plan but "SMS-I"/"SMS-II" in actuals.
                # (Roman-numeral map, not chained .replace() - "SMS-II".replace('-I','-1')
                # already consumes the "-I" substring before a second .replace('-II','-2')
                # can ever match, producing the nonsense "SMS-1I" instead of "SMS-2".)
                _ROMAN_TO_ARABIC_SU = {"SMS-I": "SMS-1", "SMS-II": "SMS-2", "SMS-III": "SMS-3"}
                _plan_unit_candidates = [
                    f"{p} {su}",
                    f"{p} {_ROMAN_TO_ARABIC_SU[su]}" if su in _ROMAN_TO_ARABIC_SU else None,
                    f"{p} SMS-1" if su == "SMS" else None,
                ]
                plan_data = {}
                for _pu in _plan_unit_candidates:
                    if not _pu:
                        continue
                    _pd = db.get_techno_plan(p, target_fy, _pu)
                    if _pd and _pd.get('data'):
                        plan_data = _pd
                        break
                plan_value = None
                if plan_data and 'data' in plan_data and param_name in plan_data['data']:
                    val = plan_data['data'][param_name]
                    plan_value = val.get('value') if isinstance(val, dict) else val

                def _pick_key(d, aliases):
                    for k in aliases:
                        v = d.get(k)
                        if v is not None:
                            return v
                    return None

                def _gv_aliases(plant, rm, _su, aliases, period="month"):
                    pd = store.get((plant, rm), {}).get(_su, {}).get(period, {})
                    return _pick_key(pd, aliases)

                if tmi:
                    def _tmi(plant, rm, period, _su=su):
                        # Try direct tmi key first, then compute from HM + Scrap
                        v = _gv_aliases(plant, rm, _su, _TMI_ALIASES, period)
                        if v is not None:
                            return v
                        hm = _gv_aliases(plant, rm, _su, _HM_ALIASES,    period)
                        sc = _gv_aliases(plant, rm, _su, _SCRAP_ALIASES,  period)
                        if hm is not None and sc is not None:
                            return hm + sc
                        return hm if hm is not None else sc
                    rows.append(_build_row(
                        f"{p} {su}", unit_str,
                        month_fn    = lambda m, _p=p: _tmi(_p, m, "month"),
                        cum_fn      = lambda     _p=p: _tmi(_p, report_month, "till_month"),
                        cply_fn     = lambda     _p=p: _tmi(_p, cply_month,   "month"),
                        fy1_fn      = lambda     _p=p: _tmi(_p, fy1_march, "till_month"),
                        fy2_fn      = lambda     _p=p: _tmi(_p, fy2_march, "till_month"),
                        fy3_fn      = lambda     _p=p: _tmi(_p, fy3_march, "till_month"),
                        cum_cply_fn = lambda     _p=p: _tmi(_p, cply_month,   "till_month"),
                        target_fn   = lambda     _pv=plan_value: _pv,
                        param_name  = param_name,
                    ))
                else:
                    # Determine alias list based on src_key
                    _aliases = (
                        _HM_ALIASES    if src_key == "specific_hm_consumption"   else
                        _SCRAP_ALIASES if src_key == "specific_scrap_consumption" else
                        [src_key]
                    )
                    rows.append(_build_row(
                        f"{p} {su}", unit_str,
                        month_fn    = lambda m, _p=p, _su=su, _al=_aliases: _gv_aliases(_p, m,            _su, _al),
                        cum_fn      = lambda     _p=p, _su=su, _al=_aliases: _gv_aliases(_p, report_month, _su, _al, "till_month"),
                        cply_fn     = lambda     _p=p, _su=su, _al=_aliases: _gv_aliases(_p, cply_month,   _su, _al),
                        fy1_fn      = lambda     _p=p, _su=su, _al=_aliases: _gv_aliases(_p, fy1_march,    _su, _al, "till_month"),
                        fy2_fn      = lambda     _p=p, _su=su, _al=_aliases: _gv_aliases(_p, fy2_march,    _su, _al, "till_month"),
                        fy3_fn      = lambda     _p=p, _su=su, _al=_aliases: _gv_aliases(_p, fy3_march,    _su, _al, "till_month"),
                        cum_cply_fn = lambda     _p=p, _su=su, _al=_aliases: _gv_aliases(_p, cply_month,   _su, _al, "till_month"),
                        target_fn   = lambda     _pv=plan_value: _pv,
                        param_name  = param_name,
                    ))
        return {"label": param_name, "rows": rows}

    # Fetch SAIL plan data from techno_plan_fy (where plant_name='SAIL')
    # Using get_sail_techno_plan to get both data and is_user_supplied flag
    sail_plan_fetch = db.get_sail_techno_plan(target_fy)
    sail_plan_data = sail_plan_fetch.get('data', {}) if sail_plan_fetch else {}
    sail_is_user_supplied = sail_plan_fetch.get('is_user_supplied', False) if sail_plan_fetch else False

    raw_sections = [
        unit_section("Coal to Hot Metal",           "",           ["General", "BF_Shop"],   "coal_to_hm"),
        unit_section("Coke Rate",                   "kg/thm",     _BF_UNITS,   "coke_rate"),
        unit_section("Nut Coke Rate",               "kg/thm",     _BF_UNITS,   "nut_coke_rate"),
        unit_section("CDI Rate",                    "kg/thm",     _BF_UNITS,   "cdi"),
        unit_section("Fuel Rate",                   "kg/thm",     _BF_UNITS,   "fuel_rate"),
        unit_section("Sinter in Burden",            "%",          _BF_UNITS,   "sinter_in_burden"),
        unit_section("Pellet in Burden",            "%",          _BF_UNITS,   "pellet_in_burden"),
        unit_section("BF Productivity",             "t/m³/day",   _BF_UNITS,   "bf_productivity"),
        sms_section ("Hot Metal Consumption",       "kg/tcs",     "specific_hm_consumption"),
        sms_section ("Scrap Consumption",           "kg/tcs",     "specific_scrap_consumption"),
        sms_section ("TMI",                         "kg/tcs",     None,  tmi=True),
        unit_section("Specific Energy Consumption", "Gcal/tcs",   "General",   "specific_energy_consumption"),
    ]

    # Add SAIL row to each section
    sections_with_sail = []
    for section in raw_sections:
        if not section["rows"]:
            continue

        param_name = section["label"]
        # Get SAIL plan value
        sail_plan_value = None
        if sail_plan_data and param_name in sail_plan_data:
            val = sail_plan_data[param_name]
            # Handle both direct values and dict with 'value' key
            if isinstance(val, dict) and 'value' in val:
                sail_plan_value = val['value']
            elif isinstance(val, (int, float)):
                sail_plan_value = val

        # Build SAIL row — populate actuals for SMS params from weighted-average computation
        _SMS_PARAM_KEYS = {
            "Hot Metal Consumption": ("specific_hm_consumption", False),
            "Scrap Consumption":     ("specific_scrap_consumption", False),
            "TMI":                   (None, True),
        }
        # BF-level params: weighted average by plant Hot Metal production;
        # BF Productivity: harmonic mean by HM; Specific Energy Consumption:
        # weighted average by plant Crude Steel production.
        # 5th tuple element = zero_fill_plants: plants whose missing value for
        # this parameter reflects "doesn't apply" rather than "not yet
        # reported" (see _bf_sail docstring). Only Pellet in Burden has one
        # today — DSP's burden mix is sinter + iron ore, no pellets, and its
        # PDF report never carries a pellet figure at all.
        _BF_SAIL_SPECS = {
            "Coal to Hot Metal":           ("coal_to_hm",                  ["General", "BF_Shop"], "hm", False, None),
            "Coke Rate":                   ("coke_rate",                   _BF_UNITS,               "hm", False, None),
            "Nut Coke Rate":               ("nut_coke_rate",               _BF_UNITS,               "hm", False, None),
            "CDI Rate":                    ("cdi",                         _BF_UNITS,               "hm", False, None),
            "Fuel Rate":                   ("fuel_rate",                   _BF_UNITS,               "hm", False, None),
            "Sinter in Burden":            ("sinter_in_burden",            _BF_UNITS,               "hm", False, None),
            "Pellet in Burden":            ("pellet_in_burden",            _BF_UNITS,               "hm", False, {"DSP"}),
            "BF Productivity":             ("bf_productivity",             _BF_UNITS,               "hm", True,  None),
            "Specific Energy Consumption": ("specific_energy_consumption", ["General"],             "cs", False, None),
        }
        if param_name in _SMS_PARAM_KEYS:
            _sk, _is_tmi = _SMS_PARAM_KEYS[param_name]
            sail_row = {
                "label":  "SAIL",
                "unit":   section["rows"][0]["unit"] if section["rows"] else "",
                "fy3":    _fmt_param(_sms_sail_v(_sk, _is_tmi, fy3_march,     "till_month"), param_name),
                "fy2":    _fmt_param(_sms_sail_v(_sk, _is_tmi, fy2_march,     "till_month"), param_name),
                "fy1":    _fmt_param(_sms_sail_v(_sk, _is_tmi, fy1_march,     "till_month"), param_name),
                "target": _fmt_param(sail_plan_value, param_name) if sail_plan_value else "",
                "months": [_fmt_param(_sms_sail_v(_sk, _is_tmi, m,            "month"),      param_name) for m in ytd],
                "cply":   _fmt_param(_sms_sail_v(_sk, _is_tmi, cply_month,    "month"),      param_name),
                "cum":    _fmt_param(_sms_sail_v(_sk, _is_tmi, report_month,  "till_month"), param_name),
                "cum_cply": _fmt_param(_sms_sail_v(_sk, _is_tmi, cply_month,  "till_month"), param_name),
            }
        elif param_name in _BF_SAIL_SPECS:
            _sk, _su, _wb, _harm, _zfp = _BF_SAIL_SPECS[param_name]
            sail_row = {
                "label":  "SAIL",
                "unit":   section["rows"][0]["unit"] if section["rows"] else "",
                "fy3":    _fmt_param(_bf_sail_v(_sk, _su, fy3_march,     "till_month", _wb, _harm, _zfp), param_name),
                "fy2":    _fmt_param(_bf_sail_v(_sk, _su, fy2_march,     "till_month", _wb, _harm, _zfp), param_name),
                "fy1":    _fmt_param(_bf_sail_v(_sk, _su, fy1_march,     "till_month", _wb, _harm, _zfp), param_name),
                "target": _fmt_param(sail_plan_value, param_name) if sail_plan_value else "",
                "months": [_fmt_param(_bf_sail_v(_sk, _su, m,            "month",      _wb, _harm, _zfp), param_name) for m in ytd],
                "cply":   _fmt_param(_bf_sail_v(_sk, _su, cply_month,    "month",      _wb, _harm, _zfp), param_name),
                "cum":    _fmt_param(_bf_sail_v(_sk, _su, report_month,  "till_month", _wb, _harm, _zfp), param_name),
                "cum_cply": _fmt_param(_bf_sail_v(_sk, _su, cply_month,  "till_month", _wb, _harm, _zfp), param_name),
            }
        else:
            sail_row = {
                "label":  "SAIL",
                "unit":   section["rows"][0]["unit"] if section["rows"] else "",
                "fy3":    "",
                "fy2":    "",
                "fy1":    "",
                "target": _fmt_param(sail_plan_value, param_name) if sail_plan_value else "",
                "months": [""] * len(section["rows"][0].get("months", [])),
                "cply":   "",
                "cum":    "",
                "cum_cply": "",
            }
        section["rows"].append(sail_row)
        sections_with_sail.append(section)

    sections = sections_with_sail

    return {
        "title":          "MAJOR TECHNO-ECONOMIC PARAMETERS",
        "subtitle":       "",
        "variant":        "techno_params",
        "group":          "MAJOR",
        "fy3_label":      _fy_label_short(fy - 3),
        "fy2_label":      _fy_label_short(fy - 2),
        "fy1_label":      _fy_label_short(fy - 1),
        "target_label":   f"Target {_fy_label_short(fy)}",
        "month_labels":   [_mlabel(m) for m in ytd],
        "cply_label":     _mlabel(cply_month),
        "cum_label":      _cum_label(ytd),
        "cum_cply_label": _cum_label([db.get_cply_month(m) for m in ytd]),
        "sections":       sections,
        "sail_is_user_supplied": sail_is_user_supplied,
    }


# ---------------------------------------------------------------------------
# MAJOR page verification — Reported (stored till_month) vs Calculated
# (freshly recomputed from this FY's monthly actuals via techno_cumulative)
# ---------------------------------------------------------------------------

# (param_name, unit_str, src_units, src_key, kind)
# kind: "unit" — one row per plant, src_units tried in order (unit_section-style)
#       "sms"  — one row per (plant, SMS-unit) that reports this key
#       "tmi"  — like "sms" but with the tmi-or-HM+Scrap fallback
_VERIFY_PARAMS = [
    ("Coal to Hot Metal",           "",           ["General", "BF_Shop"], "coal_to_hm",                  "unit"),
    ("Coke Rate",                   "kg/thm",     ["BF_Shop", "BF-5"],     "coke_rate",                   "unit"),
    ("Nut Coke Rate",               "kg/thm",     ["BF_Shop", "BF-5"],     "nut_coke_rate",               "unit"),
    ("CDI Rate",                    "kg/thm",     ["BF_Shop", "BF-5"],     "cdi",                         "unit"),
    ("Fuel Rate",                   "kg/thm",     ["BF_Shop", "BF-5"],     "fuel_rate",                   "unit"),
    ("Sinter in Burden",            "%",          ["BF_Shop", "BF-5"],     "sinter_in_burden",            "unit"),
    ("Pellet in Burden",            "%",          ["BF_Shop", "BF-5"],     "pellet_in_burden",            "unit"),
    ("BF Productivity",             "t/m³/day",   ["BF_Shop", "BF-5"],     "bf_productivity",             "unit"),
    ("Hot Metal Consumption",       "kg/tcs",     None,                    "specific_hm_consumption",     "sms"),
    ("Scrap Consumption",           "kg/tcs",     None,                    "specific_scrap_consumption",  "sms"),
    ("TMI",                         "kg/tcs",     None,                    "tmi",                         "tmi"),
    ("Specific Energy Consumption", "Gcal/tcs",   ["General"],             "specific_energy_consumption", "unit"),
]

_VERIFY_BF_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_VERIFY_SMS_UNIT_MAP = {
    "BSP": ["SMS-2", "SMS-3"], "DSP": ["SMS"], "RSP": ["SMS-1", "SMS-2"],
    "BSL": ["SMS-I", "SMS-II"], "ISP": ["SMS"],
}
_VERIFY_SMS_N_SHOPS = {"BSP": 2, "DSP": 1, "RSP": 2, "BSL": 2, "ISP": 1}
_VERIFY_SMS_UNIT_ORDER = ["SMS-1", "SMS-2", "SMS-3", "SMS", "SMS-I", "SMS-II"]
_VERIFY_HM_ALIASES    = ["specific_hm_consumption", "hot_metal_consumption"]
_VERIFY_SCRAP_ALIASES = ["specific_scrap_consumption", "scrap_consumption"]
_VERIFY_TMI_ALIASES   = ["tmi"]
# Only Pellet in Burden has a structural zero-fill exception today — DSP's
# burden mix is sinter + iron ore, no pellets, and its report never carries a
# pellet figure at all (see generate_major_techno_from_db's _bf_sail docstring).
_VERIFY_ZERO_FILL = {"Pellet in Burden": {"DSP"}}


def _verify_precision(param_name):
    """Same per-parameter rounding rule as _fmt_param, used to decide whether
    Reported and Calculated count as matching once rounded to the precision
    actually shown in the rest of the report."""
    if param_name in ("BF Productivity", "Specific Energy Consumption"):
        return 2
    if param_name == "Coal to Hot Metal":
        return 3
    return 0


def _verify_fmt4(v):
    """Calculated column is always shown to 4 decimal places regardless of
    parameter, per direct user instruction — unlike Reported, which uses
    _fmt_param's per-parameter display precision."""
    if v is None:
        return ""
    return str(_round_half_up(v, 4))


def generate_major_techno_verification(report_month: str) -> dict:
    """
    For every parameter on the MAJOR page (27), for every plant plus the SAIL
    rollup: show this FY's monthly actuals (Apr->report_month), the Reported
    till-month cumulative (same value page 27 shows), and a Calculated
    till-month cumulative freshly recomputed from the monthly actuals via
    techno_cumulative's production-weighted rules - the same engine the
    "Calculate Cumulative" feature uses. Flags a deviation whenever the two
    differ after rounding to that parameter's normal display precision.
    """
    import json as _json

    fy         = _fy_start(report_month)
    ytd        = db.get_ytd_months(report_month)
    fy1_march  = f"{fy}-03"
    fy2_march  = f"{fy - 1}-03"
    fy3_march  = f"{fy - 2}-03"
    all_months = sorted(set(ytd) | {fy1_march, fy2_march, fy3_march})

    store = {}
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    try:
        ph = ",".join("?" * len(all_months))
        cur.execute(
            f"SELECT plant, report_month, unit, techno_json FROM techno_data WHERE report_month IN ({ph})",
            all_months,
        )
        for plant, rm, unit, tj in cur.fetchall():
            store.setdefault((plant, rm), {})[unit] = _json.loads(tj)
    finally:
        conn.close()

    _hm_monthly, _cs_monthly = {}, {}
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    try:
        ph = ",".join("?" * len(ytd))
        cur.execute(
            f"SELECT plant_name, report_month, month_actual FROM production_table "
            f"WHERE report_month IN ({ph}) AND item_name='Hot Metal'", ytd)
        for pn, rm, val in cur.fetchall():
            _hm_monthly.setdefault(pn, {})[rm] = val
        cur.execute(
            f"SELECT plant_name, report_month, month_actual FROM production_table "
            f"WHERE report_month IN ({ph}) AND item_name='Total Crude Steel'", ytd)
        for pn, rm, val in cur.fetchall():
            _cs_monthly.setdefault(pn, {})[rm] = val
    finally:
        conn.close()

    def _cum_weight(monthly_dict, plant):
        return sum(monthly_dict.get(plant, {}).get(m, 0) or 0 for m in ytd)

    def _gv(plant, rm, unit, key, period="month"):
        return store.get((plant, rm), {}).get(unit, {}).get(period, {}).get(key)

    def _gv_aliases(plant, rm, unit, aliases, period="month"):
        d = store.get((plant, rm), {}).get(unit, {}).get(period, {})
        for k in aliases:
            v = d.get(k)
            if v is not None:
                return v
        return None

    def _tmi_val(plant, rm, unit, period):
        v = _gv_aliases(plant, rm, unit, _VERIFY_TMI_ALIASES, period)
        if v is not None:
            return v
        hm = _gv_aliases(plant, rm, unit, _VERIFY_HM_ALIASES, period)
        sc = _gv_aliases(plant, rm, unit, _VERIFY_SCRAP_ALIASES, period)
        if hm is not None and sc is not None:
            return hm + sc
        return hm if hm is not None else sc

    def _resolve_unit(plant, src_units, key):
        """Which of src_units this plant actually reports under - matches the
        first-hit order unit_section/_gv_multi already use elsewhere."""
        for u in src_units:
            for rm in all_months:
                if _gv(plant, rm, u, key) is not None or _gv(plant, rm, u, key, "till_month") is not None:
                    return u
        return None

    def _sms_aliases(key):
        if key == "specific_hm_consumption":
            return _VERIFY_HM_ALIASES
        if key == "specific_scrap_consumption":
            return _VERIFY_SCRAP_ALIASES
        return [key]

    def _sail_stored(ref_month, unit_candidates, key, period):
        """A manually entered SAIL override (plant='SAIL' techno_data row)
        takes precedence over the on-the-fly weighted average - matches
        generate_major_techno_from_db's _sail_stored/_bf_sail_v/_sms_sail_v
        precedence, so "Reported" here always matches what page 27 shows."""
        for u in unit_candidates:
            v = _gv("SAIL", ref_month, u, key, period)
            if isinstance(v, (int, float)):
                return v
        return None

    def _calc_plant(plant, unit, key, kind="unit"):
        """Calculated cumulative for one plant/unit, or None if nothing to
        compute. "sms"/"tmi" kinds build their own monthly-values series
        (with alias fallback / HM+Scrap reconstruction) since techno_data
        doesn't always store these under one canonical key."""
        try:
            if kind == "tmi":
                values = {m: v for m in ytd if (v := _tmi_val(plant, m, unit, "month")) is not None}
                return compute_cumulative_from_values(plant, unit, "tmi", report_month, values)["result"]
            if kind == "sms":
                aliases = _sms_aliases(key)
                values = {m: v for m in ytd if (v := _gv_aliases(plant, m, unit, aliases, "month")) is not None}
                return compute_cumulative_from_values(plant, unit, key, report_month, values)["result"]
            return compute_cumulative_preview(plant, unit, key, report_month)["result"]
        except ValueError:
            return None

    def _months_row(plant, unit, key, kind="unit"):
        if kind == "tmi":
            return [_tmi_val(plant, m, unit, "month") for m in ytd]
        if kind == "sms":
            aliases = _sms_aliases(key)
            return [_gv_aliases(plant, m, unit, aliases, "month") for m in ytd]
        return [_gv(plant, m, unit, key) for m in ytd]

    plants_with_data = sorted(
        {p for (p, rm) in store if p != "SAIL"},
        key=lambda p: _VERIFY_BF_PLANTS.index(p) if p in _VERIFY_BF_PLANTS else 99,
    )

    sections = []
    for param_name, unit_str, src_units, src_key, kind in _VERIFY_PARAMS:
        rows = []

        if kind == "unit":
            for plant in plants_with_data:
                unit = _resolve_unit(plant, src_units, src_key)
                if unit is None:
                    continue
                reported = _gv(plant, report_month, unit, src_key, "till_month")
                calculated = _calc_plant(plant, unit, src_key)
                if reported is None and calculated is None:
                    continue
                rows.append({
                    "label": plant, "unit": unit_str,
                    "months": [_fmt_param(v, param_name) for v in _months_row(plant, unit, src_key)],
                    "reported": _fmt_param(reported, param_name),
                    "calculated": _verify_fmt4(calculated),
                    "deviation": _verify_deviates(reported, calculated, param_name),
                })
            # SAIL rollup — same HM/CS weighting as generate_major_techno_from_db's
            # _bf_sail, but "Calculated" combines each plant's own CALCULATED
            # cumulative rather than each plant's stored till_month.
            weight_by = "cs" if src_key == "specific_energy_consumption" else "hm"
            harmonic = (src_key == "bf_productivity")
            weights = _cs_monthly if weight_by == "cs" else _hm_monthly
            zero_fill = _VERIFY_ZERO_FILL.get(param_name)

            def _sail_reported():
                stored = _sail_stored(report_month, src_units, src_key, "till_month")
                if stored is not None:
                    return stored
                num = den = 0.0
                for plant in _VERIFY_BF_PLANTS:
                    w = _cum_weight(weights, plant)
                    if not w or w <= 0:
                        continue
                    unit = _resolve_unit(plant, src_units, src_key)
                    v = _gv(plant, report_month, unit, src_key, "till_month") if unit else None
                    if v is None:
                        if zero_fill and plant in zero_fill:
                            v = 0.0
                        else:
                            continue
                    if harmonic:
                        if v <= 0:
                            continue
                        num += w
                        den += w / v
                    else:
                        num += v * w
                        den += w
                return num / den if den > 0 else None

            def _sail_calculated():
                num = den = 0.0
                for plant in _VERIFY_BF_PLANTS:
                    w = _cum_weight(weights, plant)
                    if not w or w <= 0:
                        continue
                    unit = _resolve_unit(plant, src_units, src_key)
                    v = _calc_plant(plant, unit, src_key) if unit else None
                    if v is None:
                        if zero_fill and plant in zero_fill:
                            v = 0.0
                        else:
                            continue
                    if harmonic:
                        if v <= 0:
                            continue
                        num += w
                        den += w / v
                    else:
                        num += v * w
                        den += w
                return num / den if den > 0 else None

            def _sail_month(m):
                stored = _sail_stored(m, src_units, src_key, "month")
                if stored is not None:
                    return stored
                num = den = 0.0
                for plant in _VERIFY_BF_PLANTS:
                    w = weights.get(plant, {}).get(m, 0) or 0
                    if w <= 0:
                        continue
                    unit = _resolve_unit(plant, src_units, src_key)
                    v = _gv(plant, m, unit, src_key) if unit else None
                    if v is None:
                        if zero_fill and plant in zero_fill:
                            v = 0.0
                        else:
                            continue
                    if harmonic:
                        if v <= 0:
                            continue
                        num += w
                        den += w / v
                    else:
                        num += v * w
                        den += w
                return num / den if den > 0 else None

            sail_reported = _sail_reported()
            sail_calculated = _sail_calculated()
            rows.append({
                "label": "SAIL", "unit": unit_str,
                "months": [_fmt_param(_sail_month(m), param_name) for m in ytd],
                "reported": _fmt_param(sail_reported, param_name),
                "calculated": _verify_fmt4(sail_calculated),
                "deviation": _verify_deviates(sail_reported, sail_calculated, param_name),
            })

        else:  # "sms" or "tmi"
            is_tmi = (kind == "tmi")
            for plant in plants_with_data:
                for su in _VERIFY_SMS_UNIT_MAP.get(plant, []):
                    if plant == "BSL" and su == "SMS":
                        continue
                    reported = _tmi_val(plant, report_month, su, "till_month") if is_tmi \
                        else _gv_aliases(plant, report_month, su,
                                         _VERIFY_HM_ALIASES if src_key == "specific_hm_consumption"
                                         else _VERIFY_SCRAP_ALIASES, "till_month")
                    calculated = _calc_plant(plant, su, src_key, kind=kind)
                    if reported is None and calculated is None:
                        continue
                    rows.append({
                        "label": f"{plant} {su}", "unit": unit_str,
                        "months": [_fmt_param(v, param_name)
                                   for v in _months_row(plant, su, src_key, kind=kind)],
                        "reported": _fmt_param(reported, param_name),
                        "calculated": _verify_fmt4(calculated),
                        "deviation": _verify_deviates(reported, calculated, param_name),
                    })

            def _sms_reported():
                stored = _sail_stored(report_month, _VERIFY_SMS_UNIT_ORDER,
                                       "tmi" if is_tmi else src_key, "till_month")
                if stored is not None:
                    return stored
                num = den = 0.0
                for plant, shops in _VERIFY_SMS_UNIT_MAP.items():
                    n = _VERIFY_SMS_N_SHOPS[plant]
                    cs = _cum_weight(_cs_monthly, plant)
                    w = cs / n if cs > 0 else 0
                    if w <= 0:
                        continue
                    for su in shops:
                        v = _tmi_val(plant, report_month, su, "till_month") if is_tmi \
                            else _gv_aliases(plant, report_month, su,
                                             _VERIFY_HM_ALIASES if src_key == "specific_hm_consumption"
                                             else _VERIFY_SCRAP_ALIASES, "till_month")
                        if v is not None:
                            num += v * w
                            den += w
                return num / den if den > 0 else None

            def _sms_calculated():
                num = den = 0.0
                for plant, shops in _VERIFY_SMS_UNIT_MAP.items():
                    n = _VERIFY_SMS_N_SHOPS[plant]
                    cs = _cum_weight(_cs_monthly, plant)
                    w = cs / n if cs > 0 else 0
                    if w <= 0:
                        continue
                    for su in shops:
                        v = _calc_plant(plant, su, src_key, kind=kind)
                        if v is not None:
                            num += v * w
                            den += w
                return num / den if den > 0 else None

            def _sms_month(m):
                stored = _sail_stored(m, _VERIFY_SMS_UNIT_ORDER,
                                       "tmi" if is_tmi else src_key, "month")
                if stored is not None:
                    return stored
                num = den = 0.0
                for plant, shops in _VERIFY_SMS_UNIT_MAP.items():
                    n = _VERIFY_SMS_N_SHOPS[plant]
                    cs = _cs_monthly.get(plant, {}).get(m, 0) or 0
                    w = cs / n if cs > 0 else 0
                    if w <= 0:
                        continue
                    for su in shops:
                        v = _tmi_val(plant, m, su, "month") if is_tmi \
                            else _gv_aliases(plant, m, su,
                                             _VERIFY_HM_ALIASES if src_key == "specific_hm_consumption"
                                             else _VERIFY_SCRAP_ALIASES)
                        if v is not None:
                            num += v * w
                            den += w
                return num / den if den > 0 else None

            sail_reported = _sms_reported()
            sail_calculated = _sms_calculated()
            rows.append({
                "label": "SAIL", "unit": unit_str,
                "months": [_fmt_param(_sms_month(m), param_name) for m in ytd],
                "reported": _fmt_param(sail_reported, param_name),
                "calculated": _verify_fmt4(sail_calculated),
                "deviation": _verify_deviates(sail_reported, sail_calculated, param_name),
            })

        if rows:
            sections.append({"label": param_name, "unit": unit_str, "rows": rows})

    return {
        "title":        "MAJOR TECHNO-ECONOMIC PARAMETERS — VERIFICATION",
        "subtitle":     "Reported (stored) vs Calculated (recomputed from monthly actuals)",
        "report_month": report_month,
        "month_labels": [_mlabel(m) for m in ytd],
        "cum_label":    _cum_label(ytd),
        "sections":     sections,
    }


def _verify_deviates(reported, calculated, param_name):
    if reported is None or calculated is None:
        return False
    precision = _verify_precision(param_name)
    return _round_half_up(reported, precision) != _round_half_up(calculated, precision)


# ---------------------------------------------------------------------------
# Pages 28-35 from techno_data table
# ---------------------------------------------------------------------------

# Schema for "param" pages (28-30): sections=parameters, rows=plant×unit combos
# Each entry: (section_label, unit_str, [(src_unit, src_key), ...])
# Schema for "mill" pages (31-35): sections=mill-units, rows=params for one plant
# Each entry: (mill_unit_name, [(param_label, src_key, unit_str), ...])

_TECHNO_DB_SCHEMA = {
    28: {
        "type": "param",
        # Coke oven parameters. Units used across plants: RSP/ISP split their
        # ovens into "COB-old"/"COB-new"; BSL/DSP report one shop as "Coke
        # Ovens"; BSP reports one shop as "COB". _COKE_OVEN_PARAM_ALIASES
        # (see generate_techno_from_db) resolves each plant's own key name to
        # the canonical one used below.
        "sections": [
            ("BF Coke Yield",          "%",          [("COB-old", "bf_coke_yield"),        ("COB-new", "bf_coke_yield"),        ("Coke Ovens", "bf_coke_yield"),        ("COB", "bf_coke_yield")]),
            # BSP reports this per battery group only ("3 page Tech" rows
            # 32/33); the battery keys exist solely for this parameter.
            ("Dry Coal Charge/Oven",   "t/oven",     [("COB", "dry_coal_charge_batt_1_8"), ("COB", "dry_coal_charge_batt_9_11"), ("COB-old", "dry_coal_charge_oven"), ("COB-new", "dry_coal_charge_oven"), ("Coke Ovens", "dry_coal_charge_oven")]),
            # RSP's "General" key, DSP's and BSP's "specific_heat_coke_ovens"
            # are all per dry-coal-charged (confirmed) - same row. BSL's
            # "sp_heat_cons" is explicitly Kcal/TCO (per tonne coke output)
            # per its own extractor - a different basis, so intentionally
            # NOT included here.
            # ISP: "Sp Heat Cons" per battery on the COKE OVENS sheet
            # (rows 169/195, 10^6 kcal/t — extractor multiplies by 1000).
            ("Sp. Heat Consmn./t DC",  "1000 Kcal/Kg DC", [("General", "specific_heat_coke_ovens"), ("Coke Ovens", "specific_heat_coke_ovens"), ("COB", "specific_heat_coke_ovens"), ("COB-old", "specific_heat_coke_ovens"), ("COB-new", "specific_heat_coke_ovens")]),
            ("Coke Oven Gas Yield",    "NM3/t",      [("COB-old", "coke_oven_gas_yield"),  ("COB-new", "coke_oven_gas_yield"),  ("Coke Ovens", "coke_oven_gas_yield"),  ("COB", "coke_oven_gas_yield")]),
            ("Coal Tar Yield",         "kg/t",       [("COB-new", "crude_tar_yield"),      ("Coke Ovens", "crude_tar_yield"),      ("COB", "crude_tar_yield")]),
            ("Crude Benzol Yield",     "kg/t",       [("COB-new", "crude_benzol_yield"),   ("Coke Ovens", "crude_benzol_yield"),   ("COB", "crude_benzol_yield")]),
            ("Amm. Sulphate Yield",    "kg/t",       [("COB-new", "ammonium_sulphate_yield"), ("Coke Ovens", "ammonium_sulphate_yield"), ("COB", "ammonium_sulphate_yield")]),
            # Also shown on page 29 (Iron Making) — coke_screen_loss is a
            # plant/shop-level figure, not per-coke-oven-unit, so (unlike the
            # rows above) it's stored under "General" (BSL/DSP/ISP/RSP) or
            # BSP's "BF_Shop", never COB/Coke Ovens/COB-old/COB-new.
            ("Coke Screen Loss",       "%",          [("General", "coke_screen_loss"), ("BF_Shop", "coke_screen_loss")]),
        ],
    },
    29: {
        "type": "param",
        "sections": [
            # Sinter plants — RSP: SP-1/SP-2/SP-3, ISP: SP, DSP/BSL: single
            # "Sinter" unit (DSP splits it into two machine-specific keys
            # dsp_sp_1/dsp_sp_2; BSL reports one combined machine_productivity)
            ("Sinter Productivity", "t/m²/day", [("SP-1", "specific_productivity"), ("SP-2", "specific_productivity"), ("SP-3", "specific_productivity"), ("SP", "specific_productivity"), ("Sinter", "dsp_sp_1"), ("Sinter", "dsp_sp_2"), ("Sinter", "machine_productivity")]),
            ("LD Slag Usage",       "kg/t",      [("SP-1", "ld_slag_cons"),          ("SP-2", "ld_slag_cons"),          ("SP-3", "ld_slag_cons"),          ("SP", "ld_slag_cons")]),
            # Blast furnaces — RSP: BF-1/BF-4/BF-5/BF_Shop, ISP: BF-5, BSL: BF-1/BF-2/BF-4/BF-5 (shared unit names)
            ("CDI Rate",            "kg/thm",    [("BF-1", "cdi"), ("BF-2", "cdi"), ("BF-4", "cdi"), ("BF-5", "cdi"), ("BF-6", "cdi"), ("BF-7", "cdi"), ("BF-8", "cdi"), ("BF_Shop", "cdi")]),
            ("Hot Blast Temp",      "°C",        [("BF-1", "hot_blast_temp"), ("BF-2", "hot_blast_temp"), ("BF-3", "hot_blast_temp"), ("BF-4", "hot_blast_temp"), ("BF-5", "hot_blast_temp"), ("BF-6", "hot_blast_temp"), ("BF-7", "hot_blast_temp"), ("BF-8", "hot_blast_temp"), ("BF_Shop", "hot_blast_temp")]),
            ("Oxygen Enrichment",   "%",         [("BF-1", "o2_enrichment"), ("BF-2", "o2_enrichment"), ("BF-3", "o2_enrichment"), ("BF-4", "o2_enrichment"), ("BF-5", "o2_enrichment"), ("BF-6", "o2_enrichment"), ("BF-7", "o2_enrichment"), ("BF-8", "o2_enrichment"), ("BF_Shop", "o2_enrichment")]),
        ],
    },
    30: {
        "type": "param",
        "sections": [
            # SMS shops — RSP: SMS-1/SMS-2, BSP: SMS-2/SMS-3, ISP/DSP: SMS, BSL: SMS-I/SMS-II
            ("Average Blows/Day",   "Nos",   [("SMS-1", "average_blows_per_day"), ("SMS-2", "average_blows_per_day"), ("SMS-3", "average_blows_per_day"), ("SMS", "average_blows_per_day"), ("SMS-I", "average_blows_per_day"), ("SMS-II", "average_blows_per_day")]),
            ("Average Heat Weight", "t",     [("SMS-1", "average_heat_weight"),   ("SMS-2", "average_heat_weight"),   ("SMS-3", "average_heat_weight"),   ("SMS", "average_heat_weight"), ("SMS-I", "average_heat_weight"), ("SMS-II", "average_heat_weight")]),
            ("Average Lining Life", "heats", [("SMS-1", "average_lining_life"),   ("SMS-2", "average_lining_life"),   ("SMS-3", "average_lining_life"),   ("SMS-I", "average_lining_life"), ("SMS-II", "average_lining_life")]),
            ("Fe-Mn Consumption",   "kg/t",  [("SMS-1", "fe-mn"),  ("SMS-2", "fe-mn"),  ("SMS-3", "fe-mn"),  ("SMS", "fe-mn"),  ("SMS-I", "fe-mn"),  ("SMS-II", "fe-mn")]),
            ("Fe-Si Consumption",   "kg/t",  [("SMS-1", "fe-si"),  ("SMS-2", "fe-si"),  ("SMS-3", "fe-si"),  ("SMS", "fe-si"),  ("SMS-I", "fe-si"),  ("SMS-II", "fe-si")]),
            ("Si-Mn Consumption",   "kg/t",  [("SMS-1", "si-mn"),  ("SMS-2", "si-mn"),  ("SMS-3", "si-mn"),  ("SMS", "si-mn"),  ("SMS-I", "si-mn"),  ("SMS-II", "si-mn")]),
            ("Oxygen Blowing",      "NM3/t", [("SMS-1", "oxygen_blowing"), ("SMS-2", "oxygen_blowing"), ("SMS-3", "oxygen_blowing"), ("SMS", "oxygen_blowing"), ("SMS-I", "oxygen_blowing"), ("SMS-II", "oxygen_blowing")]),
            # BSP reports Caster Yield per product under SMS-2 (Conditioned
            # Slabs, Conditioned Blooms); DSP reports it per caster under SMS
            # (Billet/Bloom/BRC) — rather than one overall figure in either
            # case. See _CASTER_YIELD_LABEL for the distinct row labels.
            ("Caster Yield",        "%",     [("SMS-1", "caster_yield"),   ("SMS-2", "caster_yield"),   ("SMS-3", "caster_yield"),   ("SMS", "caster_yield"), ("SMS-I", "caster_yield"), ("SMS-II", "caster_yield"), ("SMS-2", "conditioned_slab_caster_yield"), ("SMS-2", "conditioned_bloom_caster_yield"), ("SMS", "billet_caster_yield"), ("SMS", "bloom_caster_yield"), ("SMS", "brc_caster_yield")]),
        ],
    },
    # Mill pages: sections = mill-unit, rows = params for that plant
    31: {
        "type": "mill",
        "plant": "BSP",
        "sections": [
            ("PM", [
                ("Yield",             "yield",             "%"),
                ("Availability",      "availability",      "%"),
                ("Utilisation",       "utilisation",       "%"),
                ("Rolling Rate",      "rolling_rate",      "t/hr"),
                ("Sp. Heat Consmn.",  "heat_consumption",  "kcal/t"),
                ("Sp. Power Consmn.", "power_consumption", "kWh/t"),
            ]),
            ("RSM", [
                ("Yield",             "yield",             "%"),
                ("Availability",      "availability",      "%"),
                ("Utilisation",       "utilisation",       "%"),
                ("Rolling Rate",      "rolling_rate",      "t/hr"),
                ("Sp. Heat Consmn.",  "heat_consumption",  "kcal/t"),
                ("Sp. Power Consmn.", "power_consumption", "kWh/t"),
            ]),
            ("MM", [
                ("Yield",             "yield",             "%"),
                ("Availability",      "availability",      "%"),
                ("Utilisation",       "utilisation",       "%"),
                ("Rolling Rate",      "rolling_rate",      "t/hr"),
                ("Sp. Heat Consmn.",  "heat_consumption",  "kcal/t"),
                ("Sp. Power Consmn.", "power_consumption", "kWh/t"),
            ]),
            ("URM", [
                ("Yield",             "yield",             "%"),
                ("Availability",      "availability",      "%"),
                ("Utilisation",       "utilisation",       "%"),
                ("Rolling Rate",      "rolling_rate",      "t/hr"),
                ("Sp. Heat Consmn.",  "heat_consumption",  "kcal/t"),
                ("Sp. Power Consmn.", "power_consumption", "kWh/t"),
            ]),
            ("WRM", [
                ("Yield",             "yield",             "%"),
                ("Availability",      "availability",      "%"),
                ("Utilisation",       "utilisation",       "%"),
                ("Rolling Rate",      "rolling_rate",      "t/hr"),
                ("Sp. Heat Consmn.",  "heat_consumption",  "kcal/t"),
                ("Sp. Power Consmn.", "power_consumption", "kWh/t"),
            ]),
            ("BRM", [
                ("Yield",             "yield",             "%"),
                ("Availability",      "availability",      "%"),
                ("Utilisation",       "utilisation",       "%"),
                ("Rolling Rate",      "rolling_rate",      "t/hr"),
            ]),
        ],
    },
    32: {
        "type": "mill",
        "plant": "DSP",
        "sections": [
            ("Merchant Mill", [
                ("Yield",             "yield",              "%"),
                ("Availability",      "mill_availability",  "%"),
                ("Utilisation",       "mill_utilisation",   "%"),
                ("Rolling Rate",      "rolling_rate",       "t/hr"),
                ("On ICH",            "on_ich",             "%"),
                ("Sp. Heat Consmn.",  "specific_heat",      "M.Cal/T"),
                ("Sp. Power Consmn.", "specific_power",     "kWh/T"),
            ]),
            ("MSM", [
                ("Yield",             "yield",              "%"),
                ("Availability",      "mill_availability",  "%"),
                ("Utilisation",       "mill_utilisation",   "%"),
                ("Rolling Rate",      "rolling_rate",       "t/hr"),
                ("On ICH",            "on_ich",             "%"),
                ("Sp. Heat Consmn.",  "specific_heat",      "M.Cal/T"),
                ("Sp. Power Consmn.", "specific_power",     "kWh/T"),
            ]),
            ("Wheel Plant", [
                ("Yield",             "finished_wheel_over_ingot_round", "%"),
                ("Availability",      "forging_availability",            "%"),
                ("Utilisation",       "forging_utilisation",             "%"),
                ("Rolling Rate",      "rolling_rate",                    "Nos./Hr."),
                ("On ICH",            "on_ich",                          "%"),
                ("Sp. Heat Consmn.",  "specific_heat",                   "M.Cal/T"),
                ("Sp. Power Consmn.", "specific_power",                  "kWh/T"),
            ]),
            ("Axle Plant", [
                ("Yield",             "yield_over_good_bloom", "%"),
                ("Availability",      "forging_availability",  "%"),
                ("Utilisation",       "forging_utilisation",   "%"),
                ("Forging Rate",      "forging_rate",          "Nos./Hr."),
                ("On ICH",            "on_ich",                "%"),
                ("Sp. Heat Consmn.",  "specific_heat",         "M.Cal/T"),
                ("Sp. Power Consmn.", "specific_power",        "kWh/T"),
            ]),
        ],
    },
    33: {
        "type": "mill",
        "plant": "RSP",
        "sections": [
            ("PM", [
                ("Yield Prime",       "yield_prime",               "%"),
                ("Yield Total",       "yield_total",               "%"),
                ("Avg Slab Weight",   "average_slab_weight",       "t"),
                ("Availability",      "availability",              "%"),
                ("Utilisation",       "utilisation",               "%"),
                ("Rolling Rate",      "rolling_rate",              "t/hr"),
                ("Sp. Heat Consmn.",  "specific_heat_consumption", "M.Cal/T"),
                ("Sp. Power Consmn.", "specific_power_consumption","kWh/t"),
            ]),
            ("NPM", [
                ("Yield Prime",       "yield_prime",               "%"),
                ("Yield Total",       "yield_total",               "%"),
                ("Avg Slab Weight",   "average_slab_weight",       "t"),
                ("Availability",      "availability",              "%"),
                ("Utilisation",       "utilisation",               "%"),
                ("Rolling Rate",      "rolling_rate",              "t/hr"),
                ("Sp. Heat Consmn.",  "specific_heat_consumption", "M.Cal/T"),
                ("Sp. Power Consmn.", "specific_power_consumption","kWh/t"),
            ]),
            ("HSM-1", [
                ("HR Coil Yield",     "yield_total",                  "%"),
                ("Avg Slab Weight",   "average_slab_weight",          "t"),
                ("Availability",      "availability",                 "%"),
                ("Utilisation",       "utilisation",                  "%"),
                ("Rolling Rate",      "rolling_rate",                 "t/hr"),
                ("RH Fce Avail.",     "average_furnace_availability", "Nos/day"),
                ("Sp. Heat Consmn.",  "specific_heat_consumption",    "M.Cal/T"),
                ("Sp. Power Consmn.", "specific_power_consumption",   "kWh/t"),
            ]),
            ("HSM-2", [
                ("HR Coil Yield",     "yield_total",                  "%"),
                ("Avg Slab Weight",   "average_slab_weight",          "t"),
                ("Availability",      "availability",                 "%"),
                ("Utilisation",       "utilisation",                  "%"),
                ("Rolling Rate",      "rolling_rate",                 "t/hr"),
                ("RH Fce Avail.",     "average_furnace_availability", "Nos/day"),
                ("Sp. Heat Consmn.",  "specific_heat_consumption",    "M.Cal/T"),
                ("Sp. Power Consmn.", "specific_power_consumption",   "kWh/t"),
            ]),
            ("SSM", [
                ("Yield",             "yield",            "%"),
                ("Acid Consumption",  "acid_consumption", "kg/t"),
                ("Availability",      "availability",     "%"),
                ("Utilisation",       "utilisation",      "%"),
                ("Rolling Rate",      "rolling_rate",     "t/hr"),
            ]),
            ("SWP", [
                ("Yield",             "yield",        "%"),
                ("Availability",      "availability", "%"),
                ("Utilisation",       "utilisation",  "%"),
                ("Rolling Rate",      "rolling_rate", "t/hr"),
            ]),
            ("ERW", [
                ("Yield",             "yield",        "%"),
                ("Availability",      "availability", "%"),
                ("Utilisation",       "utilisation",  "%"),
                ("Rolling Rate",      "rolling_rate", "t/hr"),
            ]),
            ("CRM", [
                ("Acid Cons. in Pick Input", "acid_consumption",       "Kg/T"),
                ("Zinc Cons. Excl. Dross",   "zinc_cons_excl_dross",   "Kg/T"),
                ("Zinc Cons. Incl. Dross",   "zinc_cons_incl_dross",   "Kg/T"),
                ("Pickled Coils Yield",      "pickled_coils_yield",    "%"),
                ("Galvanised Sheet Yield",   "galvanised_sheet_yield", "%"),
            ]),
        ],
    },
    34: {
        # BSL's actual rolling mills - HSM, CRM 1&2, CRM 3. (BF_Shop/SMS-I/
        # SMS-II used to be listed here by mistake; those are Iron Making/
        # SMS shops, not mills, and already have their own pages: 29 and 30.)
        #
        # CRM 1&2 and CRM 3 are each a complex of several independently
        # -operated sub-machines with no complex-wide Availability/
        # Utilisation/Rolling Rate figure of their own — per direct user
        # instruction, only these specific named figures are surfaced, all
        # under the CRM 1&2 / CRM 3 row itself (not as separate per-sub-
        # machine rows). See excel_extractors/excel_extractor_bsl.py's
        # _CRM_ROWS for the extraction side.
        "type": "mill",
        "plant": "BSL",
        "sections": [
            ("HSM", [
                ("Yield",             "yield",             "%"),
                ("Availability",      "availability",      "%"),
                ("Utilisation",       "utilisation",       "%"),
                ("Rolling Rate",      "rolling_rate",      "t/hr"),
                ("Sp. Heat Consmn.",  "heat_consumption",  "kcal/t"),
                ("Sp. Power Consmn.", "power_consumption", "kWh/t"),
            ]),
            ("CRM 1&2", [
                ("Yield of HR Coil",  "yield_of_hr_coil",  "%"),
                ("TM-1 Utilisation",  "tm_1_utilisation",  "%"),
                ("TM-2 Utilisation",  "tm_2_utilisation",  "%"),
            ]),
            ("CRM 3", [
                ("Yield of HR Coil",             "yield_of_hr_coil",           "%"),
                ("PLTCM Yield",                  "pltcm_yield",                "%"),
                ("PLTCM Availability",           "pltcm_availability",         "%"),
                ("PLTCM Utilisation",            "pltcm_utilisation",          "%"),
                ("SPM Yield of CR Coil",         "spm_yield_of_cr_coil",       "%"),
                ("SPM Availability",             "spm_availability",           "%"),
                ("SPM Utilisation",              "spm_utilisation",            "%"),
                ("Specific Power Consumption",   "specific_power_consumption", "kWh/t"),
            ]),
        ],
    },
    35: {
        "type": "mill",
        "plant": "ISP",
        "sections": [
            ("BM", [
                ("Yield",             "yield_total",               "%"),
                ("Availability",      "availability",              "%"),
                ("Utilisation",       "utilisation",               "%"),
                ("Rolling Rate",      "rolling_rate",              "t/hr"),
                ("Sp. Power Consmn.", "specific_power_consumption","kWh/t"),
                ("Sp. Heat Consmn.",  "specific_heat_consumption", "kcal/t"),
                ("Gas Consumption",   "total_gas_consumption",     "Nm³/t"),
                ("CBM Gas Consmn.",   "cbm_gas_consumption",       "Nm³/t"),
            ]),
            ("USM", [
                ("Yield",             "yield_total",               "%"),
                ("Availability",      "availability",              "%"),
                ("Utilisation",       "utilisation",               "%"),
                ("Rolling Rate",      "rolling_rate",              "t/hr"),
                ("Sp. Power Consmn.", "specific_power_consumption","kWh/t"),
                ("Sp. Heat Consmn.",  "specific_heat_consumption", "kcal/t"),
                ("Gas Consumption",   "total_gas_consumption",     "Nm³/t"),
                ("CBM Gas Consmn.",   "cbm_gas_consumption",       "Nm³/t"),
            ]),
            ("WRM", [
                ("Yield",             "yield_total",               "%"),
                ("Availability",      "availability",              "%"),
                ("Utilisation",       "utilisation",               "%"),
                ("Rolling Rate",      "rolling_rate",              "t/hr"),
                ("Sp. Power Consmn.", "specific_power_consumption","kWh/t"),
                ("Sp. Heat Consmn.",  "specific_heat_consumption", "kcal/t"),
                ("Gas Consumption",   "total_gas_consumption",     "Nm³/t"),
                ("CBM Gas Consmn.",   "cbm_gas_consumption",       "Nm³/t"),
            ]),
        ],
    },
}


def generate_techno_from_db(report_month: str, page_no: int) -> dict:
    """
    Generate techno pages 28-35 from techno_data.
    FY columns use till_month from March of each past FY.
    """
    import json as _json

    if page_no not in TECHNO_PAGES or page_no not in _TECHNO_DB_SCHEMA:
        return {}

    group, title, subtitle = TECHNO_PAGES[page_no]
    cfg = _TECHNO_DB_SCHEMA[page_no]

    fy         = _fy_start(report_month)
    ytd        = db.get_ytd_months(report_month)
    cply_month = db.get_cply_month(report_month)
    fy1_march  = f"{fy}-03"
    fy2_march  = f"{fy - 1}-03"
    fy3_march  = f"{fy - 2}-03"

    all_months = sorted(set(ytd) | {cply_month, fy1_march, fy2_march, fy3_march})

    store = {}
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    try:
        ph = ",".join("?" * len(all_months))
        cur.execute(
            f"SELECT plant, report_month, unit, techno_json FROM techno_data WHERE report_month IN ({ph})",
            all_months,
        )
        for plant, rm, unit, tj in cur.fetchall():
            store.setdefault((plant, rm), {})[unit] = _json.loads(tj)
    finally:
        conn.close()

    # Fetch plan data from techno_plan_fy for the current FY
    fy_str = _fy_label(fy)  # e.g., "2026-27"
    plan_store = {}
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT plant_name, unit, techno_json FROM techno_plan_fy WHERE fy = ?",
            (fy_str,)
        )
        for plant_name, unit, tj in cur.fetchall():
            plan_store[(plant_name, unit)] = _json.loads(tj) if tj else {}
    finally:
        conn.close()

    _PLANT_ORDER = ["BSP", "DSP", "RSP", "BSL", "ISP"]
    # A plant qualifies if it has data for ANY period this page displays
    # (current month, current-FY months so far, CPLY, or any of the last 3
    # FY-end Marches) - not just the exact report_month. A plant that hasn't
    # uploaded report_month's file yet shouldn't have its other-period data
    # hidden entirely. `store` is already scoped to `all_months` by the SQL
    # fetch above, so every key already qualifies.
    available_plants = sorted(
        {p for (p, rm) in store},
        key=lambda p: _PLANT_ORDER.index(p) if p in _PLANT_ORDER else 99,
    )

    # Coke Ovens parameters: different plants store the same concept under
    # different snake_case keys (e.g. RSP/ISP historically also wrote
    # "cog_yield"/"dry_coal_charge" alongside the canonical long-form keys
    # below). Canonical key -> alternate keys to also check.
    _COKE_OVEN_PARAM_ALIASES = {
        "dry_coal_charge_oven":      ["dry_coal_charge", "dry_coal_charge_per_oven"],
        "coke_oven_gas_yield":       ["cog_yield"],
        "crude_tar_yield":           ["coal_tar_yield", "crude_tar"],
        "crude_benzol_yield":        ["crude_benzol"],
        "ammonium_sulphate_yield":   ["ammonium_sulphate"],
        "ash_blend_coal":            ["average_ash_in_coal_blend", "ash_in_coal_blend"],
        "ash_in_coke":               ["average_ash_in_coke", "ash_in_bf_coke"],
        "m10_coke":                  ["m10", "coke_m_10"],
        "m40_coke":                  ["m40"],
        "csr_coke":                  ["coke_csr"],
        "cri_coke":                  ["coke_cri"],
        "vm_blend_coal":             ["average_volatile_matter_in_coal_blend", "vm_in_coal_blend"],
        # BSL's own extractor stores this under "sp_heat_cons" (Sheet1 F10/G10,
        # "HEAT CONSUMPN. IN G.CAL/T OF DRY COAL CHARGED", x1000 to kcal/kg DC
        # - same basis and scale as DSP's "specific_heat_coke_ovens", confirmed
        # against real data: BSL ~660-685 vs DSP ~668 for the same months).
        "specific_heat_coke_ovens":  ["sp_heat_cons"],
    }

    # TMI (Total Metallic Input) fallback — same aliases/logic page 27's
    # MAJOR page uses: prefer a stored "tmi" value, else compute HM + Scrap.
    _TMI_HM_ALIASES    = ["specific_hm_consumption", "hot_metal_consumption"]
    _TMI_SCRAP_ALIASES = ["specific_scrap_consumption", "scrap_consumption"]

    def _tmi_value(d):
        v = d.get("tmi")
        if v is not None:
            return v
        hm = next((d.get(k) for k in _TMI_HM_ALIASES if d.get(k) is not None), None)
        sc = next((d.get(k) for k in _TMI_SCRAP_ALIASES if d.get(k) is not None), None)
        if hm is not None and sc is not None:
            return hm + sc
        return hm if hm is not None else sc

    def _gv(plant, rm, unit, key, period="month"):
        d = store.get((plant, rm), {}).get(unit, {}).get(period, {})
        if key == "tmi":
            return _tmi_value(d)
        v = d.get(key)
        if v is None:
            for alt in _COKE_OVEN_PARAM_ALIASES.get(key, []):
                v = d.get(alt)
                if v is not None:
                    break
        return v

    def _get_plan_value(plant, unit, param_key):
        """Get planned value for a parameter from techno_plan_fy."""
        plan_data = plan_store.get((plant, unit), {})
        param_obj = plan_data.get(param_key, {})
        # Handle both {value, unit} format and flat value
        if isinstance(param_obj, dict):
            return param_obj.get('value')
        return param_obj

    def _make_row(label, unit_str, plant, src_unit, src_key, bold=False):
        target_val = _get_plan_value(plant, src_unit, src_key)
        return {
            "label":    label,
            "unit":     unit_str,
            "bold":     bold,
            "fy3":      _fmt(_gv(plant, fy3_march,    src_unit, src_key, "till_month")),
            "fy2":      _fmt(_gv(plant, fy2_march,    src_unit, src_key, "till_month")),
            "fy1":      _fmt(_gv(plant, fy1_march,    src_unit, src_key, "till_month")),
            "target":   _fmt(target_val),
            "months":   [_fmt(_gv(plant, m, src_unit, src_key)) for m in ytd],
            "cply":     _fmt(_gv(plant, cply_month,   src_unit, src_key)),
            "cum":      _fmt(_gv(plant, report_month, src_unit, src_key, "till_month")),
            "cum_cply": _fmt(_gv(plant, cply_month,   src_unit, src_key, "till_month")),
        }

    # Page 34 (BSL mills) display names - techno_data stores these under
    # "CRM 1&2"/"CRM 3", shown here as "CRM"/"CRM-III" per report convention.
    _MILL_UNIT_LABEL = {"CRM 1&2": "CRM", "CRM 3": "CRM-III"}

    # BSP's Dry Coal Charge/Oven comes as two battery groups ("3 page Tech"
    # rows 32/33) - key-specific row labels, used for no other parameter.
    _DRY_COAL_BATT_LABEL = {
        "dry_coal_charge_batt_1_8":  "Batt. 1-8",
        "dry_coal_charge_batt_9_11": "Batt. 9-11",
    }

    # DSP's Sinter Productivity reports two machines under one "Sinter" unit
    # (dsp_sp_1/dsp_sp_2) rather than splitting into separate SP-1/SP-2 units
    # like RSP/BSP - key-specific row labels so the two rows aren't both
    # rendered as the identical "DSP Sinter".
    _SINTER_MACHINE_LABEL = {
        "dsp_sp_1": "SP-1",
        "dsp_sp_2": "SP-2",
    }

    # BSP's Caster Yield is reported per product under one SMS-2 unit
    # (Conditioned Slab / Conditioned Blooms); DSP's is reported per caster
    # under one SMS unit (Billet / Bloom / BRC) — rather than one overall
    # figure in either case.
    _CASTER_YIELD_LABEL = {
        "conditioned_slab_caster_yield":  "Conditioned Slabs",
        "conditioned_bloom_caster_yield": "Conditioned Blooms",
        "billet_caster_yield":            "Billet Caster",
        "bloom_caster_yield":             "Bloom Caster",
        "brc_caster_yield":               "Bloom cum Round Caster",
    }

    def _coke_oven_label(plant, unit):
        """Page 28 row labels: drop the "COB"/"Coke Ovens" wording entirely -
        "RSP COB-old" -> "RSP-Old", "BSL Coke Ovens" -> "BSL" (single battery,
        no suffix needed)."""
        if unit == "COB-old":
            return f"{plant}-Old"
        if unit == "COB-new":
            return f"{plant}-New"
        return plant

    def _row_label_and_bold(page_no, plant, src_unit, multi_plant):
        """Resolve a (label, bold) pair for a "param" page row.
        - Page 28: coke-oven naming (see _coke_oven_label).
        - "BF_Shop" (shop-wide average across furnaces): bare plant name,
          bold, to stand out from the individual furnace rows above it.
        - "General" (plant-wide, not furnace/shop specific): bare plant name.
        - Otherwise: "<plant> <unit>" as before.
        """
        if page_no == 28:
            return _coke_oven_label(plant, src_unit), False
        if src_unit == "BF_Shop":
            return plant, True
        if src_unit == "General":
            return plant, False
        label = f"{plant} {src_unit}" if multi_plant else src_unit
        return label, False

    sections = []

    if cfg["type"] == "param":
        # sections = parameters, rows = available plant×unit combos
        multi_plant = len(available_plants) > 1
        for (sec_label, unit_str, unit_specs) in cfg["sections"]:
            rows = []
            # Plant order (BSP, DSP, RSP, BSL, ISP - see _PLANT_ORDER) takes
            # priority over unit order, so e.g. RSP-Old/RSP-New stay grouped
            # together in plant position rather than all "-Old" units first.
            for plant in available_plants:
                for (src_unit, src_key) in unit_specs:
                    _key_aliases = [src_key] + _COKE_OVEN_PARAM_ALIASES.get(src_key, [])
                    # Include the row if ANY period this page displays has a
                    # value - current month, current-FY months so far, CPLY,
                    # or any of the last 3 FY-end Marches - not just
                    # report_month specifically (a plant/unit that only
                    # reports at FY-end, or hasn't uploaded report_month's
                    # file yet, should still show its other-period data
                    # rather than being omitted entirely).
                    if src_key == "tmi":
                        has_val = any(
                            _tmi_value(store.get((plant, rm), {}).get(src_unit, {}).get(period, {})) is not None
                            for rm in all_months
                            for period in ("month", "till_month")
                        )
                    else:
                        has_val = any(
                            store.get((plant, rm), {}).get(src_unit, {}).get(period, {}).get(k) is not None
                            for rm in all_months
                            for period in ("month", "till_month")
                            for k in _key_aliases
                        )
                    if not has_val:
                        continue
                    label, bold = _row_label_and_bold(page_no, plant, src_unit, multi_plant)
                    if src_key in _DRY_COAL_BATT_LABEL:
                        label = f"{plant} {_DRY_COAL_BATT_LABEL[src_key]}"
                    elif src_key in _SINTER_MACHINE_LABEL:
                        label = f"{plant} {_SINTER_MACHINE_LABEL[src_key]}"
                    elif src_key in _CASTER_YIELD_LABEL:
                        label = f"{plant} {_CASTER_YIELD_LABEL[src_key]}"
                    if plant == "BSL" and src_unit == "SMS":
                        # BSL has only SMS-I/SMS-II, no 3rd "SMS" shop - a
                        # param stored only at the combined-shop level (no
                        # per-converter breakdown, e.g. LD Slag Cons) is
                        # shown under both real shops rather than as its own
                        # "BSL SMS" row implying a shop that doesn't exist.
                        rows.append(_make_row(f"{plant} SMS-I",  unit_str, plant, src_unit, src_key))
                        rows.append(_make_row(f"{plant} SMS-II", unit_str, plant, src_unit, src_key))
                    else:
                        rows.append(_make_row(label, unit_str, plant, src_unit, src_key, bold=bold))
            # Stored SAIL values (techno_data plant='SAIL', entered via the
            # techno-manual page) get a bold SAIL row at the end of the
            # section. Unlike plant rows, checked across ALL displayed months
            # so an entry for e.g. a past-FY March still shows up.
            sail_spec = next(
                ((su, sk) for (su, sk) in unit_specs
                 if any(_gv("SAIL", rm, su, sk, p) is not None
                        for rm in all_months for p in ("month", "till_month"))),
                None,
            )
            if sail_spec:
                rows.append(_make_row("SAIL", unit_str, "SAIL",
                                      sail_spec[0], sail_spec[1], bold=True))
            if rows:
                sections.append({"label": sec_label, "rows": rows})

    elif cfg["type"] == "mill":
        # sections = mill units, rows = params for that fixed plant
        plant = cfg.get("plant", "RSP")
        for (src_unit, param_specs) in cfg.get("sections", []):
            rows = []
            for (param_label, src_key, unit_str) in param_specs:
                # Include the row if ANY period this page displays has a
                # value - current-FY months so far (incl. report_month), or
                # any of the last 3 FY-end Marches - not just report_month
                # specifically. `all_months` already covers ytd + cply_month
                # + fy1/fy2/fy3 marches.
                has_val = any(
                    _gv(plant, rm, src_unit, src_key, p) is not None
                    for rm in all_months
                    for p in ["month", "till_month"]
                )
                if has_val:
                    rows.append(_make_row(param_label, unit_str, plant, src_unit, src_key))
            if rows:
                mill_label = _MILL_UNIT_LABEL.get(src_unit, src_unit) if page_no == 34 else src_unit
                sections.append({"label": mill_label, "rows": rows})

    return {
        "title":          title,
        "subtitle":       subtitle,
        "variant":        "techno_params",
        "group":          group,
        "fy3_label":      _fy_label_short(fy - 3),
        "fy2_label":      _fy_label_short(fy - 2),
        "fy1_label":      _fy_label_short(fy - 1),
        "target_label":   f"Target {_fy_label_short(fy)}",
        "month_labels":   [_mlabel(m) for m in ytd],
        "cply_label":     _mlabel(cply_month),
        "cum_label":      _cum_label(ytd),
        "cum_cply_label": _cum_label([db.get_cply_month(m) for m in ytd]),
        "sections":       sections,
    }
