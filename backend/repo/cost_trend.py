"""Cost trend repository on the v2 schema: cost_trend_annual and
cost_trend_monthly (v1 plant -> plant_code, aliased back where a row is
returned).

Same public names, signatures, return shapes, exceptions and module
constants as repo/cost_trend.py.

ORDER. v1's reads had no ORDER BY; WHERE product = %s AND fy / report_month
IN (...) was served by the primary key (fy | report_month, product,
cost_type, plant), which v2's primary key repeats under the same ai_ci
collation. That order fixes the insertion order of the returned dicts'
plant keys, so it is explicit here.

WRITES. One bump per call, first (skipped in a dry run), as v1 (also for an
empty batch). Each entry is checked against v1's column limits just before
its own INSERT, where v1's statement would have failed (1048 / 1406 with
v1's column names; the transaction then commits nothing, as v1's
uncommitted connection did), then a plant longer than the v2 plant
master's 8 characters is refused (OutOfModelError; v1's VARCHAR(16) stored
it). Months and FYs are cut to CHAR(7) as MySQL cut them
(_keys.fit_month / fit_fy); missing cal_month / plant rows are created
(_keys.ensure_month / ensure_plant). An empty batch never touches the month,
as in v1.
"""
from typing import Any, Dict, List

from dbengine import connect
from repo import conn as rc
from repo import version as _ver
from repo import _keys

COST_TREND_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"]
COST_TREND_COST_TYPES = ["TOTAL", "VARIABLE", "FIXED"]

# Entry-only subset of COST_TREND_COST_TYPES: "TOTAL COST" is always
# VARIABLE + FIXED, computed by page_cost_trend.py, never entered directly
# (see repo/cost_trend.py).
COST_TREND_ENTRY_PLANTS = COST_TREND_PLANTS
COST_TREND_ENTRY_COST_TYPES = ["VARIABLE", "FIXED"]


def _check_entry(key_column, key, product, cost_type, plant):
    """v1's column checks for one row, in v1's column order, then the plant
    model check."""
    _keys.fits(key_column, key, 7, nullable=False)
    _keys.fits("product", product, 8, nullable=False)
    _keys.fits("cost_type", cost_type, 16, nullable=False)
    _keys.fits("plant", plant, 16, nullable=False)
    if key_column == "report_month":
        _keys.check_month(key)
    _keys.check_plant_model(plant, "plant", 16)


def get_cost_trend_annual(product: str, fys: List[str]) -> Dict[str, Any]:
    """{fy: {cost_type: {plant: value}}} for the given product ('HM'/'CS'/
    'SS') across the given FYs — used both by the report page (page_cost_
    trend.py) and the data-entry form's pre-fill."""
    conn = connect()
    try:
        cur = conn.cursor()
        out = {fy: {ct: {} for ct in COST_TREND_COST_TYPES} for fy in fys}
        if fys:
            ph = ",".join(["%s"] * len(fys))
            cur.execute(
                f"SELECT fy, cost_type, plant_code, value FROM cost_trend_annual "
                f"WHERE product=%s AND fy IN ({ph}) ORDER BY fy, cost_type, plant_code",
                (product, *fys),
            )
            for fy, cost_type, plant, value in cur.fetchall():
                out.setdefault(fy, {}).setdefault(cost_type, {})[plant] = value
    finally:
        conn.close()
    return out


def save_cost_trend_annual(fy: str, product: str, entries: List[Dict[str, Any]]) -> int:
    """Upsert a batch of {cost_type, plant, value} entries for one FY/product
    (the data-entry form's Annual tab submits every cell for the FY/product
    it's editing in one call)."""
    stored_fy = _keys.fit_fy(fy)
    conn = connect()
    try:
        cur = conn.cursor()
        saved = 0
        _ver.bump(cur)
        for e in entries:
            cost_type, plant = e["cost_type"], e["plant"]
            _check_entry("fy", stored_fy, product, cost_type, plant)
            _keys.ensure_plant(cur, plant, bump=False)
            cur.execute("""
                INSERT INTO cost_trend_annual (fy, product, cost_type, plant_code, value)
                VALUES (%s, %s, %s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE value = new.value
            """, (stored_fy, product, cost_type, plant, e.get("value")))
            saved += 1
        conn.commit()
    finally:
        conn.close()
    return saved


