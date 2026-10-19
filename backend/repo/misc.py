"""Miscellaneous small repositories: market_price_trend_monthly ("Movement
of Key Prices - International", page 2.41) and macro_indicators_monthly
("India Macro Economic Indicators", page 2.42), both entered via
/data-entry/market-intel or the market-commentary PDF upload.

The db.py functions moved here verbatim (re-exported from db.py).
"""
from typing import Any, Dict, List

from dbengine import connect


# ── "Movement of Key Prices - International" (page 2.41) ───────────────────
# Backing store for page_market_prices.py + /data-entry/market-intel. See
# scripts/migrate_add_market_intel.sql.

def get_market_price_trend(report_months: List[str]) -> Dict[str, Dict[str, float]]:
    """-> {report_month: {series_code: value}}."""
    conn = connect()
    cur = conn.cursor()
    out = {m: {} for m in report_months}
    if report_months:
        ph = ",".join(["%s"] * len(report_months))
        cur.execute(f"SELECT report_month, series_code, value FROM market_price_trend_monthly "
                    f"WHERE report_month IN ({ph})", report_months)
        for rm, series, value in cur.fetchall():
            out.setdefault(rm, {})[series] = value
    conn.close()
    return out


def save_market_price_trend(rows: List[Dict[str, Any]]) -> int:
    """Upsert market_price_trend_monthly rows: {report_month, series_code, value}."""
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO market_price_trend_monthly (report_month, series_code, value)
            VALUES (%s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE value = new.value
        """, (r["report_month"], r["series_code"], r.get("value")))
    conn.commit()
    conn.close()
    return len(rows)


# ── "India Macro Economic Indicators" (page 2.42) ───────────────────────────
# Backing store for page_macro_indicators.py + /data-entry/market-intel. See
# scripts/migrate_add_market_intel.sql.

def get_macro_indicators(report_months: List[str]) -> Dict[str, Dict[str, float]]:
    """-> {report_month: {metric_code: value}}."""
    conn = connect()
    cur = conn.cursor()
    out = {m: {} for m in report_months}
    if report_months:
        ph = ",".join(["%s"] * len(report_months))
        cur.execute(f"SELECT report_month, metric_code, value FROM macro_indicators_monthly "
                    f"WHERE report_month IN ({ph})", report_months)
        for rm, metric, value in cur.fetchall():
            out.setdefault(rm, {})[metric] = value
    conn.close()
    return out


def save_macro_indicators(rows: List[Dict[str, Any]]) -> int:
    """Upsert macro_indicators_monthly rows: {report_month, metric_code, value}."""
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO macro_indicators_monthly (report_month, metric_code, value)
            VALUES (%s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE value = new.value
        """, (r["report_month"], r["metric_code"], r.get("value")))
    conn.commit()
    conn.close()
    return len(rows)

