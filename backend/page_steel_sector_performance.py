"""
"Indian Steel Sector Performance" — pages 2.1-2.4, right after the Index
(see main.py's STEEL_SECTOR_PAGES). Reproduces the monthly PIB (Ministry of
Steel) release archived by pdf_extractor_steel_sector_performance.py /
/api/steel-sector-performance/confirm into steel_sector_performance_table,
verbatim — EXCEPT Table 1a (Production Overview), which gets SAIL's own
Crude Steel / Hot Metal / Finished Steel actuals appended as extra rows,
plus SAIL's % share of the India total for each of the table's four value
columns (report month, CPLY month, Apr-report-month cumulative, CPLY
Apr-report-month cumulative).

SAIL rollup for those extra rows reuses db.get_sail_production_ytd_actual()
— the same helper page_records.py / page_jpc_report.py's SAIL total already
relies on (5 core plants + ASP/SSP/VISL, with the Finished-Steel SSP/VISL
alias) — passed a single-element month list for a single month's actual, or
db.get_ytd_months(month) for an Apr-to-month cumulative. No new SAIL-rollup
logic here.
"""
import json

import db

# PDF's Table 1a item label -> production_table's own item_name.
_ITEM_DB_NAME = {
    "Crude Steel": "Total Crude Steel",
    "Hot Metal": "Hot Metal",
    "Finished Steel": "Finished Steel",
}

_VALUE_COLS = ["report_month", "cply_month", "apr_report_month", "cply_apr_report_month"]


def _load_row(report_month: str):
    """Freshest archived release at-or-before report_month — same
    "latest snapshot at-or-before" convention page_power_data.py uses for
    its Cum. row, so a month gets last month's release shown (labelled as
    such) rather than a blank page until that month's own PDF is uploaded."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT report_month, data_json, source_file FROM steel_sector_performance_table
            WHERE report_month <= ?
            ORDER BY report_month DESC LIMIT 1
        """, (report_month,))
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None, None, None
    data_month, data_json, source_file = row
    return data_month, (json.loads(data_json) if data_json else None), source_file


_KT_TO_MT = 1000.0  # production_table stores '000 T (see page_jpc_report.py's "Unit:'000 T");
                     # the PDF's Table 1a figures are in Mt (Million Tonnes) — convert to match.


def _sail_value(item_db_name: str, months: list) -> float:
    v = db.get_sail_production_ytd_actual(months, item_db_name)
    return round(v / _KT_TO_MT, 3) if v is not None else None


def _share_pct(sail_val, india_val):
    if sail_val is None or not india_val:
        return None
    return round(sail_val / india_val * 100, 1)


def _augment_production_overview(items: list, report_month: str) -> list:
    """Appends a 'SAIL' row and a 'SAIL Share %' row right after each
    India-total item row, using the item's own data (Crude Steel / Hot
    Metal / Finished Steel only — the three rows this table has)."""
    cply_month = db.get_cply_month(report_month)
    ytd_months = db.get_ytd_months(report_month)
    cply_ytd_months = db.get_ytd_months(cply_month)

    out = []
    for row in items:
        out.append(row)
        db_item = _ITEM_DB_NAME.get(row["item"])
        if not db_item:
            continue

        sail = {
            "report_month": _sail_value(db_item, [report_month]),
            "cply_month": _sail_value(db_item, [cply_month]),
            "apr_report_month": _sail_value(db_item, ytd_months),
            "cply_apr_report_month": _sail_value(db_item, cply_ytd_months),
        }
        sail_row = {"item": f"SAIL {row['item']}", "kind": "sail", **sail}
        share_row = {
            "item": "SAIL Share % of India",
            "kind": "share",
            **{col: _share_pct(sail[col], row.get(col)) for col in _VALUE_COLS},
        }
        out.append(sail_row)
        out.append(share_row)
    return out


def generate_steel_sector_performance(report_month: str, section: str = "all") -> dict:
    """section selects which physical page's slice of content to return
    (see main.py's STEEL_SECTOR_PAGES) — 'all' returns everything, for
    direct/API use outside the paginated report flow."""
    data_month, data, source_file = _load_row(report_month)
    page = {
        "type": "steel_sector_performance",
        "section": section,
        "report_month": report_month,
        "data_month": data_month,
        "available": data is not None,
    }
    if data is None:
        return page

    page.update({
        "title": data.get("title"),
        "posted_on": data.get("posted_on"),
        "tables": data.get("tables", {}),
        "text_sections": data.get("text_sections", {}),
        "footer_note": data.get("footer_note"),
        "source_file": source_file,
        "production_overview_1a": _augment_production_overview(
            data.get("production_overview_1a_items", []), data_month or report_month,
        ),
    })
    return page