def get_cost_trend_monthly(product: str, report_months: List[str]) -> Dict[str, Any]:
    """{report_month: {cost_type: {plant: {"month": v, "till_month": v}}}}
    for the given product across the given report_months."""
    conn = connect()
    try:
        cur = conn.cursor()
        out = {rm: {ct: {} for ct in COST_TREND_COST_TYPES} for rm in report_months}
        if report_months:
            ph = ",".join(["%s"] * len(report_months))
            cur.execute(
                f"SELECT report_month, cost_type, plant_code, month_value, till_month_value "
                f"FROM cost_trend_monthly WHERE product=%s AND report_month IN ({ph}) "
                f"ORDER BY report_month, cost_type, plant_code",
                (product, *report_months),
            )
            for rm, cost_type, plant, mv, tmv in cur.fetchall():
                out.setdefault(rm, {}).setdefault(cost_type, {})[plant] = {"month": mv, "till_month": tmv}
    finally:
        conn.close()
    return out


def save_cost_trend_monthly(report_month: str, product: str, entries: List[Dict[str, Any]]) -> int:
    """Upsert a batch of {cost_type, plant, month_value, till_month_value}
    entries for one report_month/product (the data-entry form's Monthly tab
    submits every cell for the month/product it's editing in one call); a
    blank cell is saved as NULL (see repo/cost_trend.py)."""
    stored_month = _keys.fit_month(report_month)
    conn = connect()
    try:
        cur = conn.cursor()
        saved = 0
        _ver.bump(cur)
        for e in entries:
            cost_type, plant = e["cost_type"], e["plant"]
            _check_entry("report_month", stored_month, product, cost_type, plant)
            _keys.ensure_month(cur, stored_month, bump=False)
            _keys.ensure_plant(cur, plant, bump=False)
            cur.execute("""
                INSERT INTO cost_trend_monthly (report_month, product, cost_type, plant_code, month_value, till_month_value)
                VALUES (%s, %s, %s, %s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE month_value = new.month_value, till_month_value = new.till_month_value
            """, (stored_month, product, cost_type, plant, e.get("month_value"), e.get("till_month_value")))
            saved += 1
        conn.commit()
    finally:
        conn.close()
    return saved


def save_cost_trend_monthly_field(report_month: str, product: str, entries: List[Dict[str, Any]], field: str) -> int:
    """Upsert a batch of {cost_type, plant, value} entries into ONE column
    (field: 'month_value' or 'till_month_value') of cost_trend_monthly,
    leaving the other column untouched on an existing row (the Cost Trend
    Excel extractor; see repo/cost_trend.py)."""
    if field not in ("month_value", "till_month_value"):
        raise ValueError(f"field must be 'month_value' or 'till_month_value', got {field!r}")
    stored_month = _keys.fit_month(report_month)
    conn = connect()
    try:
        cur = conn.cursor()
        saved = 0
        _ver.bump(cur)
        for e in entries:
            cost_type, plant = e["cost_type"], e["plant"]
            _check_entry("report_month", stored_month, product, cost_type, plant)
            _keys.ensure_month(cur, stored_month, bump=False)
            _keys.ensure_plant(cur, plant, bump=False)
            cur.execute(f"""
                INSERT INTO cost_trend_monthly (report_month, product, cost_type, plant_code, {field})
                VALUES (%s, %s, %s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE {field} = new.{field}
            """, (stored_month, product, cost_type, plant, e.get("value")))
            saved += 1
        conn.commit()
    finally:
        conn.close()
    return saved


# ── Named queries ────────────────────────────────────────────────────────────

def monthly_any_row(report_month):
    """True when cost_trend_monthly has any row for the month.
    page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT 1 FROM cost_trend_monthly WHERE report_month = %s LIMIT 1",
                    [report_month])
        return bool(cur.fetchall())
