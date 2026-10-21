"""Cost trend repository: cost_trend_annual (per-FY Cost of Production per
product / cost type / plant) and cost_trend_monthly (month + till-month
figures). Feeds page_cost_trend.py (HM/CS/SS) and page_key_parameters.py's
CoP rows (COKE/SINTER); written by the Cost Trend entry form, the Cost Trend
Excel extractor confirm (save_cost_trend_monthly_field) and backfill scripts.

The db.py functions and constants moved here verbatim (re-exported from
db.py). They open their own connection via dbengine.connect, so the
rollback_tx() dry-run routing still applies.
"""
from typing import Any, Dict, List

from dbengine import connect
from repo import version as _ver
from repo import conn as rc


# ── Moved from db.py ─────────────────────────────────────────────────────────

COST_TREND_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"]
COST_TREND_COST_TYPES = ["TOTAL", "VARIABLE", "FIXED"]

# Entry-only subset of COST_TREND_COST_TYPES: "TOTAL COST" is always
# VARIABLE + FIXED, computed by page_cost_trend.py, never entered directly.
# Every plant in COST_TREND_PLANTS (including SAIL 5 ISPs) is entered
# directly for VARIABLE/FIXED — SAIL is its own reported figure, not a sum
# of the other 5 plants (that was tried and reverted; a plant-level rollup
# doesn't necessarily match SAIL's own cost of production).
COST_TREND_ENTRY_PLANTS = COST_TREND_PLANTS
COST_TREND_ENTRY_COST_TYPES = ["VARIABLE", "FIXED"]


def get_cost_trend_annual(product: str, fys: List[str]) -> Dict[str, Any]:
    """{fy: {cost_type: {plant: value}}} for the given product ('HM'/'CS'/
    'SS') across the given FYs — used both by the report page (page_cost_
    trend.py) and the data-entry form's pre-fill."""
    conn = connect()
    cur = conn.cursor()
    out = {fy: {ct: {} for ct in COST_TREND_COST_TYPES} for fy in fys}
    if fys:
        ph = ",".join(["%s"] * len(fys))
        cur.execute(
            f"SELECT fy, cost_type, plant, value FROM cost_trend_annual "
            f"WHERE product=%s AND fy IN ({ph})",
            (product, *fys),
        )
        for fy, cost_type, plant, value in cur.fetchall():
            out.setdefault(fy, {}).setdefault(cost_type, {})[plant] = value
    conn.close()
    return out


def save_cost_trend_annual(fy: str, product: str, entries: List[Dict[str, Any]]) -> int:
    """Upsert a batch of {cost_type, plant, value} entries for one FY/product
    (the data-entry form's Annual tab submits every cell for the FY/product
    it's editing in one call)."""
    conn = connect()
    cur = conn.cursor()
    saved = 0
    for e in entries:
        cur.execute("""
            INSERT INTO cost_trend_annual (fy, product, cost_type, plant, value)
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE value = new.value
        """, (fy, product, e["cost_type"], e["plant"], e.get("value")))
        saved += 1
    _ver.bump(conn)
    conn.commit()
    conn.close()
    return saved


def get_cost_trend_monthly(product: str, report_months: List[str]) -> Dict[str, Any]:
    """{report_month: {cost_type: {plant: {"month": v, "till_month": v}}}}
    for the given product across the given report_months."""
    conn = connect()
    cur = conn.cursor()
    out = {rm: {ct: {} for ct in COST_TREND_COST_TYPES} for rm in report_months}
    if report_months:
        ph = ",".join(["%s"] * len(report_months))
        cur.execute(
            f"SELECT report_month, cost_type, plant, month_value, till_month_value "
            f"FROM cost_trend_monthly WHERE product=%s AND report_month IN ({ph})",
            (product, *report_months),
        )
        for rm, cost_type, plant, mv, tmv in cur.fetchall():
            out.setdefault(rm, {}).setdefault(cost_type, {})[plant] = {"month": mv, "till_month": tmv}
    conn.close()
    return out


def save_cost_trend_monthly(report_month: str, product: str, entries: List[Dict[str, Any]]) -> int:
    """Upsert a batch of {cost_type, plant, month_value, till_month_value}
    entries for one report_month/product (the data-entry form's Monthly tab
    submits every cell for the month/product it's editing in one call).
    Either value may be None — same "only overwrite what's actually
    provided" wouldn't apply here since this is a full-grid submit, not a
    partial merge, so a blank cell is saved as NULL (matches how the grid's
    own blank state should round-trip)."""
    conn = connect()
    cur = conn.cursor()
    saved = 0
    for e in entries:
        cur.execute("""
            INSERT INTO cost_trend_monthly (report_month, product, cost_type, plant, month_value, till_month_value)
            VALUES (%s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE month_value = new.month_value, till_month_value = new.till_month_value
        """, (report_month, product, e["cost_type"], e["plant"], e.get("month_value"), e.get("till_month_value")))
        saved += 1
    _ver.bump(conn)
    conn.commit()
    conn.close()
    return saved


def save_cost_trend_monthly_field(report_month: str, product: str, entries: List[Dict[str, Any]], field: str) -> int:
    """Upsert a batch of {cost_type, plant, value} entries into ONE column
    (field: 'month_value' or 'till_month_value') of cost_trend_monthly,
    leaving the other column untouched on an existing row. Used by the Cost
    Trend Excel extractor (excel_extractors/excel_extractor_cost_trend.py),
    which reads the month figure and the till-month figure from two
    separate source workbooks — unlike save_cost_trend_monthly's full-grid
    submit, writing both columns unconditionally here would blank out
    whichever one wasn't part of this particular extraction."""
    if field not in ("month_value", "till_month_value"):
        raise ValueError(f"field must be 'month_value' or 'till_month_value', got {field!r}")
    conn = connect()
    cur = conn.cursor()
    saved = 0
    for e in entries:
        cur.execute(f"""
            INSERT INTO cost_trend_monthly (report_month, product, cost_type, plant, {field})
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE {field} = new.{field}
        """, (report_month, product, e["cost_type"], e["plant"], e.get("value")))
        saved += 1
    _ver.bump(conn)
    conn.commit()
    conn.close()
    return saved



# ── Named queries (moved verbatim from page_missing_data) ─────────────────────

def monthly_any_row(report_month):
    """True when cost_trend_monthly has any row for the month.
    page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT 1 FROM cost_trend_monthly WHERE report_month = %s LIMIT 1",
                    [report_month])
        return bool(cur.fetchall())
